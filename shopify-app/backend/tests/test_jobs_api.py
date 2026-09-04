from __future__ import annotations

import time

from .conftest import SERVICE_KEY
from .test_security import make_token

HEADERS = {"x-app-api-key": SERVICE_KEY}
SHOP = "demo-shop.myshopify.com"
SHOP_HEADERS = {**HEADERS, "x-shop-domain": SHOP}


def wait_for_job(client, job_id: str, timeout: float = 60.0, headers: dict | None = None) -> dict:
    headers = headers or SHOP_HEADERS
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/diagnosis-jobs/{job_id}", headers=headers)
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
        "shop_domain": SHOP.split(".")[0],
        **overrides,
    }
    shop = payload.get("shop_domain") or "demo-shop"
    headers = {**HEADERS, "x-shop-domain": shop if "." in shop else f"{shop}.myshopify.com"}
    response = client.post("/api/diagnosis-jobs", json=payload, headers=headers)
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
    assert client.get("/api/diagnosis-jobs", headers=SHOP_HEADERS).status_code == 200


def test_demo_job_end_to_end(client):
    job = submit_demo_job(client)
    assert job["status"] in ("queued", "running")
    assert job["shop_domain"] == SHOP

    finished = wait_for_job(client, job["job_id"])
    assert finished["status"] == "succeeded", finished.get("error")
    assert finished["run_id"]
    assert isinstance(finished["overall_score"], int)
    assert len(finished["dimensions"]) == 8
    assert all(dimension.get("score") is not None for dimension in finished["dimensions"])
    assert all(dimension.get("weight") is not None for dimension in finished["dimensions"])
    agents = {crawler["agent"] for crawler in finished["ai_crawlers"]}
    assert {"GPTBot", "OAI-SearchBot", "Google-Extended"} <= agents

    # Insight enrichment (evidence / action / conclusion + process numbers).
    assert finished["evidence_coverage"] == "8/8"
    assert finished["inventory_count"] >= finished["representative_pages"]
    assert finished["observed_pages"] + finished["source_gaps"] == finished["representative_pages"]
    assert finished["top_action"]["title"]
    assert "observable signals" in finished["conclusion"]
    assert len(finished["pages"]) == finished["representative_pages"]
    page = finished["pages"][0]
    assert page["url"] and page["page_type"] and page["status"] in ("observed", "source_gap")

    report = client.get(f"/api/diagnosis-jobs/{job['job_id']}/report", headers=SHOP_HEADERS)
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/html")
    assert b"GEOHub" in report.content or b"report" in report.content.lower()

    artifact = client.get(
        f"/api/diagnosis-jobs/{job['job_id']}/artifacts/site-diagnosis.json", headers=SHOP_HEADERS
    )
    assert artifact.status_code == 200
    assert artifact.json()["overall_score"] == finished["overall_score"]

    forbidden = client.get(
        f"/api/diagnosis-jobs/{job['job_id']}/artifacts/run-lineage.json", headers=SHOP_HEADERS
    )
    assert forbidden.status_code == 404


def test_service_must_forward_shop_header(client):
    job = submit_demo_job(client)
    wait_for_job(client, job["job_id"])
    # No x-shop-domain: 403 for single jobs and the listing.
    assert client.get(f"/api/diagnosis-jobs/{job['job_id']}", headers=HEADERS).status_code == 403
    assert client.get("/api/diagnosis-jobs", headers=HEADERS).status_code == 403


def test_service_wrong_shop_is_404(client):
    job = submit_demo_job(client)
    wait_for_job(client, job["job_id"])
    wrong = {**HEADERS, "x-shop-domain": "other-shop.myshopify.com"}
    assert client.get(f"/api/diagnosis-jobs/{job['job_id']}", headers=wrong).status_code == 404
    assert (
        client.get(f"/api/diagnosis-jobs/{job['job_id']}/report", headers=wrong).status_code == 404
    )
    listing = client.get("/api/diagnosis-jobs", params={"shop_domain": SHOP}, headers=wrong)
    assert listing.status_code == 403


def test_session_identity_scoped_to_own_shop(client):
    job = submit_demo_job(client, shop_domain="session-shop")
    wait_for_job(client, job["job_id"], headers={**HEADERS, "x-shop-domain": "session-shop.myshopify.com"})

    own = {"authorization": f"Bearer {make_token()}"}  # session-shop token
    assert client.get(f"/api/diagnosis-jobs/{job['job_id']}", headers=own).status_code == 200
    listing = client.get("/api/diagnosis-jobs", headers=own)
    assert listing.status_code == 200
    assert all(item["shop_domain"] == "session-shop.myshopify.com" for item in listing.json()["jobs"])

    # A session for a different shop gets 404 / 403, never the data.
    other = {"authorization": f"Bearer {make_token(dest='https://evil-shop.myshopify.com', iss='https://evil-shop.myshopify.com/admin')}"}
    assert client.get(f"/api/diagnosis-jobs/{job['job_id']}", headers=other).status_code == 404
    assert client.get("/api/diagnosis-jobs", headers=other).status_code == 200
    assert client.get("/api/diagnosis-jobs", headers=other).json()["jobs"] == []


def test_job_listing_scopes_by_shop(client):
    job = submit_demo_job(client)
    wait_for_job(client, job["job_id"])

    listing = client.get("/api/diagnosis-jobs", params={"shop_domain": SHOP}, headers=SHOP_HEADERS)
    assert listing.status_code == 200
    assert any(item["job_id"] == job["job_id"] for item in listing.json()["jobs"])

    empty = client.get(
        "/api/diagnosis-jobs",
        params={"shop_domain": "other-shop.myshopify.com"},
        headers={**HEADERS, "x-shop-domain": "other-shop.myshopify.com"},
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
        response = client.post("/api/diagnosis-jobs", json=payload, headers=SHOP_HEADERS)
        assert response.status_code == 422, payload


def test_missing_job_is_404(client):
    assert (
        client.get("/api/diagnosis-jobs/job-doesnotexist", headers=SHOP_HEADERS).status_code == 404
    )
