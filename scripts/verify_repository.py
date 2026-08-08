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
        "geo": ("SKILL.md", "manifest.json", "agents/interface.yaml", "references/routing-contract.md", "scripts/run_route.py", "evals/trigger_cases.json", "evals/semantic_config.json", "evals/output/cases.jsonl", "reports/output_quality_scorecard.md", "reports/trust-report.md", "reports/skill-ir.json"),
        "geo-discover": (
            "SKILL.md",
            "manifest.json",
            "agents/interface.yaml",
            "references/discovery-method.md",
            "references/input-example.json",
            "scripts/run_discover.py",
            "evals/trigger_cases.json", "evals/semantic_config.json", "evals/output/cases.jsonl", "reports/output_quality_scorecard.md", "reports/trust-report.md", "reports/skill-ir.json",
        ),
        "geo-diagnose": (
            "SKILL.md",
            "manifest.json",
            "agents/interface.yaml",
            "references/diagnosis-method.md",
            "references/input-example.json",
            "scripts/run_diagnose.py",
            "evals/trigger_cases.json", "evals/semantic_config.json", "evals/output/cases.jsonl", "reports/output_quality_scorecard.md", "reports/trust-report.md", "reports/skill-ir.json",
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
            "evals/trigger_cases.json", "evals/semantic_config.json", "evals/output/cases.jsonl", "reports/output_quality_scorecard.md", "reports/trust-report.md", "reports/skill-ir.json",
        ),
    }
    for skill_id, relative_paths in required_files.items():
        skill_root = ROOT / "skills" / skill_id
        for relative in relative_paths:
            if not (skill_root / relative).is_file():
                fail(f"{skill_id} missing {relative}")
        manifest = json.loads((skill_root / "manifest.json").read_text(encoding="utf-8"))
        expected_contract = {
            "status": "experimental",
            "maturity_tier": "library",
            "lifecycle_stage": "library",
            "context_budget_tier": "production",
            "contract_version": "1.0.0",
            "availability": "active",
            "entrypoint": "SKILL.md",
        }
        for key, expected in expected_contract.items():
            if manifest.get(key) != expected:
                fail(f"{skill_id} manifest {key} must be {expected!r}")
        if not manifest.get("permission_profile"):
            fail(f"{skill_id} manifest missing permission_profile")
        if manifest.get("target_platforms") != ["openai", "claude", "generic"]:
            fail(f"{skill_id} manifest target_platforms are inconsistent")
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
        interface = yaml.safe_load((skill_root / "agents/interface.yaml").read_text(encoding="utf-8"))
        if interface.get("compatibility", {}).get("execution", {}).get("shell") != "bash":
            fail(f"{skill_id} interface execution.shell must be bash")
        for key in ("input_contract", "output_contract", "permission_contract"):
            if not interface.get("interface", {}).get(key):
                fail(f"{skill_id} interface missing {key}")
        trigger = json.loads((skill_root / "evals" / "trigger_cases.json").read_text(encoding="utf-8"))
        if sum(len(trigger.get(key, [])) for key in ("should_trigger", "should_not_trigger", "near_neighbor")) < 5:
            fail(f"{skill_id} needs at least five trigger cases")
        output_lines = [line for line in (skill_root / "evals" / "output" / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(output_lines) < 5:
            fail(f"{skill_id} needs at least five output cases")
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        if "scripts/" not in skill_text:
            fail(f"{skill_id} SKILL.md must reference scripts/ wrapper")

    if not (ROOT / "skills" / "RESOLVER.md").is_file():
        fail("skills/RESOLVER.md is required")

    diagnose_manifest = json.loads(
        (ROOT / "skills" / "geo-diagnose" / "manifest.json").read_text(encoding="utf-8")
    )
    if diagnose_manifest.get("status") != "experimental":
        fail("geo-diagnose manifest status must be experimental")
    if diagnose_manifest.get("maturity") != "experimental":
        fail("geo-diagnose manifest maturity must be experimental")
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

    router_cases = json.loads((ROOT / "evals" / "router_cases.json").read_text(encoding="utf-8"))
    output_cases = json.loads((ROOT / "evals" / "output_cases.json").read_text(encoding="utf-8"))
    if len(router_cases) < 60 or len(output_cases) < 20:
        fail("suite eval case minimums are not met")

    machine_markers = ("/" + "Users/", "C:" + "\\Users\\")
    report_files = list((ROOT / "reports").rglob("*.json")) + list((ROOT / "reports").rglob("*.md")) + list((ROOT / "reports").rglob("*.html"))
    report_files.extend((ROOT / "skills" / skill_id / "reports" / "skill-ir.json") for skill_id in ("geo", "geo-discover", "geo-diagnose", "geo-content"))
    for report_path in report_files:
        if report_path.is_file() and any(marker in report_path.read_text(encoding="utf-8") for marker in machine_markers):
            fail(f"machine-local path found in report: {report_path.relative_to(ROOT)}")

    meta_gate = json.loads((ROOT / "reports" / "yao-meta-gates.json").read_text(encoding="utf-8"))
    if meta_gate.get("status") != "pass" or meta_gate.get("failed_commands") != 0:
        fail("recorded yao-meta gate report is not green")
    if any(item.get("exit_code") != 0 for item in meta_gate.get("commands", [])):
        fail("recorded yao-meta command failure found")

    print("repository verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
