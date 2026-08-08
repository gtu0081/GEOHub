#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yao_geo.registry import load_registry  # noqa: E402
from yao_geo.validation import load_schema  # noqa: E402


def fail(message: str) -> None:
    raise SystemExit(f"repository verification failed: {message}")


def main() -> int:
    if (ROOT / "VERSION").read_text(encoding="utf-8").strip() != "0.1.0":
        fail("VERSION must be 0.1.0")
    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in (ROOT / "LICENSE").read_text(encoding="utf-8"):
        fail("LICENSE is not the GNU AGPLv3 text")

    schemas = sorted((ROOT / "schemas").glob("*.schema.json"))
    if len(schemas) != 8:
        fail(f"expected 8 protocol schemas, found {len(schemas)}")
    for path in schemas:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        if schema.get("properties", {}).get("protocol_version", {}).get("const") != "1.0.0":
            fail(f"{path.name} does not pin protocol_version 1.0.0")

    registry = load_registry(ROOT / "registry" / "skills.yaml")
    registered = {item["id"]: item for item in registry["skills"]}
    for skill_id in ("geo", "geo-discover"):
        if registered[skill_id]["status"] != "active":
            fail(f"{skill_id} must be active")
    for skill_id in ("geo-diagnose", "geo-content"):
        if registered[skill_id]["status"] != "pending-implementation":
            fail(f"{skill_id} must be pending-implementation")

    for skill_id in ("geo", "geo-discover"):
        skill_root = ROOT / "skills" / skill_id
        for relative in ("SKILL.md", "manifest.json", "agents/interface.yaml"):
            if not (skill_root / relative).is_file():
                fail(f"{skill_id} missing {relative}")
        manifest = json.loads((skill_root / "manifest.json").read_text(encoding="utf-8"))
        for key in (
            "owner",
            "review_cadence",
            "input_files",
            "output_contract",
            "rollback_boundary",
        ):
            if not manifest.get(key):
                fail(f"{skill_id} manifest missing {key}")
        yaml.safe_load((skill_root / "agents/interface.yaml").read_text(encoding="utf-8"))

    print("repository verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
