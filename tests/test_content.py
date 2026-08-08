import importlib
import json
import zipfile
from pathlib import Path

import pytest

from yao_geo.artifact_bus import ArtifactBus
from yao_geo.cli import main
from yao_geo.content import MAX_INPUT_BYTES, content, validate_content_brief


def _write(tmp_path: Path, payload: dict, name: str = "brief.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _run(tmp_path: Path, payload: dict, root: str = "runs") -> tuple[dict, Path]:
    result = content(_write(tmp_path, payload), tmp_path / root)
    return result, Path(result["output"])


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_title_candidates_are_pattern_varied_and_compliant(tmp_path):
    _, run = _run(tmp_path, {"mode": "title", "topic": "2026 最新最好 AI 搜索"})
    artifact = _read(run / "content.json")
    candidates = artifact["mode_data"]["title_candidates"]
    assert len(candidates) >= 5
    assert len({item["pattern"] for item in candidates}) == len(candidates)
    rendered = " ".join(item["title"] for item in candidates).casefold()
    for forbidden in ("最好", "最新", "best", "latest", "2026"):
        assert forbidden not in rendered
    assert all(set(item["scores"]) == {"intent", "scenario", "evidence", "compliance"} for item in candidates)


def test_explainer_has_required_structure_and_lineage(tmp_path):
    _, run = _run(
        tmp_path,
        {
            "mode": "explainer",
            "topic": "证据血缘",
            "evidence": [{"label": "user-ref", "claim": "事实 A", "source_uri": "https://example.com/a"}],
        },
    )
    content_json = _read(run / "content.json")
    ledger = _read(run / "evidence-ledger.json")
    assert len(content_json["sections"]) >= 6
    assert content_json["factual_claims"][0]["evidence_ids"][0] == ledger["records"][0]["evidence_id"]
    assert ledger["records"][0]["evidence_id"] != "user-ref"
    normalized = _read(run / "input" / "content-brief.json")
    assert normalized["evidence"][0]["label"] == ledger["records"][0]["evidence_id"]


def test_comparison_blocks_without_evidence_and_stays_neutral_with_evidence(tmp_path):
    _, blocked_run = _run(tmp_path, {"mode": "comparison", "topic": "A 和 B", "entities": ["A", "B"]}, "blocked")
    blocked = _read(blocked_run / "content.json")
    assert blocked["status"] == "blocked-by-evidence"
    assert blocked["mode_data"]["comparison"]["verdict"] is None
    _, ready_run = _run(
        tmp_path,
        {
            "mode": "comparison",
            "topic": "A 和 B",
            "entities": ["A", "B"],
            "evidence": [
                {"label": "a", "claim": "A 有属性 X", "source_uri": "https://example.com/a", "entity": "A", "dimension": "X"},
                {"label": "b", "claim": "B 有属性 X", "source_uri": "https://example.com/b", "entity": "B", "dimension": "X"},
            ],
        },
        "ready",
    )
    ready = _read(ready_run / "content.json")
    assert ready["status"] == "ready"
    assert ready["mode_data"]["comparison"]["verdict"] is None


def test_ranking_requires_method_and_evidence_backed_scores(tmp_path):
    _, blocked_run = _run(tmp_path, {"mode": "ranking", "topic": "工具榜单", "entities": ["A", "B"]}, "blocked")
    blocked = _read(blocked_run / "content.json")
    assert blocked["status"] == "blocked-by-evidence"
    assert blocked["mode_data"]["ranking"]["rows"] == []
    assert "TOP1" not in (blocked_run / "content.md").read_text(encoding="utf-8")

    _, ready_run = _run(
        tmp_path,
        {
            "mode": "ranking",
            "topic": "工具评估",
            "entities": ["A", "B"],
            "evaluation_method": {"name": "同口径评分", "criteria": [{"name": "质量", "weight": 2}]},
            "evidence": [
                {"label": "a", "claim": "A 质量得分 80", "source_uri": "https://example.com/a", "entity": "A", "dimension": "质量", "score": 80},
                {"label": "b", "claim": "B 质量得分 90", "source_uri": "https://example.com/b", "entity": "B", "dimension": "质量", "score": 90},
            ],
        },
        "ready",
    )
    rows = _read(ready_run / "content.json")["mode_data"]["ranking"]["rows"]
    assert [(row["rank"], row["entity"]) for row in rows] == [(1, "B"), (2, "A")]
    assert all(row["evidence_ids"] for row in rows)


def test_page_blueprint_contains_semantic_html_and_evidence_consistent_schema(tmp_path):
    _, run = _run(
        tmp_path,
        {"mode": "page-blueprint", "topic": "产品页", "evidence": [{"label": "x", "claim": "产品支持离线运行", "source_uri": "https://example.com/product"}]},
    )
    blueprint = _read(run / "content.json")["mode_data"]["page_blueprint"]
    assert blueprint["semantic_html_example"].startswith("<main>")
    assert blueprint["schema_candidates"][0]["claims"] == ["产品支持离线运行"]
    assert blueprint["cms_fields"] and blueprint["acceptance_checklist"]


def test_refine_requires_source_and_article_friendly_reuses_profile(tmp_path):
    with pytest.raises(ValueError, match="requires source_content"):
        validate_content_brief({"mode": "refine", "topic": "原文"})
    source = "核心主张保持不变。\n第二条内容可用于回答问题。"
    _, refine_run = _run(tmp_path, {"mode": "refine", "topic": "原文", "source_content": source}, "refine")
    refine = _read(refine_run / "content.json")["mode_data"]["refinement"]
    assert refine["profile"] == "refine"
    assert any("核心主张保持不变" in item["text"] for item in refine["source_claims"])
    assert refine["after_score"] > refine["before_score"]
    _, article_run = _run(tmp_path, {"mode": "article-friendly", "topic": "原文", "source_content": source}, "article")
    article = _read(article_run / "content.json")["mode_data"]["refinement"]
    assert article["profile"] == "article-friendly"
    assert article["source_claims"] == refine["source_claims"]
    assert any("证据补充" in note for note in article["change_notes"])


def test_source_snapshot_is_safe_and_replayable(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("需要保留的核心 claim。", encoding="utf-8")
    brief = {"mode": "refine", "topic": "安全快照", "source_content": {"path": "source.md"}}
    result, run = _run(tmp_path, brief, "first")
    normalized = _read(run / "input" / "content-brief.json")
    assert normalized["source_content"]["path"] == "source.md"
    replay = content(run / "input" / "content-brief.json", tmp_path / "replay")
    assert replay["run_id"] == result["run_id"]
    assert (Path(replay["output"]) / "input" / "source.md").read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(ValueError, match="stay relative"):
        content(_write(tmp_path, {"mode": "refine", "topic": "escape", "source_content": {"path": f"../{outside.name}"}}, "escape.json"), tmp_path / "escape-runs")


def test_source_symlink_is_rejected(tmp_path):
    target = tmp_path / "target.md"
    target.write_text("claim", encoding="utf-8")
    (tmp_path / "link.md").symlink_to(target)
    brief = _write(tmp_path, {"mode": "refine", "topic": "link", "source_content": {"path": "link.md"}})
    with pytest.raises(ValueError, match="unsafe"):
        content(brief, tmp_path / "runs")


def test_html_escapes_user_text_and_has_sticky_print_navigation(tmp_path):
    attack = '<script>alert("x")</script><img src=x onerror=alert(1)>\n# injected-heading'
    _, run = _run(tmp_path, {"mode": "title", "topic": attack})
    rendered = (run / "content.html").read_text(encoding="utf-8")
    assert attack not in rendered
    assert "&lt;script&gt;" in rendered
    assert "position:sticky" in rendered
    assert "@media print" in rendered
    assert "内容主体" in rendered and "补充说明与参考来源" in rendered
    assert "http://" not in rendered and "https://" not in rendered
    markdown = (run / "content.md").read_text(encoding="utf-8")
    assert markdown.count("\n# ") == 2


def test_optional_renderers_create_valid_files_when_available(tmp_path):
    pytest.importorskip("docx")
    if importlib.util.find_spec("weasyprint") is None and importlib.util.find_spec("reportlab") is None:
        pytest.skip("no PDF renderer")
    _, run = _run(tmp_path, {"mode": "title", "topic": "渲染", "desired_formats": ["docx", "pdf"]})
    assert zipfile.is_zipfile(run / "content.docx")
    assert (run / "content.pdf").read_bytes().startswith(b"%PDF")
    manifest = _read(run / "run-manifest.json")
    assert "content.docx" in manifest["artifacts"] and "content.pdf" in manifest["artifacts"]


def test_missing_optional_renderers_degrade_explicitly(tmp_path, monkeypatch):
    real_import = importlib.import_module

    def unavailable(name, package=None):
        if name in {"docx", "weasyprint", "reportlab.pdfgen.canvas"}:
            raise ModuleNotFoundError(name)
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", unavailable)
    _, run = _run(tmp_path, {"mode": "title", "topic": "降级", "desired_formats": ["docx", "pdf"]})
    assert not (run / "content.docx").exists() and not (run / "content.pdf").exists()
    quality = _read(run / "quality-report.json")
    assert quality["status"] == "passed-with-warnings"
    assert any("DOCX renderer" in item for item in quality["warnings"])
    assert any("PDF renderer" in item for item in quality["warnings"])
    assert _read(run / "run-manifest.json")["status"] == "completed-with-warnings"


def test_artifact_bus_failure_does_not_publish_partial_run(tmp_path, monkeypatch):
    brief = _write(tmp_path, {"mode": "title", "topic": "atomic"})

    def fail_publish(self, expected_files):
        raise RuntimeError("simulated publish failure")

    monkeypatch.setattr(ArtifactBus, "publish", fail_publish)
    with pytest.raises(RuntimeError, match="simulated"):
        content(brief, tmp_path / "runs")
    assert list((tmp_path / "runs").iterdir()) == []


def test_core_artifacts_and_manifest_exact_file_set(tmp_path):
    result, run = _run(tmp_path, {"mode": "explainer", "topic": "产物"})
    expected = {
        "input/content-brief.json",
        "content-spec.json",
        "content.json",
        "content.md",
        "content.html",
        "evidence-ledger.json",
        "quality-report.json",
        "run-manifest.json",
    }
    actual = {path.relative_to(run).as_posix() for path in run.rglob("*") if path.is_file()}
    assert actual == expected
    manifest = _read(run / "run-manifest.json")
    assert set(manifest["artifacts"]) == expected - {"run-manifest.json"}
    assert run.parent.name == "runs" and run.name == result["run_id"]


def test_strict_contract_limits_and_cli_json_error(tmp_path, capsys):
    with pytest.raises(ValueError, match="unknown fields"):
        validate_content_brief({"mode": "title", "topic": "x", "unexpected": True})
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (MAX_INPUT_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds"):
        content(oversized, tmp_path / "runs")
    bad = _write(tmp_path, {"mode": "refine", "topic": "missing source"}, "bad.json")
    assert main(["content", "--input", str(bad), "--output", str(tmp_path / "cli-runs")]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["status"] == "error"
