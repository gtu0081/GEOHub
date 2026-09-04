from __future__ import annotations

import hashlib
import json
import shutil
import socket
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from geo_seo_hub.content import content as geo_content
from geo_seo_hub.diagnose import FetchResult, SourceUnavailable, diagnose as geo_diagnose
from geo_seo_hub.discover import discover as geo_discover
from geo_seo_hub.knowledge import knowledge as geo_knowledge
from geo_seo_hub.measure import measure as geo_measure
from geo_seo_hub.site_diagnose import site_diagnose

JOB_KINDS = ("diagnosis", "discover", "content", "measure", "knowledge", "compare")
LOCALES = ("zh-CN", "en-US")
RENDER_MODES = ("auto", "http", "browser")
CONTENT_MODES = ("page-blueprint", "explainer", "refine")
MAX_PAGES_LIMIT = 10
MEASURE_ENGINES = ("chatgpt", "perplexity", "gemini", "copilot", "other")
# Artifacts the API may serve next to report.html.
ALLOWED_ARTIFACTS = (
    "site-diagnosis.json",
    "remediation-backlog.json",
    "sampling-plan.json",
    "crawl-manifest.json",
    "quality-report.json",
    "run-manifest.json",
    "query-map.json",
    "opportunity-map.json",
    "content-spec.json",
    "content.md",
    "measurement-report.json",
    "knowledge-graph.json",
    "diagnosis.json",
)


class JobError(ValueError):
    """Raised for invalid job submissions."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class JobSpec:
    target_url: str = ""
    shop_domain: str | None = None
    locale: str = "en-US"
    max_pages: int = 10
    render_mode: str = "auto"
    demo: bool = False
    kind: str = "diagnosis"  # diagnosis | discover | content | measure | knowledge | compare
    subject: str = ""
    brand: str = ""
    seed_queries: tuple[str, ...] = ()
    # content / measure / compare inputs
    mode: str = ""
    topic: str = ""
    audience: str = ""
    source_content: str = ""
    engine: str = ""
    my_url: str = ""
    competitor_urls: tuple[str, ...] = ()
    observations: tuple[dict[str, Any], ...] = ()

    def validate(self) -> None:
        if self.kind not in JOB_KINDS:
            raise JobError(f"kind must be one of {JOB_KINDS}")
        if self.locale not in LOCALES:
            raise JobError(f"locale must be one of {LOCALES}")
        if self.kind == "discover":
            if not self.subject.strip():
                raise JobError("subject is required for discover jobs")
            if not self.seed_queries:
                raise JobError("seed_queries must contain at least one question")
            return
        if self.kind == "content":
            if self.mode not in CONTENT_MODES:
                raise JobError(f"content mode must be one of {CONTENT_MODES}")
            if not self.topic.strip():
                raise JobError("topic is required for content jobs")
            if self.mode == "refine" and not self.source_content.strip():
                raise JobError("refine mode requires source_content")
            return
        if self.kind == "measure":
            if self.engine not in MEASURE_ENGINES:
                raise JobError(f"engine must be one of {MEASURE_ENGINES}")
            if not self.observations:
                raise JobError("at least one observation is required")
            for index, observation in enumerate(self.observations):
                if not observation.get("query_id", "").strip():
                    raise JobError(f"observations[{index}].query_id is required")
                if "cited" not in observation:
                    raise JobError(f"observations[{index}].cited is required")
            return
        if self.kind == "knowledge":
            if not self.shop_domain:
                raise JobError("knowledge jobs require a shop-scoped diagnosis first")
            return  # sources are derived from the shop's latest diagnosis
        if self.kind == "compare":
            parsed = urlsplit(self.my_url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise JobError("my_url must be an absolute http(s) URL")
            if not self.competitor_urls:
                raise JobError("at least one competitor URL is required")
            if 1 + len(self.competitor_urls) > 5:
                raise JobError("compare accepts at most 4 competitor URLs")
            normalized: list[str] = []
            for url in (self.my_url, *self.competitor_urls):
                candidate = urlsplit(url)
                if candidate.scheme not in ("http", "https") or not candidate.hostname:
                    raise JobError(f"invalid URL in compare sources: {url!r}")
                key = f"{candidate.scheme}://{candidate.netloc.lower()}{candidate.path.rstrip('/')}"
                if key in normalized:
                    raise JobError("compare sources must be unique URLs")
                normalized.append(key)
            return
        # diagnosis
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
    # Process transparency (from sampling plan + page records).
    inventory_count: int | None = None
    observed_pages: int | None = None
    source_gaps: int | None = None
    # Evidence / priority action / conclusion callouts.
    evidence_coverage: str | None = None
    top_action: dict[str, Any] | None = None
    conclusion: str | None = None
    # Per-page drilldown summaries.
    pages: list[dict[str, Any]] = field(default_factory=list)
    # Discover jobs (question maps).
    kind: str = "diagnosis"
    subject: str | None = None
    brand: str | None = None
    query_map: list[dict[str, Any]] = field(default_factory=list)
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    # Content jobs.
    content_title: str | None = None
    content_markdown: str | None = None
    # Measure jobs.
    metrics: dict[str, Any] | None = None
    # Knowledge jobs (brand facts).
    brand_facts: list[dict[str, Any]] = field(default_factory=list)
    fact_conflicts: list[dict[str, Any]] = field(default_factory=list)
    # Compare jobs (competitor benchmark).
    comparison: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["report_url"] = (
            f"/api/diagnosis-jobs/{self.job_id}/report"
            if self.status == "succeeded" and self.kind == "diagnosis"
            else None
        )
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
        self._specs: dict[str, JobSpec] = {}
        self._deleted: set[str] = set()  # tombstones for redacted/retired jobs
        self._stop_event: threading.Event | None = None
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="geohub-job")
        self._clock = clock
        self._jobs_dir = self._data_root / "jobs"
        self._runs_root = self._data_root / "runs"
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._runs_root.mkdir(parents=True, exist_ok=True)
        self._load_existing_jobs()
        self._start_retention_sweeper()

    def shutdown(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        self._pool.shutdown(wait=False)

    # -- public API -------------------------------------------------------

    def submit(self, spec: JobSpec) -> DiagnosisJob:
        spec.validate()
        if spec.demo and self._fixture_root is None:
            raise JobError("demo jobs require the offline fixture bundle (GEOHUB_FIXTURE_ROOT)")
        shop_domain = spec.shop_domain
        if shop_domain:
            shop_domain = shop_domain.strip().lower()
            if "." not in shop_domain:
                shop_domain = f"{shop_domain}.myshopify.com"
        job = DiagnosisJob(
            job_id=f"job-{uuid.uuid4().hex[:12]}",
            target_url=spec.target_url,
            shop_domain=shop_domain,
            locale=spec.locale,
            max_pages=spec.max_pages,
            render_mode=spec.render_mode,
            demo=spec.demo,
            kind=spec.kind,
            subject=spec.subject or spec.topic or spec.my_url or None,
            brand=spec.brand or None,
        )
        with self._lock:
            self._jobs[job.job_id] = job
            self._specs[job.job_id] = spec
            self._persist(job)
        self._pool.submit(self._execute, job.job_id)
        return job

    def get(self, job_id: str) -> DiagnosisJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(
        self,
        shop_domain: str | None = None,
        limit: int = 50,
        kind: str | None = None,
    ) -> list[DiagnosisJob]:
        with self._lock:
            jobs = list(self._jobs.values())
        if shop_domain:
            jobs = [job for job in jobs if job.shop_domain == shop_domain]
        if kind:
            jobs = [job for job in jobs if job.kind == kind]
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
                self._specs.pop(job_id, None)
                self._jobs.pop(job_id, None)
                self._deleted.add(job_id)  # block late writes from running engines
                removed += 1
        return removed

    # -- retention (geo_seo_hub.data_retention, L2 = 30 days default) --------

    def retention_sweep(self, *, confirm: bool = False, now=None) -> dict[str, Any]:
        """Apply the library retention policy to every job's run directory.

        Expired runs move into ``<job_id>/.geohub-trash`` (recoverable); the
        job records themselves are dropped once their runs are trashed.
        """
        from geo_seo_hub.data_retention import apply_retention_policy

        with self._lock:
            job_ids = [job_id for job_id in self._jobs]
        expired = []
        for job_id in job_ids:
            job_dir = self._runs_root / job_id
            if not job_dir.is_dir():
                continue
            try:
                result = apply_retention_policy(job_dir, now=now, confirm=confirm)
            except (OSError, ValueError):
                continue
            targets = result.get("targets") or []
            if targets:
                expired.append({"job_id": job_id, "runs": targets})
        summary = {
            "status": "moved-to-trash" if confirm and expired else "dry-run",
            "expired_jobs": expired,
            "run_count": sum(len(entry["runs"]) for entry in expired),
        }
        if confirm and expired:
            with self._lock:
                for entry in expired:
                    job_id = entry["job_id"]
                    record = self._jobs_dir / f"{job_id}.json"
                    if record.exists():
                        record.unlink(missing_ok=True)
                    self._specs.pop(job_id, None)
                    self._jobs.pop(job_id, None)
                    self._deleted.add(job_id)
            # Remove the whole job directory: submitted briefs (merchant data)
            # and the trashed runs must not outlive the retention window.
            for entry in expired:
                shutil.rmtree(self._runs_root / entry["job_id"], ignore_errors=True)
        return summary

    def _start_retention_sweeper(self) -> None:
        stop = threading.Event()
        self._stop_event = stop

        def _loop() -> None:
            stop.wait(3600)  # first sweep after an hour, then daily
            while not stop.is_set():
                try:
                    self.retention_sweep(confirm=True)
                except Exception:
                    pass
                stop.wait(24 * 3600)

        thread = threading.Thread(target=_loop, name="geohub-retention", daemon=True)
        thread.start()

    # -- internals --------------------------------------------------------

    def _clock_kw(self) -> dict[str, Any]:
        return {"clock": self._clock} if self._clock is not None else {}

    def _write_json_input(self, runs_root: Path, name: str, payload: dict[str, Any]) -> Path:
        path = runs_root / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        return path

    def _discover_brief(self, spec: JobSpec) -> dict[str, Any]:
        return {
            "protocol_version": "1.0.0",
            "brief_id": f"brief-{uuid.uuid4().hex[:12]}",
            "subject": spec.subject.strip(),
            "brand": spec.brand.strip() or None,
            "locale": spec.locale,
            "seed_queries": list(spec.seed_queries),
        }

    def _observation(self, *, engine: str, **raw: Any) -> dict[str, Any]:
        """Normalize one merchant-submitted sighting into a schema-valid trial."""
        answered = bool(raw.get("answered", False))
        cited_raw = raw.get("cited")
        # Schema: cited is a boolean when answered, null otherwise.
        if answered:
            cited = bool(cited_raw) if cited_raw is not None else False
        else:
            cited = None
        return {
            "trial_id": f"trial-{uuid.uuid4().hex[:12]}",
            "query_id": str(raw.get("query_id", "")).strip() or f"q-{uuid.uuid4().hex[:8]}",
            "engine": engine,
            "interface": str(raw.get("interface", "web")),
            "language": str(raw.get("language", "en")),
            "geography": str(raw.get("geography", "global")),
            "collected_at": str(raw.get("collected_at") or _utcnow()),
            "model_version": str(raw.get("model_version", "unreported")),
            "sample_unit": str(raw.get("sample_unit", "assistant-answer")),
            "eligible": True,
            "answered": answered,
            "cited": cited,
            "missing_answer_reason": None if answered else "assistant declined or failed to answer",
            "exclusion_reason": None,
            "source_uri": str(
                raw.get("source_uri") or f"https://{engine}.example/answer/{uuid.uuid4().hex[:8]}"
            ),
        }

    def _knowledge_request(self, spec: JobSpec) -> dict[str, Any]:
        """Derive brand-fact sources from the shop's latest completed diagnosis."""
        if spec.shop_domain is None:
            raise JobError("knowledge jobs require a shop-scoped diagnosis first")
        with self._lock:
            candidates = [
                job
                for job in self._jobs.values()
                if job.shop_domain == spec.shop_domain
                and job.kind == "diagnosis"
                and job.status == "succeeded"
                and job.run_id
            ]
        if not candidates:
            raise JobError("run a site diagnosis before building the brand fact card")
        latest = max(candidates, key=lambda job: job.created_at)
        run_dir = self._runs_root / latest.job_id / (latest.run_id or "")
        diagnosis_file = run_dir / "site-diagnosis.json"
        if not diagnosis_file.is_file():
            raise JobError("the latest diagnosis run is missing its artifacts")
        diagnosis = json.loads(diagnosis_file.read_text(encoding="utf-8"))
        brand_name = spec.brand.strip() or spec.shop_domain.split(".")[0]
        reviewed_at = _utcnow()
        valid_from = reviewed_at.split("T")[0]  # knowledge dates are plain dates
        sources = []
        for page in diagnosis.get("pages") or []:
            if page.get("status") != "observed":
                continue
            url = str(page.get("url") or spec.shop_domain)
            digest = str(page.get("content_sha256") or "")
            if len(digest) != 64:
                digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
            entity_id = f"{page.get('page_id')}-org"
            metrics = page.get("metrics") or {}
            facts = [
                {
                    "entity_id": entity_id,
                    "attribute": "page_role",
                    "value": str(page.get("page_type_label") or page.get("page_type") or "page"),
                    "valid_from": valid_from,
                }
            ]
            description = str(metrics.get("meta_description") or "").strip()
            if description:
                facts.append(
                    {
                        "entity_id": entity_id,
                        "attribute": "meta_description",
                        "value": description[:300],
                        "valid_from": valid_from,
                    }
                )
            sources.append(
                {
                    "source_id": f"src-{page.get('page_id')}",
                    "source_uri": url,
                    "source_hash": digest,
                    "reviewed_at": reviewed_at,
                    "entities": [
                        {
                            "entity_id": entity_id,
                            "type": "Organization",
                            "canonical_name": brand_name,
                            "aliases": [],
                            "valid_from": valid_from,
                        }
                    ],
                    "facts": facts,
                    "relations": [],
                }
            )
        if not sources:
            raise JobError("the latest diagnosis has no observed pages to build facts from")
        return {
            "protocol_version": "1.0.0",
            "subject": spec.shop_domain,
            "query": {"mode": "global", "value": brand_name},
            "sources": sources,
        }

    def _execute(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            spec = self._specs.get(job_id)
            if job is None or spec is None or job.status not in ("queued",):
                return
            job.status = "running"
            job.started_at = _utcnow()
            self._persist(job)
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
        if spec.kind == "discover":
            brief_path = self._write_json_input(
                runs_root, "geo-brief.json", self._discover_brief(spec)
            )
            return geo_discover(brief_path, runs_root, execution_mode="deterministic", **self._clock_kw())
        if spec.kind == "content":
            brief = {
                "mode": spec.mode,
                "topic": spec.topic.strip(),
                "audience": spec.audience.strip() or "general shoppers",
                "target_brand": spec.brand.strip() or "the store",
                "competitors": [],
                "entities": [],
                "evidence": [],
                "desired_formats": ["markdown", "json"],
                "locale": spec.locale,
            }
            if spec.mode == "refine":
                brief["source_content"] = spec.source_content
            brief_path = self._write_json_input(runs_root, "content-brief.json", brief)
            return geo_content(brief_path, runs_root, execution_mode="legacy", **self._clock_kw())
        if spec.kind == "measure":
            batch_time = _utcnow()
            brief = {
                "protocol_version": "1.0.0",
                "measurement_id": f"measurement-{uuid.uuid4().hex[:12]}",
                "subject": spec.subject.strip() or spec.brand.strip() or "store",
                "study_design": {"kind": "observational", "intervention": None, "comparator": None},
                "confidence_level": 0.9,
                "inclusion_criteria": ["query belongs to the tracked question map"],
                "exclusion_criteria": ["answer could not be loaded"],
                "observations": [
                    self._observation(engine=spec.engine, **{**observation, "collected_at": batch_time})
                    for observation in spec.observations
                ],
            }
            brief_path = self._write_json_input(runs_root, "measurement-brief.json", brief)
            return geo_measure(brief_path, runs_root, **self._clock_kw())
        if spec.kind == "knowledge":
            request = self._knowledge_request(spec)
            brief_path = self._write_json_input(runs_root, "knowledge-request.json", request)
            return geo_knowledge(brief_path, runs_root, **self._clock_kw())
        if spec.kind == "compare":
            brief = {
                "subject": spec.my_url,
                "scope": "page",
                "target_urls": [spec.my_url, *spec.competitor_urls],
            }
            brief_path = self._write_json_input(runs_root, "diagnosis-brief.json", brief)
            kwargs: dict[str, Any] = {}
            if self._fixture_root is not None:
                # Offline fixture mode (tests): serve only demo.geohub.invalid.
                kwargs["fetcher"] = self._fixture_fetcher
                kwargs["resolver"] = self._fixture_resolver
            if self._clock is not None:
                kwargs["clock"] = self._clock
            return geo_diagnose(brief_path, runs_root, **kwargs)
        kwargs = {
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
                # Deleted while running (redact/retention race): drop what the
                # engine just wrote so shop data cannot resurrect on disk.
                if job_id in self._deleted:
                    shutil.rmtree(self._runs_root / job_id, ignore_errors=True)
                return
            job.status = "succeeded"
            job.finished_at = _utcnow()
            job.run_id = str(result.get("run_id"))
            job.run_status = str(result.get("status"))
            job.overall_score = result.get("overall_score")
            job.confidence = result.get("confidence")
            job.representative_pages = result.get("representative_pages")
            run_dir = Path(str(result.get("run_directory") or result.get("output") or ""))
            if job.kind == "discover":
                self._apply_discover_result(job, run_dir)
                self._persist(job)
                return
            if job.kind == "content":
                self._apply_content_result(job, run_dir)
                self._persist(job)
                return
            if job.kind == "measure":
                self._apply_measure_result(job, run_dir)
                self._persist(job)
                return
            if job.kind == "knowledge":
                self._apply_knowledge_result(job, run_dir)
                self._persist(job)
                return
            if job.kind == "compare":
                self._apply_compare_result(job, run_dir)
                self._persist(job)
                return
            diagnosis_file = run_dir / "site-diagnosis.json"
            if not diagnosis_file.is_file():
                self._persist(job)
                return
            diagnosis = json.loads(diagnosis_file.read_text(encoding="utf-8"))
            weights = diagnosis.get("dimension_weights") or {}
            raw_dimensions = diagnosis.get("dimensions") or {}
            if isinstance(raw_dimensions, dict):
                job.dimensions = [
                    {"key": key, "score": score, "weight": weights.get(key)}
                    for key, score in raw_dimensions.items()
                ]
            else:
                job.dimensions = list(raw_dimensions)
            job.ai_crawlers = [
                {
                    "agent": entry.get("agent"),
                    "role": entry.get("role"),
                    "allowed": entry.get("allowed"),
                    "basis": entry.get("basis"),
                }
                for entry in diagnosis.get("crawler_matrix") or []
            ]
            self._apply_page_insights(job, run_dir, diagnosis)
            self._persist(job)

    def _apply_discover_result(self, job: DiagnosisJob, run_dir: Path) -> None:
        query_file = run_dir / "query-map.json"
        if query_file.is_file():
            query_map = json.loads(query_file.read_text(encoding="utf-8"))
            job.query_map = [
                {
                    "query_id": item.get("query_id"),
                    "question": item.get("question"),
                    "intent": item.get("intent"),
                    "audience": item.get("audience"),
                    "scenario": item.get("scenario"),
                    "rewrites": list((item.get("rewrites") or {}).values()) if isinstance(item.get("rewrites"), dict) else list(item.get("rewrites") or []),
                    "evidence_status": item.get("evidence_status"),
                }
                for item in query_map.get("queries") or []
            ]
        opportunity_file = run_dir / "opportunity-map.json"
        if opportunity_file.is_file():
            opportunity_map = json.loads(opportunity_file.read_text(encoding="utf-8"))
            job.opportunities = [
                {
                    "opportunity_id": item.get("opportunity_id"),
                    "query_ids": list(item.get("query_ids") or []),
                    "asset_type": item.get("asset_type"),
                    "priority": item.get("priority"),
                    "rationale": item.get("rationale"),
                    "evidence_status": item.get("evidence_status"),
                }
                for item in opportunity_map.get("opportunities") or []
            ]

    def _apply_content_result(self, job: DiagnosisJob, run_dir: Path) -> None:
        spec_file = run_dir / "content-spec.json"
        if spec_file.is_file():
            spec = json.loads(spec_file.read_text(encoding="utf-8"))
            job.content_title = spec.get("title")
        markdown = run_dir / "content.md"
        if markdown.is_file():
            job.content_markdown = markdown.read_text(encoding="utf-8")[:200000]

    def _apply_measure_result(self, job: DiagnosisJob, run_dir: Path) -> None:
        report_file = run_dir / "visibility-report.json"
        if not report_file.is_file():
            return
        report = json.loads(report_file.read_text(encoding="utf-8"))
        metrics = report.get("metrics") or {}
        job.metrics = {
            name: (metrics[name] or {}).get("value")
            if isinstance(metrics[name], dict)
            else metrics[name]
            for name in (
                "mention_rate",
                "citation_share",
                "answer_coverage",
                "source_inclusion_rate",
                "observation_coverage",
            )
            if name in metrics
        }

    def _apply_knowledge_result(self, job: DiagnosisJob, run_dir: Path) -> None:
        graph_file = run_dir / "knowledge-graph.json"
        if not graph_file.is_file():
            return
        graph = json.loads(graph_file.read_text(encoding="utf-8"))
        job.brand_facts = [
            {
                "entity": entity.get("canonical_name"),
                "attribute": fact.get("attribute"),
                "value": fact.get("value"),
                "sources": len(fact.get("source_ids") or []),
            }
            for entity in graph.get("entities") or []
            for fact in entity.get("facts") or []
        ][:40]
        job.fact_conflicts = [
            conflict if isinstance(conflict, dict) else {"detail": str(conflict)}
            for conflict in graph.get("conflicts") or []
        ][:20]

    def _apply_compare_result(self, job: DiagnosisJob, run_dir: Path) -> None:
        diagnosis_file = run_dir / "diagnosis.json"
        if not diagnosis_file.is_file():
            return
        diagnosis = json.loads(diagnosis_file.read_text(encoding="utf-8"))
        findings_by_source: dict[str, list[dict[str, Any]]] = {}
        for finding in diagnosis.get("findings") or []:
            statement = str(finding.get("statement") or "")
            prefix = statement.split(":", 1)[0] if ":" in statement else ""
            findings_by_source.setdefault(prefix, []).append(finding)
        comparison: list[dict[str, Any]] = []
        for entry in diagnosis.get("source_status") or []:
            observations = entry.get("observations") or {}
            source_id = str(entry.get("source_id") or "")
            own_findings = findings_by_source.get(source_id, [])
            comparison.append(
                {
                    "url": entry.get("source_uri"),
                    "status": entry.get("status"),
                    "metrics": {
                        "h1": observations.get("h1") or [],
                        "h2_count": len(observations.get("h2") or []),
                        "external_link_count": observations.get("external_link_count"),
                        "faq_like_count": observations.get("faq_like_count"),
                        "json_ld_count": observations.get("json_ld_count"),
                        "meta_description": observations.get("meta_description"),
                        "canonical": observations.get("canonical"),
                    },
                    "findings": {
                        "total": len(own_findings),
                        "warning": sum(
                            1 for item in own_findings if item.get("severity") in ("warning", "high", "critical")
                        ),
                    },
                }
            )
        job.comparison = comparison[:10]
        job.metrics = diagnosis.get("scores") or None

    def _apply_page_insights(
        self, job: DiagnosisJob, run_dir: Path, diagnosis: dict[str, Any]
    ) -> None:
        pages = [page for page in diagnosis.get("pages") or [] if isinstance(page, dict)]
        observed = [page for page in pages if page.get("status") == "observed"]
        job.observed_pages = len(observed)
        job.source_gaps = len(pages) - len(observed)
        job.pages = [_page_summary(page) for page in pages]
        scored = [
            dimension for dimension in job.dimensions if dimension.get("score") is not None
        ]
        job.evidence_coverage = f"{len(scored)}/{len(job.dimensions) or 8}"

        sampling_file = run_dir / "sampling-plan.json"
        if sampling_file.is_file():
            sampling = json.loads(sampling_file.read_text(encoding="utf-8"))
            job.inventory_count = sampling.get("inventory_count")

        backlog_file = run_dir / "remediation-backlog.json"
        if backlog_file.is_file():
            backlog = json.loads(backlog_file.read_text(encoding="utf-8"))
            actions = sorted(
                backlog.get("actions") or [], key=lambda item: -(item.get("priority") or 0)
            )
            if actions:
                top = actions[0]
                job.top_action = {
                    "title": top.get("title"),
                    "severity": top.get("severity"),
                    "impact": top.get("impact"),
                    "effort": top.get("effort"),
                    "affected_pages": len(top.get("affected_page_ids") or []),
                }
        job.conclusion = _conclusion(job, diagnosis)

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
                    inventory_count=data.get("inventory_count"),
                    observed_pages=data.get("observed_pages"),
                    source_gaps=data.get("source_gaps"),
                    evidence_coverage=data.get("evidence_coverage"),
                    top_action=data.get("top_action"),
                    conclusion=data.get("conclusion"),
                    pages=data.get("pages") or [],
                    kind=data.get("kind", "diagnosis"),
                    subject=data.get("subject"),
                    brand=data.get("brand"),
                    query_map=data.get("query_map") or [],
                    opportunities=data.get("opportunities") or [],
                    content_title=data.get("content_title"),
                    content_markdown=data.get("content_markdown"),
                    metrics=data.get("metrics"),
                    brand_facts=data.get("brand_facts") or [],
                    fact_conflicts=data.get("fact_conflicts") or [],
                    comparison=data.get("comparison") or [],
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


def _page_summary(page: dict[str, Any]) -> dict[str, Any]:
    """Flatten one engine page record into the API's drilldown payload."""
    metrics = page.get("metrics") or {}
    selection = page.get("selection") or {}
    issues = [
        {
            "check_id": issue.get("check_id"),
            "dimension": issue.get("dimension"),
            "severity": issue.get("severity"),
            "statement": issue.get("statement"),
            "recommendation": issue.get("recommendation"),
        }
        for issue in (page.get("issues") or [])
        if isinstance(issue, dict)
    ][:5]
    return {
        "page_id": page.get("page_id"),
        "url": page.get("url"),
        "page_type": page.get("page_type"),
        "page_type_label": page.get("page_type_label"),
        "status": page.get("status"),
        "score": page.get("score"),
        "representativeness": selection.get("representativeness"),
        "issues": issues,
        "issue_count": len(page.get("issues") or []),
        "metrics": {
            "h2_count": metrics.get("h2_count"),
            "external_link_count": metrics.get("external_link_count"),
            "faq_like_count": metrics.get("faq_like_count"),
            "schema_types": metrics.get("schema_types") or [],
        },
    }


def _conclusion(job: DiagnosisJob, diagnosis: dict[str, Any]) -> str:
    """One honest sentence about what this run does and does not show."""
    parts: list[str] = []
    if job.source_gaps:
        parts.append(
            f"{job.source_gaps} of {len(job.pages)} selected pages could not be fully fetched, so their signals are marked as gaps rather than guessed"
        )
    weakest = None
    for dimension in job.dimensions:
        score = dimension.get("score")
        if score is not None and (weakest is None or score < weakest[1]):
            weakest = (dimension.get("key"), score)
    if weakest and weakest[1] < 60:
        parts.append(f"the weakest dimension is {weakest[0].replace('_', ' ')} ({weakest[1]}/100)")
    if not parts:
        parts.append("every selected page was observed and no dimension scored below 60")
    return (
        f"Scores describe observable signals in this snapshot only — {', '.join(parts)}; "
        "no live AI rankings, citations, or traffic are estimated."
    )
