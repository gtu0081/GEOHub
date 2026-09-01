from __future__ import annotations

import json
import re
import shutil
import socket
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from geo_seo_hub.diagnose import FetchResult, SourceUnavailable
from geo_seo_hub.site_diagnose import site_diagnose

JOB_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{7,63}$")
LOCALES = ("zh-CN", "en-US")
RENDER_MODES = ("auto", "http", "browser")
MAX_PAGES_LIMIT = 10
# Artifacts the API may serve next to report.html.
ALLOWED_ARTIFACTS = (
    "site-diagnosis.json",
    "remediation-backlog.json",
    "sampling-plan.json",
    "crawl-manifest.json",
    "quality-report.json",
    "run-manifest.json",
)


class JobError(ValueError):
    """Raised for invalid job submissions."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class JobSpec:
    target_url: str
    shop_domain: str | None = None
    locale: str = "en-US"
    max_pages: int = 10
    render_mode: str = "auto"
    demo: bool = False

    def validate(self) -> None:
        if self.locale not in LOCALES:
            raise JobError(f"locale must be one of {LOCALES}")
        if self.render_mode not in RENDER_MODES:
            raise JobError(f"render_mode must be one of {RENDER_MODES}")
        if not isinstance(self.max_pages, int) or not 1 <= self.max_pages <= MAX_PAGES_LIMIT:
            raise JobError(f"max_pages must be an integer in 1..{MAX_PAGES_LIMIT}")
        parsed = urlsplit(self.target_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise JobError("target_url must be an absolute http(s) URL")
        if parsed.username or parsed.password:
            raise JobError("target_url must not carry credentials")


@dataclass
class DiagnosisJob:
    job_id: str
    target_url: str
    shop_domain: str | None
    locale: str
    max_pages: int
    render_mode: str
    demo: bool
    status: str = "queued"  # queued | running | succeeded | failed
    created_at: str = field(default_factory=_utcnow)
    started_at: str | None = None
    finished_at: str | None = None
    run_id: str | None = None
    run_status: str | None = None
    overall_score: int | None = None
    confidence: float | None = None
    representative_pages: int | None = None
    dimensions: list[dict[str, Any]] = field(default_factory=list)
    ai_crawlers: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["report_url"] = f"/api/diagnosis-jobs/{self.job_id}/report" if self.status == "succeeded" else None
        return data


class JobManager:
    """Runs site-diagnose jobs on a small worker pool.

    Each job gets its own runs root (``data/runs/<job_id>``) so deterministic
    library run IDs can never collide across jobs or tenants.
    """

    def __init__(
        self,
        data_root: Path,
        *,
        fixture_root: Path | None = None,
        max_workers: int = 2,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._data_root = Path(data_root)
        self._fixture_root = Path(fixture_root) if fixture_root else None
        self._jobs: dict[str, DiagnosisJob] = {}
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="geohub-job")
        self._clock = clock
        self._jobs_dir = self._data_root / "jobs"
        self._runs_root = self._data_root / "runs"
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._runs_root.mkdir(parents=True, exist_ok=True)
        self._load_existing_jobs()

    # -- public API -------------------------------------------------------

    def submit(self, spec: JobSpec) -> DiagnosisJob:
        spec.validate()
        if spec.demo and self._fixture_root is None:
            raise JobError("demo jobs require the offline fixture bundle (GEOHUB_FIXTURE_ROOT)")
        job = DiagnosisJob(
            job_id=f"job-{uuid.uuid4().hex[:12]}",
            target_url=spec.target_url,
            shop_domain=spec.shop_domain,
            locale=spec.locale,
            max_pages=spec.max_pages,
            render_mode=spec.render_mode,
            demo=spec.demo,
        )
        if job.shop_domain is not None and not JOB_ID_RE.match(job.shop_domain) and "." not in job.shop_domain:
            raise JobError("invalid shop_domain")
        with self._lock:
            self._jobs[job.job_id] = job
            self._persist(job)
        self._pool.submit(self._execute, job.job_id)
        return job

    def get(self, job_id: str) -> DiagnosisJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, shop_domain: str | None = None, limit: int = 50) -> list[DiagnosisJob]:
        with self._lock:
            jobs = list(self._jobs.values())
        if shop_domain:
            jobs = [job for job in jobs if job.shop_domain == shop_domain]
        jobs.sort(key=lambda job: job.created_at, reverse=True)
        return jobs[: max(1, min(limit, 200))]

    def run_directory(self, job_id: str) -> Path | None:
        job = self.get(job_id)
        if job is None or job.run_id is None:
            return None
        candidate = self._runs_root / job_id / job.run_id
        return candidate if candidate.is_dir() else None

    def report_path(self, job_id: str) -> Path | None:
        run_dir = self.run_directory(job_id)
        if run_dir is None:
            return None
        report = run_dir / "report.html"
        return report if report.is_file() else None

    def artifact_path(self, job_id: str, name: str) -> Path | None:
        if name not in ALLOWED_ARTIFACTS:
            return None
        run_dir = self.run_directory(job_id)
        if run_dir is None:
            return None
        artifact = run_dir / name
        return artifact if artifact.is_file() else None

    def redact_shop(self, shop_domain: str) -> int:
        """Delete every job and run belonging to a shop (shop/redact webhook)."""
        removed = 0
        with self._lock:
            job_ids = [
                job.job_id for job in self._jobs.values() if job.shop_domain == shop_domain
            ]
            for job_id in job_ids:
                shutil.rmtree(self._runs_root / job_id, ignore_errors=True)
                record = self._jobs_dir / f"{job_id}.json"
                if record.exists():
                    record.unlink(missing_ok=True)
                self._jobs.pop(job_id, None)
                removed += 1
        return removed

    # -- internals --------------------------------------------------------

    def _execute(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status not in ("queued",):
                return
            job.status = "running"
            job.started_at = _utcnow()
            self._persist(job)
        spec = JobSpec(
            target_url=job.target_url,
            shop_domain=job.shop_domain,
            locale=job.locale,
            max_pages=job.max_pages,
            render_mode=job.render_mode,
            demo=job.demo,
        )
        try:
            result = self._invoke_engine(job_id, spec)
            self._apply_result(job_id, result)
        except Exception as exc:  # engine errors are expected (bad URLs, offline sites)
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                job.status = "failed"
                job.finished_at = _utcnow()
                job.error = f"{type(exc).__name__}: {exc}"[:500]
                self._persist(job)

    def _invoke_engine(self, job_id: str, spec: JobSpec) -> dict[str, Any]:
        runs_root = self._runs_root / job_id
        runs_root.mkdir(parents=True, exist_ok=True)
        kwargs: dict[str, Any] = {
            "locale": spec.locale,
            "max_pages": spec.max_pages,
            "render_mode": spec.render_mode,
        }
        if spec.demo:
            kwargs.update(
                render_mode="http",
                fetcher=self._fixture_fetcher,
                resolver=self._fixture_resolver,
                demo_fixture=True,
            )
            if self._clock is not None:
                kwargs["clock"] = self._clock
        elif self._clock is not None:
            kwargs["clock"] = self._clock
        return site_diagnose(spec.target_url, runs_root, **kwargs)

    def _apply_result(self, job_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "succeeded"
            job.finished_at = _utcnow()
            job.run_id = str(result.get("run_id"))
            job.run_status = str(result.get("status"))
            job.overall_score = result.get("overall_score")
            job.confidence = result.get("confidence")
            job.representative_pages = result.get("representative_pages")
            run_dir = Path(str(result.get("run_directory") or ""))
            diagnosis_file = run_dir / "site-diagnosis.json"
            if diagnosis_file.is_file():
                diagnosis = json.loads(diagnosis_file.read_text(encoding="utf-8"))
                job.dimensions = list(diagnosis.get("dimensions") or [])
                job.ai_crawlers = [
                    {
                        "agent": entry.get("agent"),
                        "role": entry.get("role"),
                        "allowed": entry.get("allowed"),
                        "basis": entry.get("basis"),
                    }
                    for entry in diagnosis.get("crawler_matrix") or []
                ]
            self._persist(job)

    def _persist(self, job: DiagnosisJob) -> None:
        record = self._jobs_dir / f"{job.job_id}.json"
        payload = json.dumps(job.to_public_dict(), ensure_ascii=False, indent=2, allow_nan=False)
        tmp = record.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(record)

    def _load_existing_jobs(self) -> None:
        for record in sorted(self._jobs_dir.glob("job-*.json")):
            try:
                data = json.loads(record.read_text(encoding="utf-8"))
                job = DiagnosisJob(
                    job_id=data["job_id"],
                    target_url=data["target_url"],
                    shop_domain=data.get("shop_domain"),
                    locale=data.get("locale", "en-US"),
                    max_pages=data.get("max_pages", 10),
                    render_mode=data.get("render_mode", "auto"),
                    demo=bool(data.get("demo", False)),
                    status=data.get("status", "failed"),
                    created_at=data.get("created_at", _utcnow()),
                    started_at=data.get("started_at"),
                    finished_at=data.get("finished_at"),
                    run_id=data.get("run_id"),
                    run_status=data.get("run_status"),
                    overall_score=data.get("overall_score"),
                    confidence=data.get("confidence"),
                    representative_pages=data.get("representative_pages"),
                    dimensions=data.get("dimensions") or [],
                    ai_crawlers=data.get("ai_crawlers") or [],
                    error=data.get("error"),
                )
                if job.status in ("queued", "running"):
                    job.status = "failed"
                    job.error = job.error or "interrupted by restart"
                self._jobs[job.job_id] = job
            except (KeyError, ValueError):
                continue

    # -- offline demo fixture ---------------------------------------------

    def _fixture_fetcher(self, url: str) -> FetchResult:
        if self._fixture_root is None:
            raise SourceUnavailable("fixture root is unavailable")
        parsed = urlsplit(url)
        if parsed.netloc != "demo.geohub.invalid":
            raise SourceUnavailable("fixture blocks off-host access")
        if parsed.path == "/robots.txt":
            path = self._fixture_root / "robots.txt"
            content_type = "text/plain; charset=utf-8"
        elif parsed.path == "/sitemap.xml":
            path = self._fixture_root / "sitemap.xml"
            content_type = "application/xml; charset=utf-8"
        else:
            manifest = json.loads(
                (self._fixture_root / "manifest.json").read_text(encoding="utf-8")
            )
            relative = manifest["pages"].get(parsed.path)
            if relative is None:
                raise SourceUnavailable(f"fixture URL is unavailable: {parsed.path}")
            path = self._fixture_root / relative
            content_type = "text/html; charset=utf-8"
        return FetchResult(final_url=url, body=path.read_bytes(), content_type=content_type)

    @staticmethod
    def _fixture_resolver(host: str, port: int, *_args: Any, **_kwargs: Any):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port))]
