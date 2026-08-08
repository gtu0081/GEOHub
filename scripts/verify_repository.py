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
    for skill_id in ("geo", "geo-discover", "geo-diagnose", "geo-content"):
        if registered[skill_id]["status"] != "active":
            fail(f"{skill_id} must be active")

    required_files = {
        "geo": ("SKILL.md", "manifest.json", "agents/interface.yaml", "references/routing-contract.md"),
        "geo-discover": (
            "SKILL.md",
            "manifest.json",
            "agents/interface.yaml",
            "references/discovery-method.md",
            "references/input-example.json",
            "scripts/run_discover.py",
        ),
        "geo-diagnose": (
            "SKILL.md",
            "manifest.json",
            "agents/interface.yaml",
            "references/diagnosis-method.md",
            "references/input-example.json",
            "scripts/run_diagnose.py",
        ),
        "geo-content": (
            "SKILL.md",
            "manifest.json",
            "agents/interface.yaml",
            "references/content-method.md",
            "references/modes.md",
            "references/evidence-policy.md",
            "references/output-contract.md",
            "references/input-example.json",
            "scripts/run_content.py",
        ),
    }
    for skill_id, relative_paths in required_files.items():
        skill_root = ROOT / "skills" / skill_id
        for relative in relative_paths:
            if not (skill_root / relative).is_file():
                fail(f"{skill_id} missing {relative}")
        manifest = json.loads((skill_root / "manifest.json").read_text(encoding="utf-8"))
        expected_license_fields = {
            "license_expression": "AGPL-3.0-only",
            "commercial_license_available": True,
            "commercial_license_status": "inquiry_only",
            "copyright_owner": "姚金刚 / Yao",
            "third_party_notice_required": True,
        }
        for key, expected in expected_license_fields.items():
            if manifest.get(key) != expected:
                fail(f"{skill_id} manifest {key} must be {expected!r}")
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

    diagnose_manifest = json.loads(
        (ROOT / "skills" / "geo-diagnose" / "manifest.json").read_text(encoding="utf-8")
    )
    if diagnose_manifest.get("status") != "experimental":
        fail("geo-diagnose manifest status must be experimental")
    if diagnose_manifest.get("maturity") != "experimental":
        fail("geo-diagnose manifest maturity must be experimental")
    if "production" in json.dumps(diagnose_manifest, ensure_ascii=False):
        fail("geo-diagnose manifest must not claim production maturity")
    expected_outputs = {
        "input/diagnosis-brief.json",
        "input/sources/*.html",
        "report",
        "diagnosis",
        "evidence-ledger",
        "query-map",
        "opportunity-map",
        "quality-report",
        "run-manifest",
    }
    if set(diagnose_manifest.get("output_contract", [])) != expected_outputs:
        fail("geo-diagnose manifest output contract is incomplete")

    content_manifest = json.loads(
        (ROOT / "skills" / "geo-content" / "manifest.json").read_text(encoding="utf-8")
    )
    if content_manifest.get("status") != "experimental" or content_manifest.get("maturity") != "experimental":
        fail("geo-content manifest status and maturity must be experimental")
    if content_manifest.get("version") != "0.1.0":
        fail("geo-content manifest version must be 0.1.0")
    expected_content_outputs = {
        "input/content-brief.json",
        "input/source.md",
        "content-spec.json",
        "content.json",
        "content.md",
        "content.html",
        "content.docx",
        "content.pdf",
        "evidence-ledger.json",
        "quality-report.json",
        "run-manifest.json",
    }
    if set(content_manifest.get("output_contract", [])) != expected_content_outputs:
        fail("geo-content manifest output contract is incomplete")

    print("repository verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
