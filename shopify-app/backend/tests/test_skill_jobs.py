from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from .conftest import SERVICE_KEY
from .test_jobs_api import SHOP, SHOP_HEADERS, submit_demo_job, wait_for_job

HEADERS = {"x-app-api-key": SERVICE_KEY}


def _wait(client, prefix: str, job_id: str, timeout: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/{prefix}/{job_id}", headers=SHOP_HEADERS)
        assert response.status_code == 200
        job = response.json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.2)
    raise AssertionError("job did not finish in time")


def _submit(client, prefix: str, payload: dict) -> dict:
    response = client.post(f"/api/{prefix}", json={**payload, "shop_domain": SHOP}, headers=SHOP_HEADERS)
    assert response.status_code == 202, response.text
    return response.json()


def _post_invalid(client, prefix: str, payload: dict) -> int:
    response = client.post(f"/api/{prefix}", json={**payload, "shop_domain": SHOP}, headers=SHOP_HEADERS)
    return response.status_code


def test_content_blueprint_job(client):
    job = _submit(
        client,
        "content-jobs",
        {
            "mode": "page-blueprint",
            "topic": "storing specialty coffee beans",
            "audience": "home brewers",
            "brand": "Demo Roasters",
        },
    )
    assert job["kind"] == "content"
    finished = _wait(client, "content-jobs", job["job_id"])
    assert finished["status"] == "succeeded", finished.get("error")
    assert finished["content_markdown"], "markdown output is missing"
    assert "#" in finished["content_markdown"]
    artifact = client.get(
        f"/api/diagnosis-jobs/{job['job_id']}/artifacts/content.md", headers=SHOP_HEADERS
    )
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("text/markdown")


def test_content_refine_requires_source(client):
    assert _post_invalid(client, "content-jobs", {"mode": "refine", "topic": "x", "source_content": ""}) == 422


def test_measure_job_metrics(client):
    job = _submit(
        client,
        "measure-jobs",
        {
            "subject": "Demo Roasters",
            "engine": "chatgpt",
            "observations": [
                {"query_id": "q-1", "answered": True, "cited": True},
                {"query_id": "q-2", "answered": True, "cited": False},
                {"query_id": "q-3", "answered": False, "cited": None},
                {"query_id": "q-4", "answered": True, "cited": True},
            ],
        },
    )
    finished = _wait(client, "measure-jobs", job["job_id"])
    assert finished["status"] == "succeeded", finished.get("error")
    metrics = finished["metrics"]
    assert metrics["answer_coverage"] is not None
    assert metrics["mention_rate"] is not None
    assert 0 <= metrics["answer_coverage"] <= 1


def test_knowledge_requires_diagnosis_first(client):
    response = client.post(
        "/api/knowledge-jobs",
        json={"shop_domain": "fresh-shop.myshopify.com", "brand": "Fresh"},
        headers={**HEADERS, "x-shop-domain": "fresh-shop.myshopify.com"},
    )
    # Accepted but should fail in execution with a clear reason.
    assert response.status_code == 202
    fresh_headers = {**HEADERS, "x-shop-domain": "fresh-shop.myshopify.com"}
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        job = client.get(
            f"/api/knowledge-jobs/{response.json()['job_id']}", headers=fresh_headers
        ).json()
        if job["status"] not in ("queued", "running"):
            break
        time.sleep(0.2)
    assert job["status"] == "failed"
    assert "diagnosis" in (job["error"] or "")


def test_knowledge_brand_facts_after_diagnosis(client):
    diagnosis = submit_demo_job(client)
    wait_for_job(client, diagnosis["job_id"])

    job = _submit(client, "knowledge-jobs", {"brand": "Demo Roasters"})
    finished = _wait(client, "knowledge-jobs", job["job_id"])
    assert finished["status"] == "succeeded", finished.get("error")
    assert finished["brand_facts"], "brand facts are empty"
    attributes = {fact["attribute"] for fact in finished["brand_facts"]}
    assert "page_role" in attributes


def test_compare_job_with_fixture_sources(client):
    job = _submit(
        client,
        "compare-jobs",
        {
            "my_url": "https://demo.geohub.invalid/",
            "competitor_urls": [
                "https://demo.geohub.invalid/about",
                "https://demo.geohub.invalid/product/atlas",
            ],
        },
    )
    finished = _wait(client, "compare-jobs", job["job_id"])
    assert finished["status"] == "succeeded", finished.get("error")
    assert len(finished["comparison"]) == 3
    urls = {entry["url"] for entry in finished["comparison"]}
    assert urls == {
        "https://demo.geohub.invalid/",
        "https://demo.geohub.invalid/about",
        "https://demo.geohub.invalid/product/atlas",
    }


def test_compare_validates_urls(client):
    assert _post_invalid(
        client, "compare-jobs", {"my_url": "not-a-url", "competitor_urls": ["https://ok.example/"]}
    ) == 422


def test_retention_sweep_moves_expired_jobs(client, tmp_path):
    job = submit_demo_job(client)
    wait_for_job(client, job["job_id"])

    manager = client.app.state.job_manager
    preview = manager.retention_sweep(confirm=False)
    assert preview["run_count"] == 0  # fresh job is not expired

    future = datetime.now(timezone.utc) + timedelta(days=45)
    preview = manager.retention_sweep(confirm=False, now=future)
    assert preview["run_count"] >= 1
    assert any(entry["job_id"] == job["job_id"] for entry in preview["expired_jobs"])

    applied = manager.retention_sweep(confirm=True, now=future)
    assert applied["run_count"] >= 1
    assert manager.get(job["job_id"]) is None
    assert (
        client.get(f"/api/diagnosis-jobs/{job['job_id']}", headers=SHOP_HEADERS).status_code
        == 404
    )


def test_retention_endpoints_require_service_auth(client):
    # Session identity cannot trigger retention.
    from .test_security import make_token

    headers = {"authorization": f"Bearer {make_token()}"}
    assert client.get("/api/retention", headers=headers).status_code == 403
    assert client.post("/api/retention/apply", headers=headers).status_code == 403
    # Service identity can preview.
    assert client.get("/api/retention", headers=HEADERS).status_code == 200
