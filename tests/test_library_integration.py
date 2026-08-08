from __future__ import annotations

import importlib.util
import inspect
import json
import re
import tomllib
import zipfile
from datetime import date
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


def test_non_source_packages_have_self_contained_install_and_route_entries():
    package = load_script("package")
    collision_project = tomllib.loads(
        package.packaged_pyproject(
            {
                "SKILL.md": b"fixture",
                "references/providers/a/shared.md": b"a",
                "references/providers/b/shared.md": b"b",
            }
        ).decode()
    )
    collision_groups = collision_project["tool"]["setuptools"]["data-files"]
    assert collision_groups["share/yao-geo/references/providers/a"] == ["references/providers/a/shared.md"]
    assert collision_groups["share/yao-geo/references/providers/b"] == ["references/providers/b/shared.md"]
    archives = package.build("all")
    for path in archives:
        if path.name.startswith("yao-geo-source-"):
            continue
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            project = tomllib.loads(archive.read("pyproject.toml").decode())
            assert project["project"]["requires-python"] == ">=3.11,<3.15"
            assert project["project"]["readme"] in names
            for destination, sources in project["tool"]["setuptools"]["data-files"].items():
                assert set(sources) <= names
                for source in sources:
                    relative_parent = Path(source).parent.as_posix()
                    expected_destination = "share/yao-geo" if relative_parent == "." else f"share/yao-geo/{relative_parent}"
                    assert destination == expected_destination
            registry = yaml.safe_load(archive.read("registry/skills.yaml"))
            for skill in registry["skills"]:
                if skill["status"] == "active":
                    assert skill["entry"] in names
                    entry_text = archive.read(skill["entry"]).decode()
                    frontmatter = yaml.safe_load(entry_text.split("---", 2)[1])
                    assert frontmatter["name"] == skill["id"]
                    referenced = set(re.findall(r"(?:references|scripts)/[A-Za-z0-9_.\-/]+", entry_text))
                    assert referenced <= names
        if "unified" in path.name or "codex" in path.name or "claude" in path.name:
            assert {f"scripts/run_{name}.py" for name in ("route", "discover", "diagnose", "content")} <= names


def test_install_simulation_uses_each_extracted_package_and_real_provider_execution():
    installer = load_script("install_simulation")
    assert list(inspect.signature(installer.structural_smoke).parameters) == ["path", "temp_root", "wheelhouse"]
    assert "Path(raw).resolve()" not in inspect.getsource(installer.main)
    source = inspect.getsource(installer.structural_smoke)
    assert "install_extracted(destination" in source
    assert 'wrappers["run_route.py"]' in source
    assert all(f'"run_{provider}.py"' in source for provider in ("discover", "diagnose", "content"))
    report = json.loads((ROOT / "reports" / "install-simulation.json").read_text())
    assert len(report["structural_packages"]) == 7
    assert all(item["installed_from"] == "." and item["installed_share_resolved"] and item["resolved_entry"] and item["provider_executions"] == ["geo-discover", "geo-diagnose", "geo-content"] for item in report["structural_packages"])


def test_supported_python_range_and_governance_contracts():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert project["project"]["requires-python"] == ">=3.11,<3.15"
    assert "3.11-3.14" in (ROOT / "README.md").read_text()
    assert "3.11-3.14" in (ROOT / "docs" / "installation.md").read_text()
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert all(f'"{version}"' in ci for version in ("3.11", "3.12", "3.13", "3.14"))

    cla = (ROOT / "CONTRIBUTOR-LICENSE-AGREEMENT.md").read_text()
    assert "Harmony 1.0" in cla and "Individual" in cla and "Entity" in cla
    assert "not enabled" in cla and "not offered for acceptance" in cla
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
    assert "CC BY 3.0" in notices and "Creative Commons Attribution 3.0" in notices
    contributing = (ROOT / "CONTRIBUTING.md").read_text()
    assert "DCO" in contributing and "CLA" in contributing
    commercial = (ROOT / "COMMERCIAL-LICENSING.md").read_text()
    assert "GitHub" in commercial and "Issue" in commercial
    scope = (ROOT / "LICENSE-SCOPE.md").read_text()
    for boundary in ("code", "documentation", "templates", "generated outputs", "user data", "trademarks"):
        assert boundary in scope.casefold()


def test_yao_meta_structured_status_and_waiver_ledger_fail_closed(tmp_path):
    gate = load_script("run_yao_meta_gates")
    failed = tmp_path / "failed.json"
    failed.write_text(json.dumps({"ok": False, "summary": {"decision": "pass"}}))
    assert gate.structured_report_status(failed) == "fail"
    for payload in ({"status": "blocked"}, {"status": "partial"}, {"hello": "world"}):
        unknown = tmp_path / f"unknown-{len(list(tmp_path.iterdir()))}.json"
        unknown.write_text(json.dumps(payload))
        assert gate.structured_report_status(unknown) == "fail"
    operation_reports = {
        "skill-ir": ROOT / "reports" / "yao-meta" / "geo-skill-ir.json",
        "output-eval": ROOT / "reports" / "yao-meta" / "geo-output-eval.json",
        "trust": ROOT / "reports" / "yao-meta" / "geo-trust.json",
        "review-studio": ROOT / "reports" / "yao-meta" / "geo-review-studio.json",
        "compile-skill": ROOT / "reports" / "yao-meta" / "geo-compiled-generic.json",
        "conformance": ROOT / "reports" / "yao-meta" / "geo-conformance-generic.json",
        "skill-atlas": ROOT / "reports" / "skill-atlas.json",
    }
    for operation, positive in operation_reports.items():
        expected = "review" if operation == "review-studio" else "pass"
        assert gate.structured_report_status(positive, operation) == expected
        for index, payload in enumerate(({"status": "pass"}, {"ok": True})):
            skeletal = tmp_path / f"skeletal-{operation}-{index}.json"
            skeletal.write_text(json.dumps(payload))
            assert gate.structured_report_status(skeletal, operation) == "fail"
        typed_empty = {
            key: (True if expected_type is bool else expected_type())
            for key, expected_type in gate.OPERATION_REPORT_FIELDS[operation].items()
        }
        typed_empty_path = tmp_path / f"typed-empty-{operation}.json"
        typed_empty_path.write_text(json.dumps(typed_empty))
        assert gate.structured_report_status(typed_empty_path, operation) == "fail"

    waivers = gate.load_waiver_ledger(ROOT / "reports" / "review-waivers.json", today=date(2026, 8, 8))
    assert waivers
    assert all({"id", "skill_id", "gate", "owner", "reason", "expires_on", "recheck"} <= set(item) for item in waivers)
    review = {
        "ok": True,
        "summary": {"decision": "review"},
        "warnings": [{"key": "operations-loop"}, {"key": "release-notes"}],
    }
    classified = gate.classify_review_studio("geo", review, waivers)
    assert classified["release_blocking"] == []
    assert classified["waived_missing_evidence"] == ["operations-loop", "release-notes"]
    assert classified["review_warning_count"] == classified["classified_warning_count"] == 2

    ledger = json.loads((ROOT / "reports" / "review-waivers.json").read_text())
    attacks = []
    unknown = json.loads(json.dumps(ledger))
    unknown["waivers"][0]["gate"] = "unknown-suite-gate"
    attacks.append(unknown)
    duplicate_pair = json.loads(json.dumps(ledger))
    duplicate_pair["waivers"][1]["skill_id"] = duplicate_pair["waivers"][0]["skill_id"]
    duplicate_pair["waivers"][1]["gate"] = duplicate_pair["waivers"][0]["gate"]
    attacks.append(duplicate_pair)
    empty = {"schema_version": "1.0.0", "waivers": []}
    attacks.append(empty)
    for index, attack in enumerate(attacks):
        attack_path = tmp_path / f"waiver-attack-{index}.json"
        attack_path.write_text(json.dumps(attack))
        with pytest.raises(ValueError, match="waiver ledger"):
            gate.load_waiver_ledger(attack_path, today=date(2026, 8, 8))


def test_yao_meta_digest_and_command_inventory_are_complete():
    gate = load_script("run_yao_meta_gates")
    paths = {path.relative_to(ROOT).as_posix() for path in gate.source_digest_paths()}
    assert not any(".egg-info/" in path for path in paths)
    assert {
        "scripts/package.py",
        "scripts/verify_packages.py",
        "scripts/install_simulation.py",
        "reports/package-verification.json",
        "reports/install-simulation.json",
    } <= paths

    report = json.loads((ROOT / "reports" / "yao-meta-gates.json").read_text())
    assert gate.validate_command_inventory(report["commands"]) == []
    duplicated = [dict(report["commands"][0]) for _ in range(53)]
    assert gate.validate_command_inventory(duplicated)
    extra_flag = json.loads(json.dumps(report["commands"]))
    extra_flag[0]["command"].append("--unknown-flag")
    assert gate.validate_command_inventory(extra_flag)
    wrong_skill_path = json.loads(json.dumps(report["commands"]))
    wrong_skill_path[0]["command"][3] = "skills/geo-content"
    assert gate.validate_command_inventory(wrong_skill_path)
    unknown_unstructured_status = json.loads(json.dumps(report["commands"]))
    unknown_unstructured_status[0]["structured_status"] = "mystery"
    assert gate.validate_command_inventory(unknown_unstructured_status)
    trigger_structured_status = json.loads(json.dumps(report["commands"]))
    trigger_structured_status[1]["structured_status"] = "pass"
    assert gate.validate_command_inventory(trigger_structured_status)
    assert gate.deterministic_evidence_is_green(ROOT / "skills" / "geo" / "manifest.json")
    assert gate.deterministic_evidence_is_green(ROOT / "skills" / "geo" / "evals" / "semantic_config.json")
