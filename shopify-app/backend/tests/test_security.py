from __future__ import annotations

import time

import jwt
import pytest

from app.security import AuthError, normalize_shop_domain, verify_session_token

from .conftest import API_KEY, API_SECRET

SHOP = "session-shop.myshopify.com"


def make_token(
    *,
    secret: str = API_SECRET,
    aud: str = API_KEY,
    iss: str | None = None,
    dest: str | None = None,
    expired: bool = False,
) -> str:
    now = int(time.time())
    if iss is None:
        iss = f"https://{SHOP}/admin"
    if dest is None:
        dest = f"https://{SHOP}"
    claims = {
        "iss": iss,
        "dest": dest,
        "aud": aud,
        "sub": "42",
        "jti": "abc",
        "sid": "sid123",
        "exp": now - 60 if expired else now + 300,
        "nbf": now - 10,
        "iat": now,
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def test_valid_session_token_verifies():
    identity = verify_session_token(make_token(), api_key=API_KEY, api_secret=API_SECRET)
    assert identity.principal == SHOP
    assert identity.kind == "session"
    assert identity.claims["sub"] == "42"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"secret": "other-secret"},
        {"aud": "other-app"},
        {"iss": "https://evil.example.com/admin"},
        {"dest": "https://evil.example.com"},
        {"expired": True},
    ],
)
def test_tampered_session_tokens_are_rejected(kwargs):
    with pytest.raises(AuthError):
        verify_session_token(make_token(**kwargs), api_key=API_KEY, api_secret=API_SECRET)


def test_normalize_shop_domain():
    assert normalize_shop_domain(" My-Shop2.myshopify.com ") == "my-shop2.myshopify.com"
    for bad in ("", "my shop.myshopify.com", "shop.example.com", "myshopify.com", "-x.myshopify.com"):
        with pytest.raises(AuthError):
            normalize_shop_domain(bad)


def test_session_token_accepted_on_api(client):
    headers = {"authorization": f"Bearer {make_token()}"}
    response = client.get("/api/diagnosis-jobs", headers=headers)
    assert response.status_code == 200


def test_session_token_rejected_on_api(client):
    headers = {"authorization": "Bearer not-a-jwt"}
    assert client.get("/api/diagnosis-jobs", headers=headers).status_code == 401
    headers = {"authorization": f"Bearer {make_token(secret='wrong')}"}
    assert client.get("/api/diagnosis-jobs", headers=headers).status_code == 401
