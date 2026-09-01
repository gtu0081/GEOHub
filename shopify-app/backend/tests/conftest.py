from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "site-diagnose-demo"

SERVICE_KEY = "test-service-key"
API_KEY = "test-api-key"
API_SECRET = "test-api-secret"


def make_settings(tmp_path: Path, **overrides):
    from app.config import Settings

    defaults = dict(
        shopify_api_key=API_KEY,
        shopify_api_secret=API_SECRET,
        service_api_key=SERVICE_KEY,
        dev_mode=False,
        data_root=tmp_path / "data",
        fixture_root=FIXTURE_ROOT if FIXTURE_ROOT.is_dir() else None,
        max_workers=2,
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture()
def client(tmp_path):
    from app.main import create_app

    app = create_app(make_settings(tmp_path))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def client_no_secret(tmp_path):
    from app.main import create_app

    app = create_app(make_settings(tmp_path, shopify_api_secret=None, dev_mode=False))
    with TestClient(app) as test_client:
        yield test_client
