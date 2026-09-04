from __future__ import annotations

import html
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from . import __version__
from .config import Settings, settings_from_env
from .jobs import JobError, JobManager, JobSpec
from .security import AuthError, Identity, constant_time_equals, verify_session_token
from .webhooks import router as webhooks_router


class JobSpecIn(BaseModel):
    target_url: str = Field(min_length=1, max_length=2048)
    shop_domain: str | None = Field(default=None, max_length=255)
    locale: str = "en-US"
    max_pages: int = 10
    render_mode: str = "auto"
    demo: bool = False


class DiscoverSpecIn(BaseModel):
    shop_domain: str | None = Field(default=None, max_length=255)
    subject: str = Field(min_length=1, max_length=300)
    brand: str = Field(default="", max_length=300)
    seed_queries: list[str] = Field(min_length=1, max_length=20)
    locale: str = "en-US"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or settings_from_env()
    app = FastAPI(title="GEOHub Shopify backend", version=__version__ or "0.1.0")
    app.state.settings = settings
    app.state.job_manager = JobManager(
        settings.data_root,
        fixture_root=settings.fixture_root,
        max_workers=settings.max_workers,
    )
    app.include_router(webhooks_router)

    @app.exception_handler(RequestValidationError)
    async def _plain_validation_error(request: Request, exc: RequestValidationError):
        # Return a string detail: array details crash the React Banner renderer.
        messages = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", []) if part != "body")
            message = str(error.get("msg", "invalid input"))
            messages.append(f"{loc}: {message}" if loc else message)
        return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})

    @app.on_event("shutdown")
    def _shutdown_job_manager() -> None:
        app.state.job_manager.shutdown()

    def require_identity(request: Request) -> Identity:
        header = request.headers.get("authorization", "")
        if header.startswith("Bearer "):
            if not settings.session_auth_ready:
                raise HTTPException(status_code=503, detail="session auth is not configured")
            try:
                return verify_session_token(
                    header[len("Bearer ") :],
                    api_key=settings.shopify_api_key or "",
                    api_secret=settings.shopify_api_secret or "",
                )
            except AuthError as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc
        service_key = request.headers.get("x-app-api-key", "")
        if service_key and settings.service_api_key and constant_time_equals(
            service_key, settings.service_api_key
        ):
            return Identity(principal="service", kind="service")
        if settings.dev_mode:
            return Identity(principal="dev", kind="dev")
        raise HTTPException(status_code=401, detail="missing or invalid credentials")

    def authorize_job(request: Request, identity: Identity, job) -> None:
        """Single-job endpoints must not leak data across shops (IDOR guard)."""
        if identity.kind == "session":
            if job.shop_domain != identity.principal:
                raise HTTPException(status_code=404, detail="job not found")
            return
        if identity.kind == "service":
            # The Remix proxy must forward the authenticated session's shop.
            shop = (request.headers.get("x-shop-domain") or "").strip().lower()
            if not shop:
                raise HTTPException(status_code=403, detail="x-shop-domain header is required")
            if job.shop_domain != shop:
                raise HTTPException(status_code=404, detail="job not found")
            return
        # dev identity: dev mode only, no cross-shop isolation
        return

    def bind_shop(request: Request, identity: Identity, payload_shop: object) -> str | None:
        """Create endpoints never trust the body's shop_domain (tenant binding)."""
        if identity.kind == "session":
            return identity.principal
        if identity.kind == "service":
            header_shop = (request.headers.get("x-shop-domain") or "").strip().lower()
            if not header_shop:
                raise HTTPException(status_code=403, detail="x-shop-domain header is required")
            declared = str(payload_shop or "").strip().lower()
            if declared and "." not in declared:
                declared = f"{declared}.myshopify.com"
            if declared and declared != header_shop:
                raise HTTPException(
                    status_code=403,
                    detail="shop_domain does not match the authenticated shop",
                )
            return header_shop
        return None  # dev identity

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "service": "geohub-shopify-backend",
            "version": __version__ or "0.1.0",
            "dev_mode": settings.dev_mode,
            "session_auth_ready": settings.session_auth_ready,
        }

    @app.post("/api/diagnosis-jobs", status_code=202)
    def create_job(
        spec: JobSpecIn, request: Request, identity: Identity = Depends(require_identity)
    ) -> dict:
        try:
            job = app.state.job_manager.submit(
                JobSpec(
                    target_url=spec.target_url.strip(),
                    shop_domain=bind_shop(request, identity, spec.shop_domain),
                    locale=spec.locale,
                    max_pages=spec.max_pages,
                    render_mode=spec.render_mode,
                    demo=spec.demo,
                )
            )
        except JobError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return job.to_public_dict()

    @app.get("/api/diagnosis-jobs")
    def list_jobs(
        request: Request,
        shop_domain: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        identity: Identity = Depends(require_identity),
    ) -> dict:
        # List results are always scoped to one shop; no cross-shop enumeration.
        if identity.kind == "session":
            if shop_domain and shop_domain != identity.principal:
                raise HTTPException(status_code=403, detail="cannot list another shop's jobs")
            shop_domain = identity.principal
        elif identity.kind == "service":
            header_shop = (request.headers.get("x-shop-domain") or "").strip().lower()
            if not header_shop:
                raise HTTPException(status_code=403, detail="x-shop-domain header is required")
            if shop_domain and shop_domain != header_shop:
                raise HTTPException(status_code=403, detail="cannot list another shop's jobs")
            shop_domain = header_shop
        jobs = app.state.job_manager.list(shop_domain=shop_domain, limit=limit, kind="diagnosis")
        return {"jobs": [job.to_public_dict() for job in jobs]}

    @app.get("/api/diagnosis-jobs/{job_id}")
    def get_job(job_id: str, request: Request, identity: Identity = Depends(require_identity)) -> dict:
        job = app.state.job_manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        authorize_job(request, identity, job)
        return job.to_public_dict()

    @app.get("/api/diagnosis-jobs/{job_id}/report")
    def get_report(job_id: str, request: Request, identity: Identity = Depends(require_identity)) -> FileResponse:
        job = app.state.job_manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="report is not available")
        authorize_job(request, identity, job)
        report = app.state.job_manager.report_path(job_id)
        if report is None:
            raise HTTPException(status_code=404, detail="report is not available")
        return FileResponse(report, media_type="text/html", filename=f"{job_id}-geo-report.html")

    @app.get("/api/diagnosis-jobs/{job_id}/artifacts/{name}")
    def get_artifact(
        job_id: str, name: str, request: Request, identity: Identity = Depends(require_identity)
    ) -> FileResponse:
        job = app.state.job_manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="artifact is not available")
        authorize_job(request, identity, job)
        artifact = app.state.job_manager.artifact_path(job_id, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="artifact is not available")
        media = "text/markdown; charset=utf-8" if name.endswith(".md") else "application/json"
        return FileResponse(artifact, media_type=media)

    @app.post("/api/discover-jobs", status_code=202)
    def create_discover_job(
        spec: DiscoverSpecIn, request: Request, identity: Identity = Depends(require_identity)
    ) -> dict:
        try:
            job = app.state.job_manager.submit(
                JobSpec(
                    kind="discover",
                    subject=spec.subject.strip(),
                    brand=spec.brand.strip(),
                    seed_queries=tuple(q.strip() for q in spec.seed_queries if q.strip()),
                    locale=spec.locale,
                    shop_domain=bind_shop(request, identity, spec.shop_domain),
                )
            )
        except JobError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return job.to_public_dict()

    @app.get("/api/discover-jobs")
    def list_discover_jobs(
        request: Request,
        shop_domain: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        identity: Identity = Depends(require_identity),
    ) -> dict:
        if identity.kind == "session":
            if shop_domain and shop_domain != identity.principal:
                raise HTTPException(status_code=403, detail="cannot list another shop's jobs")
            shop_domain = identity.principal
        elif identity.kind == "service":
            header_shop = (request.headers.get("x-shop-domain") or "").strip().lower()
            if not header_shop:
                raise HTTPException(status_code=403, detail="x-shop-domain header is required")
            if shop_domain and shop_domain != header_shop:
                raise HTTPException(status_code=403, detail="cannot list another shop's jobs")
            shop_domain = header_shop
        jobs = app.state.job_manager.list(shop_domain=shop_domain, limit=limit, kind="discover")
        return {"jobs": [job.to_public_dict() for job in jobs]}

    @app.get("/api/discover-jobs/{job_id}")
    def get_discover_job(
        job_id: str, request: Request, identity: Identity = Depends(require_identity)
    ) -> dict:
        job = app.state.job_manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        authorize_job(request, identity, job)
        return job.to_public_dict()

    # -- generic registry for the remaining skill endpoints ----------------

    def str_field(payload: dict, key: str, *, max_length: int = 5000, default: str = "") -> str:
        """Type- and length-safe string extraction for raw skill payloads."""
        value = payload.get(key, default)
        if value is None:
            value = default
        if isinstance(value, bool) or not isinstance(value, str):
            raise JobError(f"{key} must be a string")
        if len(value) > max_length:
            raise JobError(f"{key} exceeds {max_length} characters")
        return value

    def register_kind_endpoints(prefix: str, kind: str, build_spec) -> None:
        """Create the POST/list/get triplet for one skill, shop-scoped."""

        @app.post(f"/api/{prefix}", status_code=202, name=f"create_{kind}")
        def create_skill_job(
            request: Request, payload: dict, identity: Identity = Depends(require_identity)
        ) -> dict:
            if not isinstance(payload, dict):
                raise HTTPException(status_code=422, detail="request body must be a JSON object")
            try:
                job = app.state.job_manager.submit(build_spec(payload, bind_shop(request, identity, payload.get("shop_domain"))))
            except JobError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            return job.to_public_dict()

        @app.get(f"/api/{prefix}", name=f"list_{kind}")
        def list_skill_jobs(
            request: Request,
            shop_domain: str | None = Query(default=None),
            limit: int = Query(default=50, ge=1, le=200),
            identity: Identity = Depends(require_identity),
        ) -> dict:
            if identity.kind == "session":
                if shop_domain and shop_domain != identity.principal:
                    raise HTTPException(status_code=403, detail="cannot list another shop's jobs")
                shop_domain = identity.principal
            elif identity.kind == "service":
                header_shop = (request.headers.get("x-shop-domain") or "").strip().lower()
                if not header_shop:
                    raise HTTPException(status_code=403, detail="x-shop-domain header is required")
                if shop_domain and shop_domain != header_shop:
                    raise HTTPException(status_code=403, detail="cannot list another shop's jobs")
                shop_domain = header_shop
            jobs = app.state.job_manager.list(shop_domain=shop_domain, limit=limit, kind=kind)
            return {"jobs": [job.to_public_dict() for job in jobs]}

        @app.get(f"/api/{prefix}/{{job_id}}", name=f"get_{kind}")
        def get_skill_job(
            job_id: str, request: Request, identity: Identity = Depends(require_identity)
        ) -> dict:
            job = app.state.job_manager.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="job not found")
            authorize_job(request, identity, job)
            return job.to_public_dict()

    def clean_observations(payload: dict) -> tuple[dict, ...]:
        raw = payload.get("observations")
        if not isinstance(raw, list):
            raise JobError("observations must be an array")
        cleaned = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise JobError(f"observations[{index}] must be an object")
            cleaned.append(
                {
                    "query_id": str_field(item, "query_id", max_length=200),
                    "answered": bool(item.get("answered", True)),
                    "cited": item.get("cited"),
                    "collected_at": item.get("collected_at"),
                }
            )
        return tuple(cleaned)

    register_kind_endpoints(
        "content-jobs", "content",
        lambda p, shop: JobSpec(
            kind="content",
            shop_domain=shop,
            mode=str_field(p, "mode", max_length=50),
            topic=str_field(p, "topic", max_length=1000),
            audience=str_field(p, "audience", max_length=300),
            brand=str_field(p, "brand", max_length=300),
            source_content=str_field(p, "source_content", max_length=100000),
            locale=str_field(p, "locale", max_length=10, default="en-US"),
        ),
    )
    register_kind_endpoints(
        "measure-jobs", "measure",
        lambda p, shop: JobSpec(
            kind="measure",
            shop_domain=shop,
            subject=str_field(p, "subject", max_length=500),
            brand=str_field(p, "brand", max_length=300),
            engine=str_field(p, "engine", max_length=100),
            observations=clean_observations(p),
            locale=str_field(p, "locale", max_length=10, default="en-US"),
        ),
    )
    register_kind_endpoints(
        "knowledge-jobs", "knowledge",
        lambda p, shop: JobSpec(
            kind="knowledge",
            shop_domain=shop or "",
            brand=str_field(p, "brand", max_length=300),
            locale=str_field(p, "locale", max_length=10, default="en-US"),
        ),
    )
    register_kind_endpoints(
        "compare-jobs", "compare",
        lambda p, shop: JobSpec(
            kind="compare",
            shop_domain=shop,
            my_url=str_field(p, "my_url", max_length=2048),
            competitor_urls=tuple(
                url.strip() for url in (
                    p.get("competitor_urls") if isinstance(p.get("competitor_urls"), list) else []
                ) if isinstance(url, str) and url.strip()
            ),
            locale=str_field(p, "locale", max_length=10, default="en-US"),
        ),
    )

    @app.get("/api/retention")
    def retention_preview(identity: Identity = Depends(require_identity)) -> dict:
        if identity.kind not in ("service", "dev"):
            raise HTTPException(status_code=403, detail="service credentials required")
        return app.state.job_manager.retention_sweep(confirm=False)

    @app.post("/api/retention/apply")
    def retention_apply(identity: Identity = Depends(require_identity)) -> dict:
        if identity.kind not in ("service", "dev"):
            raise HTTPException(status_code=403, detail="service credentials required")
        return app.state.job_manager.retention_sweep(confirm=True)

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse(url="/demo")

    @app.get("/demo", include_in_schema=False)
    def demo_page() -> HTMLResponse:
        return HTMLResponse(_DEMO_PAGE)

    return app


_DEMO_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GEOHub Shopify PoC</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f6f6f7; color: #303030; }
  header { background: #303030; color: #fff; padding: 14px 24px; font-size: 15px; }
  main { max-width: 760px; margin: 32px auto; padding: 0 16px; }
  .card { background: #fff; border: 1px solid #e1e1e2; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
  label { display: block; font-weight: 600; margin: 12px 0 4px; font-size: 13px; }
  input, select { width: 100%; padding: 8px 10px; border: 1px solid #c9c9ca; border-radius: 6px; box-sizing: border-box; font-size: 14px; }
  button { margin-top: 16px; background: #000; color: #fff; border: none; border-radius: 6px; padding: 10px 18px; font-size: 14px; cursor: pointer; }
  button:disabled { background: #8a8a8a; cursor: default; }
  .status { margin-top: 12px; font-size: 13px; }
  .score { font-size: 42px; font-weight: 700; }
  .meta { color: #6d6d6e; font-size: 13px; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 8px; }
  td, th { border-bottom: 1px solid #e1e1e2; padding: 6px 4px; text-align: left; }
  iframe { width: 100%; height: 640px; border: 1px solid #e1e1e2; border-radius: 8px; background: #fff; }
  .pill { display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: 12px; margin-right: 6px; }
  .ok { background: #d4f4dd; } .warn { background: #ffe9c7; } .muted { background: #eeeeef; }
</style>
</head>
<body>
<header>GEOHub for Shopify &middot; Phase 0 PoC &middot; local pipeline demo</header>
<main>
  <div class="card">
    <h2 style="margin-top:0">Run a GEO diagnosis</h2>
    <form id="f">
      <label for="url">Storefront URL</label>
      <input id="url" name="url" placeholder="https://your-store.myshopify.com" required>
      <label for="locale">Report language</label>
      <select id="locale"><option value="en-US">English</option><option value="zh-CN">中文</option></select>
      <label for="pages">Representative pages (max 10)</label>
      <input id="pages" type="number" min="1" max="10" value="10">
      <button id="go" type="submit">Start diagnosis</button>
      <label style="margin-top:16px"><input type="checkbox" id="demo" style="width:auto"> Offline demo (bundled fixture, no network fetch)</label>
    </form>
    <div class="status" id="status"></div>
  </div>
  <div class="card" id="result" style="display:none"></div>
  <div class="card" id="reportcard" style="display:none">
    <h2 style="margin-top:0">Visual report</h2>
    <iframe id="report"></iframe>
  </div>
</main>
<script>
const $ = (id) => document.getElementById(id);
let timer = null;
$("f").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("go").disabled = true;
  $("status").textContent = "Submitting…";
  const body = {
    target_url: $("url").value.trim(),
    locale: $("locale").value,
    max_pages: parseInt($("pages").value, 10) || 10,
    render_mode: "auto",
    demo: $("demo").checked,
  };
  try {
    const res = await fetch("/api/diagnosis-jobs", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.status);
    const job = await res.json();
    $("status").textContent = "Job " + job.job_id + " queued…";
    timer = setInterval(() => poll(job.job_id), 1500);
  } catch (err) {
    $("status").textContent = "Failed: " + err.message;
    $("go").disabled = false;
  }
});
async function poll(id) {
  const res = await fetch("/api/diagnosis-jobs/" + id);
  const job = await res.json();
  if (job.status === "queued" || job.status === "running") {
    $("status").textContent = "Job " + id + " " + job.status + "…";
    return;
  }
  clearInterval(timer);
  $("go").disabled = false;
  if (job.status === "failed") {
    $("status").textContent = "Job failed: " + job.error;
    return;
  }
  $("status").textContent = "Job " + id + " finished.";
  show(job);
}
function band(score) {
  if (score === null || score === undefined) return ["no score", "muted"];
  if (score >= 80) return [score + " · high readiness", "ok"];
  if (score >= 55) return [score + " · sound foundation", "ok"];
  return [score, "warn"];
}
function show(job) {
  const [label, cls] = band(job.overall_score);
  const rows = (job.dimensions || []).map((d) =>
    "<tr><td>" + esc(d.label || d.key) + "</td><td>" + (d.score ?? "–") + "</td></tr>"
  ).join("");
  const crawlers = (job.ai_crawlers || []).map((c) => {
    const state = c.allowed === true ? ["allowed", "ok"] : c.allowed === false ? ["blocked", "warn"] : ["unknown", "muted"];
    return '<span class="pill ' + state[1] + '">' + esc(c.agent) + ": " + state[0] + "</span>";
  }).join("");
  $("result").style.display = "";
  $("result").innerHTML =
    '<div class="score">' + esc(label) + '</div>' +
    '<div class="meta">' + job.representative_pages + ' pages · confidence ' + job.confidence + ' · run ' + esc(job.run_id || "") + '</div>' +
    (crawlers ? '<div style="margin-top:10px">' + crawlers + "</div>" : "") +
    (rows ? '<table><tr><th>Dimension</th><th>Score</th></tr>' + rows + "</table>" : "");
  $("reportcard").style.display = "";
  $("report").src = "/api/diagnosis-jobs/" + job.job_id + "/report";
}
function esc(v) { const d = document.createElement("div"); d.textContent = String(v); return d.innerHTML; }
</script>
</body>
</html>
"""


app = create_app()
