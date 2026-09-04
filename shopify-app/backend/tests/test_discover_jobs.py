from __future__ import annotations

import time

from .conftest import SERVICE_KEY
from .test_jobs_api import SHOP, SHOP_HEADERS, wait_for_job

HEADERS = {"x-app-api-key": SERVICE_KEY}


def submit_discover_job(client, **overrides) -> dict:
    payload = {
        "shop_domain": SHOP.split(".")[0],
        "subject": "specialty coffee beans",
        "brand": "Demo Roasters",
        "seed_queries": [
            "what is the difference between arabica and robusta",
            "how to store coffee beans",
        ],
        "locale": "en-US",
        **overrides,
    }
    response = client.post("/api/discover-jobs", json=payload, headers=SHOP_HEADERS)
    assert response.status_code == 202, response.text
    return response.json()


def wait_for_discover(client, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/discover-jobs/{job_id}", headers=SHOP_HEADERS)
        assert response.status_code == 200
        job = response.json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.2)
    raise AssertionError("discover job did not finish in time")


def test_discover_job_end_to_end(client):
    job = submit_discover_job(client)
    assert job["kind"] == "discover"
    assert job["status"] in ("queued", "running")

    finished = wait_for_discover(client, job["job_id"])
    assert finished["status"] == "succeeded", finished.get("error")
    assert finished["query_map"], "question map is empty"
    assert finished["opportunities"], "opportunity map is empty"
    for query in finished["query_map"]:
        assert query["question"]
        assert query["intent"] in ("learn", "compare", "evaluate", "act")
    for opportunity in finished["opportunities"]:
        assert opportunity["priority"] is not None
        assert opportunity["asset_type"] in (
            "article",
            "faq",
            "comparison",
            "landing-page",
            "knowledge-entry",
        )

    # Diagnosis listing must not mix in discover runs.
    listing = client.get("/api/diagnosis-jobs", headers=SHOP_HEADERS).json()["jobs"]
    assert all(item["job_id"] != job["job_id"] for item in listing)
    discover_listing = client.get("/api/discover-jobs", headers=SHOP_HEADERS).json()["jobs"]
    assert any(item["job_id"] == job["job_id"] for item in discover_listing)

    # Artifacts are downloadable through the shared, shop-scoped proxy.
    artifact = client.get(
        f"/api/diagnosis-jobs/{job['job_id']}/artifacts/query-map.json", headers=SHOP_HEADERS
    )
    assert artifact.status_code == 200
    assert len(artifact.json()["queries"]) == len(finished["query_map"])


def test_discover_validation(client):
    cases = [
        {"subject": ""},
        {"seed_queries": []},
        {"seed_queries": ["   "]},
        {"locale": "fr-FR"},
    ]
    for overrides in cases:
        response = client.post("/api/discover-jobs", json={
            "shop_domain": SHOP,
            "subject": "coffee",
            "seed_queries": ["how to brew coffee"],
            "locale": "en-US",
            **overrides,
        }, headers={**HEADERS, "x-shop-domain": SHOP})
        assert response.status_code == 422, overrides


def test_discover_job_authorized_by_shop(client):
    job = submit_discover_job(client)
    wait_for_discover(client, job["job_id"])
    wrong = {**HEADERS, "x-shop-domain": "other-shop.myshopify.com"}
    assert client.get(f"/api/discover-jobs/{job['job_id']}", headers=wrong).status_code == 404
    assert client.get("/api/discover-jobs", headers=HEADERS).status_code == 403
