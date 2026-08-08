import json
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from yao_geo.diagnose import (
    FetchResult,
    SourceUnavailable,
    URLPolicyError,
    _default_fetch,
    diagnose,
    validate_diagnosis,
    validate_diagnosis_brief,
    validate_public_url,
)
from yao_geo.validation import validate_artifact

FIXTURES = Path(__file__).parent / "fixtures"


def _clock():
    return datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _public_resolver(host, _port, *, type):
    assert type == socket.SOCK_STREAM
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


def test_page_source_html_writes_complete_valid_run(tmp_path):
    runs_root = tmp_path / "runs"
    result = diagnose(FIXTURES / "diagnosis-page.json", runs_root, clock=_clock)
    output = Path(result["output"])

    assert output.parent == runs_root
    assert output.name.startswith("run-")
    assert result["status"] == "completed-with-warnings"
    assert result["diagnosis_status"] == "completed"
    expected = {
        "input/diagnosis-brief.json",
        "input/source.html",
        "diagnosis.json",
        "report.md",
        "evidence-ledger.json",
        "query-map.json",
        "opportunity-map.json",
        "quality-report.json",
        "run-manifest.json",
    }
    assert {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()} == expected

    for filename, schema_name in {
        "evidence-ledger.json": "evidence-ledger",
        "query-map.json": "query-map",
        "opportunity-map.json": "opportunity-map",
        "quality-report.json": "quality-report",
        "run-manifest.json": "run-manifest",
    }.items():
        validate_artifact(schema_name, _load(output / filename))
    manifest = _load(output / "run-manifest.json")
    assert set(manifest["artifacts"]) == expected - {"run-manifest.json"}
    normalized_brief = _load(output / "input" / "diagnosis-brief.json")
    assert normalized_brief["source_html"] == {"path": "source.html"}

    diagnosis_artifact = _load(output / "diagnosis.json")
    assert diagnosis_artifact["scores"]["discoverability"] == 100
    assert diagnosis_artifact["source_status"][0]["status"] == "provided"
    assert diagnosis_artifact["source_status"][0]["observations"]["title"] == "Acme Knowledge Guide"
    assert diagnosis_artifact["source_status"][0]["observations"]["valid_json_ld_count"] == 1
    ledger_ids = {record["evidence_id"] for record in _load(output / "evidence-ledger.json")["records"]}
    for finding in diagnosis_artifact["findings"]:
        if finding["source_kind"] != "input_gap":
            assert finding["evidence_id"] in ledger_ids

    first_report = (output / "report.md").read_text(encoding="utf-8")
    second = diagnose(FIXTURES / "diagnosis-page.json", tmp_path / "second-runs", clock=lambda: datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert first_report == (Path(second["output"]) / "report.md").read_text(encoding="utf-8")

    replay = diagnose(output / "input" / "diagnosis-brief.json", tmp_path / "replay-runs", clock=_clock)
    assert replay["run_id"] == result["run_id"]


def test_brand_evidence_only_has_provided_lineage(tmp_path):
    result = diagnose(FIXTURES / "diagnosis-brand.json", tmp_path / "runs", clock=_clock)
    output = Path(result["output"])
    diagnosis_artifact = _load(output / "diagnosis.json")
    assert diagnosis_artifact["scope"] == "brand"
    assert diagnosis_artifact["scores"]["brand_fact_coverage"] == 100
    assert {finding["source_kind"] for finding in diagnosis_artifact["findings"]} == {"provided", "inferred"}
    assert {finding["evidence_id"] for finding in diagnosis_artifact["findings"]} == {"ev-acme-about"}


def test_missing_all_sources_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        validate_diagnosis_brief({"subject": "Acme", "scope": "page"})


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://localhost/page", "localhost"),
        ("http://127.0.0.1/page", "non-public"),
        ("http://169.254.1.2/page", "non-public"),
        ("http://10.0.0.1/page", "non-public"),
        ("http://user:secret@example.com/page", "credentials"),
    ],
)
def test_url_policy_rejects_unsafe_targets(url, message):
    with pytest.raises(URLPolicyError, match=message):
        validate_public_url(url, resolver=_public_resolver)


def test_url_policy_rejects_hostname_if_any_dns_answer_is_nonpublic():
    def mixed_resolver(_host, _port, *, type):
        return [
            (socket.AF_INET, type, 6, "", ("93.184.216.34", 0)),
            (socket.AF_INET, type, 6, "", ("10.0.0.1", 0)),
        ]

    with pytest.raises(URLPolicyError, match="non-public"):
        validate_public_url("https://example.com", resolver=mixed_resolver)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/page?token=secret",
        "https://example.com/page?api_key=secret",
        "https://example.com/page?X-Amz-Signature=secret",
        "https://example.com/page?credential=secret",
    ],
)
def test_url_policy_rejects_sensitive_query_credentials(url):
    with pytest.raises(URLPolicyError, match="sensitive query"):
        validate_public_url(url, resolver=_public_resolver)


def test_injected_fetcher_failure_delivers_source_gap(tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(
        json.dumps({"subject": "Unavailable page", "scope": "page", "target_urls": ["https://93.184.216.34/page"]}),
        encoding="utf-8",
    )

    def unavailable(_url):
        raise SourceUnavailable("simulated offline source")

    result = diagnose(brief, tmp_path / "runs", clock=_clock, fetcher=unavailable)
    output = Path(result["output"])
    diagnosis_artifact = _load(output / "diagnosis.json")
    assert result["status"] == "completed-with-warnings"
    assert diagnosis_artifact["status"] == "degraded"
    assert diagnosis_artifact["source_status"][0]["status"] == "source_gap"
    assert "No page observation was inferred" in diagnosis_artifact["limitations"][0]
    assert _load(output / "evidence-ledger.json")["records"] == []


def test_injected_fetcher_happy_path_observes_only_explicit_url(tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Public page", "scope": "page", "target_urls": ["https://example.com/page"]}), encoding="utf-8")
    calls = []

    def fetch(url):
        calls.append(url)
        return FetchResult(url, b"<title>Public</title><main><h1>Public</h1><h2>Facts</h2><p>Source method by expert, updated 2026. Evidence text long enough.</p></main>")

    result = diagnose(brief, tmp_path / "runs", clock=_clock, fetcher=fetch, resolver=_public_resolver)
    assert calls == ["https://example.com/page"]
    status = _load(Path(result["output"]) / "diagnosis.json")["source_status"]
    assert status[0]["status"] == "observed"


def test_dns_rebinding_attempt_degrades_without_connecting(tmp_path):
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Rebinding", "scope": "page", "target_urls": ["http://example.com"]}), encoding="utf-8")
    answers = iter(["93.184.216.34", "127.0.0.1"])

    def rebinding_resolver(_host, _port, *, type):
        return [(socket.AF_INET, type, 6, "", (next(answers), 0))]

    result = diagnose(brief, tmp_path / "runs", clock=_clock, resolver=rebinding_resolver)
    diagnosis_artifact = _load(Path(result["output"]) / "diagnosis.json")
    assert diagnosis_artifact["status"] == "degraded"
    assert diagnosis_artifact["source_status"][0]["status"] == "source_gap"


def test_private_redirect_becomes_source_gap_policy_error(monkeypatch):
    class RedirectResponse:
        status = 302

        @staticmethod
        def getheader(name, default=None):
            return "http://127.0.0.1/private" if name == "Location" else default

    class FakeConnection:
        def __init__(self, *_args, **_kwargs):
            pass

        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            return RedirectResponse()

        def close(self):
            pass

    monkeypatch.setattr("yao_geo.diagnose.http.client.HTTPConnection", FakeConnection)
    with pytest.raises(SourceUnavailable, match="redirect target rejected"):
        _default_fetch("http://example.com", resolver=_public_resolver)


def test_file_fixture_cannot_escape_brief_directory(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.html"
    outside.write_text("<title>outside</title>", encoding="utf-8")
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Escape", "scope": "page", "source_html": {"path": f"../{outside.name}"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="stay relative"):
        diagnose(brief, tmp_path / "runs", clock=_clock)


def test_file_fixture_rejects_symlink_component(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "page.html").write_text("<title>real</title>", encoding="utf-8")
    (tmp_path / "linked").symlink_to(real, target_is_directory=True)
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Symlink", "scope": "page", "source_html": {"path": "linked/page.html"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="symlinks"):
        diagnose(brief, tmp_path / "runs", clock=_clock)


def test_run_and_evidence_ids_change_with_html_content(tmp_path):
    page = tmp_path / "page.html"
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"subject": "Changing page", "scope": "page", "source_html": {"path": "page.html"}}), encoding="utf-8")
    page.write_text("<title>First</title><h1>First</h1>", encoding="utf-8")
    first = diagnose(brief, tmp_path / "first", clock=_clock)
    page.write_text("<title>Second</title><h1>Second</h1>", encoding="utf-8")
    second = diagnose(brief, tmp_path / "second", clock=_clock)
    assert first["run_id"] != second["run_id"]
    first_ledger = _load(Path(first["output"]) / "evidence-ledger.json")
    second_ledger = _load(Path(second["output"]) / "evidence-ledger.json")
    assert first_ledger["records"][0]["evidence_id"] != second_ledger["records"][0]["evidence_id"]


def test_opportunities_reference_generated_query_map(tmp_path):
    result = diagnose(FIXTURES / "diagnosis-brand.json", tmp_path / "runs", clock=_clock)
    output = Path(result["output"])
    query_ids = {item["query_id"] for item in _load(output / "query-map.json")["queries"]}
    for opportunity in _load(output / "opportunity-map.json")["opportunities"]:
        assert set(opportunity["query_ids"]) <= query_ids


@pytest.mark.parametrize(
    "brief",
    [
        {"subject": " ", "scope": "brand", "evidence": [{"evidence_id": "ev", "claim": "claim", "source_uri": "urn:test"}]},
        {"subject": "Acme", "scope": "brand", "evidence": [{"evidence_id": " ", "claim": "claim", "source_uri": "urn:test"}]},
        {"subject": "Acme", "scope": "brand", "goals": ["  "], "evidence": [{"evidence_id": "ev", "claim": "claim", "source_uri": "urn:test"}]},
    ],
)
def test_blank_input_strings_are_rejected(brief):
    with pytest.raises(ValueError, match="non-blank"):
        validate_diagnosis_brief(brief)


def test_duplicate_evidence_ids_are_rejected():
    record = {"evidence_id": "ev-1", "claim": "claim", "source_uri": "urn:test"}
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        validate_diagnosis_brief({"subject": "Acme", "scope": "brand", "evidence": [record, dict(record)]})


def test_input_limits_reject_too_many_targets_and_large_inline_html():
    with pytest.raises(ValueError, match="at most 5"):
        validate_diagnosis_brief({"subject": "Acme", "scope": "page", "target_urls": [f"https://example.com/{index}" for index in range(6)]})
    with pytest.raises(ValueError, match="source_html exceeds"):
        validate_diagnosis_brief({"subject": "Acme", "scope": "page", "source_html": "x" * (2 * 1024 * 1024 + 1)})


def test_diagnosis_validator_rejects_finding_without_ledger_lineage():
    artifact = {
        "protocol_version": "1.0.0",
        "run_id": "run-test",
        "subject": "Acme",
        "scope": "page",
        "status": "completed",
        "scores": {"structure": 50},
        "findings": [
            {
                "finding_id": "finding-1",
                "category": "structure",
                "severity": "warning",
                "source_kind": "observed",
                "statement": "An observed statement.",
                "evidence_id": "ev-missing",
                "recommendation": "Add structure.",
            }
        ],
        "limitations": [],
        "source_status": [],
    }
    with pytest.raises(ValueError, match="absent from the evidence ledger"):
        validate_diagnosis(artifact, evidence_ids=[])
