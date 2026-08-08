import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from yao_geo.artifact_bus import ArtifactBus
from yao_geo.discover import discover
from yao_geo.validation import validate_artifact

FIXTURES = Path(__file__).parent / "fixtures"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _clock():
    return datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def test_discover_happy_path_writes_valid_artifact_bus(tmp_path):
    runs_root = tmp_path / "runs"
    result = discover(FIXTURES / "brief.json", runs_root, clock=_clock)
    output = runs_root / result["run_id"]
    assert result["status"] == "completed"
    assert result["query_count"] == 4
    assert result["warning_count"] == 0
    assert Path(result["output"]) == output
    assert output.parent.name == "runs"
    assert output.name.startswith("run-")

    expected = {
        "input/geo-brief.json",
        "run-manifest.json",
        "evidence-ledger.json",
        "query-map.json",
        "opportunity-map.json",
        "quality-report.json",
    }
    actual = {
        str(path.relative_to(output))
        for path in output.rglob("*.json")
    }
    assert actual == expected

    for filename, schema_name in {
        "run-manifest.json": "run-manifest",
        "evidence-ledger.json": "evidence-ledger",
        "query-map.json": "query-map",
        "opportunity-map.json": "opportunity-map",
        "quality-report.json": "quality-report",
    }.items():
        validate_artifact(schema_name, _load(output / filename))

    ledger = _load(output / "evidence-ledger.json")
    assert ledger["records"][0]["status"] == "provided"
    assert ledger["missing_evidence"] == []


def test_discover_records_missing_evidence_without_fabrication(tmp_path):
    runs_root = tmp_path / "runs"
    result = discover(FIXTURES / "brief-missing-evidence.json", runs_root, clock=_clock)
    output = runs_root / result["run_id"]
    ledger = _load(output / "evidence-ledger.json")
    report = _load(output / "quality-report.json")
    queries = _load(output / "query-map.json")["queries"]

    assert result["status"] == "completed-with-warnings"
    assert ledger["records"] == []
    assert len(ledger["missing_evidence"]) == 2
    assert report["status"] == "passed-with-warnings"
    assert "missing evidence" in report["warnings"][0]
    assert {item["evidence_status"] for item in queries} == {"missing"}


def test_discovery_content_is_deterministic(tmp_path):
    first_result = discover(FIXTURES / "brief.json", tmp_path / "first", clock=_clock)
    second_result = discover(
        FIXTURES / "brief.json",
        tmp_path / "second",
        clock=lambda: datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    first = Path(first_result["output"])
    second = Path(second_result["output"])
    for filename in ("query-map.json", "opportunity-map.json", "evidence-ledger.json"):
        assert _load(first / filename) == _load(second / filename)


def test_artifact_bus_rejects_nonempty_output_and_path_escape(tmp_path):
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "user-file.txt").write_text("preserve me", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        ArtifactBus(occupied)

    bus = ArtifactBus(tmp_path / "clean")
    with pytest.raises(ValueError, match="escapes run directory"):
        bus.write_json("../outside.json", {})


def test_discover_rejects_duplicate_evidence_ids(tmp_path):
    source = _load(FIXTURES / "brief.json")
    source["evidence"].append(dict(source["evidence"][0]))
    duplicate_brief = tmp_path / "duplicate.json"
    duplicate_brief.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        discover(duplicate_brief, tmp_path / "runs", clock=_clock)
