import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from yao_geo.cli import main
from yao_geo.paths import repository_root
from yao_geo.registry import RegistryError


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


def test_registry_error_is_json(monkeypatch, capsys):
    def fail_route(_text):
        raise RegistryError("invalid test registry")

    monkeypatch.setattr("yao_geo.cli.route", fail_route)
    assert main(["route", "--text", "GEO"]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload == {"status": "error", "message": "invalid test registry"}


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repository_root() / "src")
    return subprocess.run(
        [sys.executable, "-m", "yao_geo", *arguments],
        cwd=repository_root(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "arguments",
    [
        (),
        ("route",),
        ("route", "--text", "GEO", "--unknown"),
    ],
)
def test_argparse_errors_are_json(arguments):
    result = _run_cli(*arguments)
    assert result.returncode == 2
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["status"] == "error"
    assert payload["message"]


def test_help_remains_standard_stdout():
    result = _run_cli("--help")
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.startswith("usage: yao-geo")
