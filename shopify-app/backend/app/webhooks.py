from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .config import Settings
from .jobs import JobManager
from .security import constant_time_equals, normalize_shop_domain, verify_webhook_hmac

logger = logging.getLogger("geohub.webhooks")

router = APIRouter()


def _hmac_header(request: Request) -> str:
    return request.headers.get("x-shopify-hmac-sha256", "")


async def _handle(
    request: Request,
    *,
    settings: Settings,
    job_manager: JobManager,
    topic: str,
    redact_shop: bool,
) -> JSONResponse:
    raw = await request.body()
    service_key = request.headers.get("x-app-api-key", "")
    forwarded_by_service = bool(
        settings.service_api_key
        and service_key
        and constant_time_equals(service_key, settings.service_api_key)
    )
    if forwarded_by_service:
        # Trusted first hop (e.g. the Remix shell) already verified Shopify's HMAC.
        pass
    elif settings.webhook_auth_ready:
        if not verify_webhook_hmac(raw, _hmac_header(request), api_secret=settings.shopify_api_secret or ""):
            return JSONResponse({"error": "invalid hmac"}, status_code=401)
    elif not settings.dev_mode:
        return JSONResponse({"error": "webhook secret is not configured"}, status_code=503)
    else:
        logger.warning("webhook accepted without HMAC verification (dev mode): %s", topic)

    announced = request.headers.get("x-shopify-topic", "")
    if announced and announced != topic:
        return JSONResponse({"error": "topic mismatch"}, status_code=400)
    try:
        shop = normalize_shop_domain(request.headers.get("x-shopify-shop-domain", ""))
    except ValueError:
        return JSONResponse({"error": "invalid shop domain"}, status_code=400)

    removed = job_manager.redact_shop(shop) if redact_shop else 0
    if redact_shop:
        logger.info("shop/redact: deleted %d jobs for %s", removed, shop)
    # Mandatory webhooks must answer 200 quickly.
    return JSONResponse({"ok": True, "shop": shop, "removed_jobs": removed})


@router.post("/webhooks/customers_data_request")
async def customers_data_request(request: Request) -> JSONResponse:
    return await _handle(
        request,
        settings=request.app.state.settings,
        job_manager=request.app.state.job_manager,
        topic="customers/data_request",
        redact_shop=False,
    )


@router.post("/webhooks/customers_redact")
async def customers_redact(request: Request) -> JSONResponse:
    return await _handle(
        request,
        settings=request.app.state.settings,
        job_manager=request.app.state.job_manager,
        topic="customers/redact",
        redact_shop=False,
    )


@router.post("/webhooks/shop_redact")
async def shop_redact(request: Request) -> JSONResponse:
    return await _handle(
        request,
        settings=request.app.state.settings,
        job_manager=request.app.state.job_manager,
        topic="shop/redact",
        redact_shop=True,
    )
