from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest
import yaml

from yao_geo.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("geo", "geo-discover", "geo-diagnose", "geo-content")


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_registry_workflows_are_valid_stable_dags():
    registry = load_registry()
    assert {item["id"] for item in registry["workflows"]} == {"brand-baseline-lite", "content-campaign"}
    for workflow in registry["workflows"]:
        seen = set()
        for step in workflow["steps"]:
            assert set(step) == {"id", "skill_id", "depends_on"}
            assert set(step["depends_on"]) <= seen
            seen.add(step["id"])


@pytest.mark.parametrize("skill_id", SKILLS)
def test_library_manifests_and_interfaces_are_consistent(skill_id):
    skill_root = ROOT / "skills" / skill_id
    manifest = json.loads((skill_root / "manifest.json").read_text())
    assert manifest["status"] == "experimental"
    assert manifest["maturity_tier"] == "library"
    assert manifest["lifecycle_stage"] == "library"
    assert manifest["context_budget_tier"] == "production"
    assert manifest["contract_version"] == "1.0.0"
    assert manifest["availability"] == "active"
    assert manifest["entrypoint"] == "SKILL.md"
    assert manifest["permission_profile"]
    interface = yaml.safe_load((skill_root / "agents" / "interface.yaml").read_text())
    assert interface["compatibility"]["execution"]["shell"] == "bash"
    assert interface["interface"]["input_contract"]
    assert interface["interface"]["output_contract"]
    assert interface["interface"]["permission_contract"]


def test_eval_case_minimums_and_taxonomy():
    router_cases = json.loads((ROOT / "evals" / "router_cases.json").read_text())
    output_cases = json.loads((ROOT / "evals" / "output_cases.json").read_text())
    assert len(router_cases) >= 60
    assert len(output_cases) >= 20
    for skill_id in SKILLS:
        types = {item["case_type"] for item in output_cases if item["skill_id"] == skill_id}
        assert types == {"happy", "missing_input", "boundary", "near_neighbor", "source_shortfall"}


def test_package_allowlist_excludes_private_surfaces():
    package = load_script("package")
    for path in package.tracked_files():
        assert not ({"reports", "evals", "tests", ".git", "runs", "dist"} & set(path.parts))


def test_package_verifier_rejects_traversal(tmp_path):
    verifier = load_script("verify_packages")
    attack = tmp_path / "attack.zip"
    with zipfile.ZipFile(attack, "w") as archive:
        archive.writestr("../escape", "bad")
    with pytest.raises(ValueError, match="unsafe ZIP member"):
        verifier.verify_archive(attack)


def test_safe_extract_rejects_symlink(tmp_path):
    installer = load_script("install_simulation")
    attack = tmp_path / "symlink.zip"
    with zipfile.ZipFile(attack, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.external_attr = 0o120777 << 16
        archive.writestr(info, "target")
    with pytest.raises(ValueError, match="symlink"):
        installer.safe_extract(attack, tmp_path / "out")


def test_legal_metadata_and_ci_contract():
    for skill_id in SKILLS:
        manifest = json.loads((ROOT / "skills" / skill_id / "manifest.json").read_text())
        assert manifest["license_expression"] == "AGPL-3.0-only"
        assert manifest["commercial_license_status"] == "inquiry_only"
    cla = (ROOT / "CONTRIBUTOR-LICENSE-AGREEMENT.md").read_text()
    assert "DRAFT" in cla and "PENDING LEGAL REVIEW" in cla
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "3.11" in ci and "3.13" in ci and "macos-latest" in ci
    assert "actions/checkout@v4" in ci and "actions/setup-python@v5" in ci


def test_migration_ledger_has_exact_21_rows_and_baseline():
    ledger = (ROOT / "docs" / "migration-source-ledger.md").read_text()
    rows = [line for line in ledger.splitlines() if line.startswith("| ") and line.split("|")[1].strip().isdigit()]
    assert len(rows) == 21
    assert "201c0c45dcf09bb37bc46a467b4baf4d721db205" in ledger
    assert "内容主体 + 补充说明与参考来源" in ledger
    assert "font files" in ledger


def test_yao_meta_interface_uses_supported_shell_and_output_cases():
    for skill_id in SKILLS:
        interface = yaml.safe_load((ROOT / "skills" / skill_id / "agents" / "interface.yaml").read_text())
        assert interface["compatibility"]["execution"]["shell"] == "bash"
        lines = (ROOT / "skills" / skill_id / "evals" / "output" / "cases.jsonl").read_text().splitlines()
        assert len(lines) >= 5
        assert all(json.loads(line)["baseline_output"] != json.loads(line)["with_skill_output"] for line in lines)
