from __future__ import annotations

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import jwt

SHOP_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$")


class AuthError(ValueError):
    """Raised when a presented credential fails verification."""


@dataclass(frozen=True)
class Identity:
    principal: str
    kind: str  # "session" | "service" | "dev"
    claims: dict | None = None


def normalize_shop_domain(value: str) -> str:
    domain = (value or "").strip().lower()
    if not SHOP_DOMAIN_RE.match(domain):
        raise AuthError(f"invalid shop domain: {value!r}")
    return domain


def verify_session_token(token: str, *, api_key: str, api_secret: str) -> Identity:
    """Verify a Shopify session token (JWT, HS256, signed with the API secret)."""
    try:
        claims = jwt.decode(
            token,
            api_secret,
            algorithms=["HS256"],
            audience=api_key,
            options={"require": ["exp", "iss", "dest", "aud"]},
        )
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"invalid session token: {exc}") from exc
    dest = str(claims.get("dest") or "")
    iss = str(claims.get("iss") or "")
    host = urlsplit(dest).hostname or ""
    if not SHOP_DOMAIN_RE.match(host):
        raise AuthError(f"session token dest is not a shop domain: {dest!r}")
    if dest != f"https://{host}":
        raise AuthError(f"session token dest must be https://<shop-domain>: {dest!r}")
    if iss != f"https://{host}/admin":
        raise AuthError(f"session token iss must match dest admin origin: {iss!r}")
    return Identity(principal=host, kind="session", claims=claims)


def verify_webhook_hmac(raw_body: bytes, hmac_header: str, *, api_secret: str) -> bool:
    digest = hmac.new(api_secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, (hmac_header or "").strip())


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
