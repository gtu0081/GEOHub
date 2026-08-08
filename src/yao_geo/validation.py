from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .paths import repository_root


class ArtifactValidationError(ValueError):
    """Raised when an artifact does not satisfy its protocol schema."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError(f"Unable to load JSON from {path}: {exc}") from exc


def load_schema(name: str) -> dict[str, Any]:
    return load_json(repository_root() / "schemas" / f"{name}.schema.json")


def validate_artifact(name: str, artifact: dict[str, Any]) -> None:
    validator = Draft202012Validator(load_schema(name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(
            f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ArtifactValidationError(f"{name} validation failed: {details}")
