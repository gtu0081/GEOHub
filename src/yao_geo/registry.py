from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .paths import repository_root
from .validation import load_json


class RegistryError(ValueError):
    """Raised when the skill registry is invalid."""


def load_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or repository_root() / "registry" / "skills.yaml"
    schema_path = registry_path.with_name("skills.schema.json")
    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RegistryError(f"Unable to load registry: {exc}") from exc

    validator = Draft202012Validator(load_json(schema_path))
    errors = sorted(validator.iter_errors(data), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RegistryError(f"Invalid registry: {details}")

    identifiers = [skill["id"] for skill in data["skills"]]
    if len(identifiers) != len(set(identifiers)):
        raise RegistryError("Invalid registry: duplicate skill IDs")

    root = registry_path.parent.parent
    for skill in data["skills"]:
        entry = skill["entry"]
        if entry and not (root / entry).is_file():
            raise RegistryError(f"Invalid registry: missing entry for {skill['id']}: {entry}")
    return data
