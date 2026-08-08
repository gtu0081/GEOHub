from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .validation import validate_artifact


class ArtifactBus:
    """Write validated protocol artifacts inside one bounded run directory."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        if self.root.exists() and any(self.root.iterdir()):
            raise ValueError(f"Output directory must be empty: {self.root}")
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError(f"Artifact path escapes run directory: {relative_path}")
        return target

    def write_json(
        self,
        relative_path: str,
        artifact: dict[str, Any],
        schema_name: str | None = None,
    ) -> Path:
        if schema_name:
            validate_artifact(schema_name, artifact)
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
        return target

    def write_text(self, relative_path: str, content: str) -> Path:
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        return target
