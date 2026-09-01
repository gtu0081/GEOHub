from __future__ import annotations

import time

from .conftest import SERVICE_KEY

HEADERS = {"x-app-api-key": SERVICE_KEY}


def wait_for_job(client, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/diagnosis-jobs/{job_id}", headers=HEADERS)
        assert response.status_code == 200
        job = response.json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.2)
    raise AssertionError("job did not finish in time")


def submit_demo_job(client, **overrides) -> dict:
    payload = {
        "target_url": "https://demo.geohub.invalid/",
        "locale": "en-US",
        "max_pages": 10,
        "render_mode": "auto",
        "demo": True,
        "shop_domain": "demo-shop",
        **overrides,
    }
    response = client.post("/api/diagnosis-jobs", json=payload, headers=HEADERS)
    assert response.status_code == 202, response.text
    return response.json()


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["dev_mode"] is False


def test_requires_auth(client):
    assert client.get("/api/diagnosis-jobs").status_code == 401
    assert client.get("/api/diagnosis-jobs", headers=HEADERS).status_code == 200


def test_demo_job_end_to_end(client):
    job = submit_demo_job(client)
    assert job["status"] in ("queued", "running")
    assert job["shop_domain"] == "demo-shop.myshopify.com"

    finished = wait_for_job(client, job["job_id"])
    assert finished["status"] == "succeeded", finished.get("error")
    assert finished["run_id"]
    assert isinstance(finished["overall_score"], int)
    assert len(finished["dimensions"]) == 8
    agents = {crawler["agent"] for crawler in finished["ai_crawlers"]}
    assert {"GPTBot", "OAI-SearchBot", "Google-Extended"} <= agents

    report = client.get(f"/api/diagnosis-jobs/{job['job_id']}/report", headers=HEADERS)
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/html")
    assert b"GEOHub" in report.content or b"report" in report.content.lower()

    artifact = client.get(
        f"/api/diagnosis-jobs/{job['job_id']}/artifacts/site-diagnosis.json", headers=HEADERS
    )
    assert artifact.status_code == 200
    assert artifact.json()["overall_score"] == finished["overall_score"]

    forbidden = client.get(
        f"/api/diagnosis-jobs/{job['job_id']}/artifacts/run-lineage.json", headers=HEADERS
    )
    assert forbidden.status_code == 404


def test_job_listing_scopes_by_shop(client):
    job = submit_demo_job(client)
    wait_for_job(client, job["job_id"])

    listing = client.get(
        "/api/diagnosis-jobs", params={"shop_domain": "demo-shop.myshopify.com"}, headers=HEADERS
    )
    assert listing.status_code == 200
    assert any(item["job_id"] == job["job_id"] for item in listing.json()["jobs"])

    empty = client.get(
        "/api/diagnosis-jobs", params={"shop_domain": "other-shop.myshopify.com"}, headers=HEADERS
    )
    assert empty.json()["jobs"] == []


def test_invalid_submissions_are_rejected(client):
    cases = [
        {"target_url": "not-a-url", "demo": True},
        {"target_url": "ftp://demo.geohub.invalid/", "demo": True},
        {"target_url": "https://demo.geohub.invalid/", "max_pages": 11, "demo": True},
        {"target_url": "https://demo.geohub.invalid/", "render_mode": "puppet", "demo": True},
        {"target_url": "https://demo.geohub.invalid/", "locale": "fr-FR", "demo": True},
    ]
    for payload in cases:
        response = client.post("/api/diagnosis-jobs", json=payload, headers=HEADERS)
        assert response.status_code == 422, payload


def test_missing_job_is_404(client):
    assert client.get("/api/diagnosis-jobs/job-doesnotexist", headers=HEADERS).status_code == 404
