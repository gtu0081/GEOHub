import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from yao_geo.paths import repository_root
from yao_geo.registry import load_registry
from yao_geo.validation import ArtifactValidationError, load_schema, validate_artifact


def test_all_eight_protocol_schemas_are_valid():
    expected = {
        "geo-brief",
        "run-manifest",
        "evidence-ledger",
        "brand-fact-card",
        "query-map",
        "opportunity-map",
        "content-spec",
        "quality-report",
    }
    actual = {path.name.removesuffix(".schema.json") for path in (repository_root() / "schemas").glob("*.schema.json")}
    assert actual == expected
    for name in expected:
        schema = load_schema(name)
        Draft202012Validator.check_schema(schema)
        assert schema["properties"]["protocol_version"]["const"] == "1.0.0"


def test_reserved_schemas_accept_protocol_examples():
    validate_artifact(
        "brand-fact-card",
        {
            "protocol_version": "1.0.0",
            "brand_id": "brand-1",
            "facts": [
                {
                    "fact_id": "fact-1",
                    "statement": "A sourced statement.",
                    "evidence_ids": ["ev-1"],
                    "status": "verified",
                }
            ],
        },
    )
    validate_artifact(
        "content-spec",
        {
            "protocol_version": "1.0.0",
            "spec_id": "spec-1",
            "title": "A useful guide",
            "target_query_ids": ["qry-1"],
            "required_evidence_ids": ["ev-1"],
            "sections": [{"heading": "Evidence", "purpose": "Answer with sourced facts."}],
            "status": "ready",
        },
    )


def test_protocol_mismatch_is_rejected():
    with pytest.raises(ArtifactValidationError, match="1.0.0"):
        validate_artifact(
            "geo-brief",
            {
                "protocol_version": "2.0.0",
                "brief_id": "bad",
                "subject": "bad protocol",
                "seed_queries": ["test"],
            },
        )


def test_registry_validates_and_unavailable_routes_have_no_entry():
    registry = load_registry()
    assert registry["protocol_version"] == "1.0.0"
    for skill in registry["skills"]:
        if skill["status"] != "active":
            assert skill["entry"] is None
            assert skill["active_placeholder"] is False


def test_skill_manifests_declare_license_governance():
    expected = {
        "license_expression": "AGPL-3.0-only",
        "commercial_license_available": True,
        "commercial_license_status": "inquiry_only",
        "copyright_owner": "姚金刚 / Yao",
        "third_party_notice_required": True,
    }
    for skill_id in ("geo", "geo-discover"):
        path = repository_root() / "skills" / skill_id / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert {key: manifest[key] for key in expected} == expected
