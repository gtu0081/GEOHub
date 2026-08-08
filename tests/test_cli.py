import json
from pathlib import Path

from yao_geo.cli import main


def test_route_cli_prints_json(capsys):
    assert main(["route", "--text", "query research"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["skill_id"] == "geo-discover"


def test_discover_cli_prints_summary(tmp_path, capsys):
    fixture = Path(__file__).parent / "fixtures" / "brief.json"
    runs_root = tmp_path / "runs"
    assert main(["discover", "--input", str(fixture), "--output", str(runs_root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query_count"] == 4
    assert Path(payload["output"]).parent == runs_root
    assert Path(payload["output"]).name.startswith("run-")


def test_route_cli_rejects_empty_text(capsys):
    assert main(["route", "--text", "   "]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["status"] == "error"
