from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# shopify-app/backend/app/config.py -> shopify-app/
SHOPIFY_APP_ROOT = Path(__file__).resolve().parents[2]
# -> geohub repository root (only valid in a checkout; not used in production)
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    shopify_api_key: str | None
    shopify_api_secret: str | None
    service_api_key: str | None
    dev_mode: bool
    data_root: Path
    fixture_root: Path | None
    max_workers: int

    @property
    def session_auth_ready(self) -> bool:
        return bool(self.shopify_api_key and self.shopify_api_secret)

    @property
    def webhook_auth_ready(self) -> bool:
        return bool(self.shopify_api_secret)


def settings_from_env() -> Settings:
    data_root = Path(
        os.environ.get("GEOHUB_APP_DATA_ROOT", str(SHOPIFY_APP_ROOT / "data"))
    ).resolve()
    fixture_root = Path(
        os.environ.get(
            "GEOHUB_FIXTURE_ROOT",
            str(REPOSITORY_ROOT / "tests" / "fixtures" / "site-diagnose-demo"),
        )
    )
    if not fixture_root.is_dir():
        fixture_root = None
    return Settings(
        shopify_api_key=os.environ.get("SHOPIFY_API_KEY") or None,
        shopify_api_secret=os.environ.get("SHOPIFY_API_SECRET") or None,
        service_api_key=os.environ.get("GEOHUB_APP_API_KEY") or None,
        dev_mode=_flag("GEOHUB_APP_DEV_MODE"),
        data_root=data_root,
        fixture_root=fixture_root,
        max_workers=max(1, int(os.environ.get("GEOHUB_APP_MAX_WORKERS", "2"))),
    )
