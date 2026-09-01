from __future__ import annotations

import html
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
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
    def create_job(spec: JobSpecIn, identity: Identity = Depends(require_identity)) -> dict:
        try:
            shop_domain = spec.shop_domain
            if shop_domain:
                shop_domain = shop_domain.strip().lower()
                if "." not in shop_domain:
                    shop_domain = f"{shop_domain}.myshopify.com"
            job = app.state.job_manager.submit(
                JobSpec(
                    target_url=spec.target_url.strip(),
                    shop_domain=shop_domain,
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
        shop_domain: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        identity: Identity = Depends(require_identity),
    ) -> dict:
        jobs = app.state.job_manager.list(shop_domain=shop_domain, limit=limit)
        return {"jobs": [job.to_public_dict() for job in jobs]}

    @app.get("/api/diagnosis-jobs/{job_id}")
    def get_job(job_id: str, identity: Identity = Depends(require_identity)) -> dict:
        job = app.state.job_manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job.to_public_dict()

    @app.get("/api/diagnosis-jobs/{job_id}/report")
    def get_report(job_id: str, identity: Identity = Depends(require_identity)) -> FileResponse:
        report = app.state.job_manager.report_path(job_id)
        if report is None:
            raise HTTPException(status_code=404, detail="report is not available")
        return FileResponse(report, media_type="text/html", filename=f"{job_id}-geo-report.html")

    @app.get("/api/diagnosis-jobs/{job_id}/artifacts/{name}")
    def get_artifact(
        job_id: str, name: str, identity: Identity = Depends(require_identity)
    ) -> FileResponse:
        artifact = app.state.job_manager.artifact_path(job_id, name)
        if artifact is None:
            raise HTTPException(status_code=404, detail="artifact is not available")
        return FileResponse(artifact, media_type="application/json")

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
