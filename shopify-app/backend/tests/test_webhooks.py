from __future__ import annotations

import base64
import hashlib
import hmac
import json

from .conftest import API_SECRET, SERVICE_KEY
from .test_jobs_api import submit_demo_job, wait_for_job

HEADERS = {"x-app-api-key": SERVICE_KEY}
SHOP = "redact-shop.myshopify.com"

PAYLOAD = {
    "shop": SHOP,
    "shop_domain": SHOP,
    "customer": {"id": 1, "email": "customer@example.com"},
}


def webhook_post(
    client,
    path: str,
    *,
    topic: str,
    shop: str = SHOP,
    payload: dict | None = None,
    secret: str = API_SECRET,
):
    """POST exactly the bytes the HMAC was computed over (as Shopify does)."""
    raw = json.dumps(payload or PAYLOAD).encode("utf-8")
    digest = base64.b64encode(
        hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()
    ).decode("ascii")
    headers = {
        "content-type": "application/json",
        "x-shopify-topic": topic,
        "x-shopify-shop-domain": shop,
        "x-shopify-hmac-sha256": digest,
    }
    return client.post(path, content=raw, headers=headers)


def test_customers_webhooks_accept_valid_hmac(client):
    for topic, path in (
        ("customers/data_request", "/webhooks/customers_data_request"),
        ("customers/redact", "/webhooks/customers_redact"),
    ):
        response = webhook_post(client, path, topic=topic)
        assert response.status_code == 200, response.text
        assert response.json() == {"ok": True, "shop": SHOP, "removed_jobs": 0}


def test_webhook_rejects_invalid_hmac(client):
    response = webhook_post(client, "/webhooks/customers_redact", topic="customers/redact", secret="wrong")
    assert response.status_code == 401


def test_webhook_rejects_topic_mismatch(client):
    response = webhook_post(client, "/webhooks/customers_data_request", topic="customers/redact")
    assert response.status_code == 400


def test_webhook_rejects_invalid_shop_domain(client):
    response = webhook_post(client, "/webhooks/customers_redact", topic="customers/redact", shop="not a domain")
    assert response.status_code == 400


def test_shop_redact_deletes_shop_jobs(client):
    job = submit_demo_job(client, shop_domain=SHOP.split(".")[0])
    wait_for_job(client, job["job_id"])
    assert client.get(f"/api/diagnosis-jobs/{job['job_id']}", headers=HEADERS).status_code == 200

    response = webhook_post(client, "/webhooks/shop_redact", topic="shop/redact")
    assert response.status_code == 200
    assert response.json()["removed_jobs"] == 1
    assert client.get(f"/api/diagnosis-jobs/{job['job_id']}", headers=HEADERS).status_code == 404
    listing = client.get("/api/diagnosis-jobs", headers=HEADERS).json()["jobs"]
    assert all(item["job_id"] != job["job_id"] for item in listing)


def test_service_key_forwarded_webhook_is_accepted(client):
    job = submit_demo_job(client, shop_domain=SHOP.split(".")[0])
    wait_for_job(client, job["job_id"])
    raw = json.dumps(PAYLOAD).encode("utf-8")
    headers = {
        "content-type": "application/json",
        "x-app-api-key": SERVICE_KEY,
        "x-shopify-shop-domain": SHOP,
        "x-shopify-topic": "shop/redact",
    }
    response = client.post("/webhooks/shop_redact", content=raw, headers=headers)
    assert response.status_code == 200
    assert response.json()["removed_jobs"] == 1


def test_webhook_fails_closed_without_secret(client_no_secret):
    headers = {"content-type": "application/json", "x-shopify-shop-domain": SHOP}
    response = client_no_secret.post("/webhooks/customers_redact", json=PAYLOAD, headers=headers)
    assert response.status_code == 503
