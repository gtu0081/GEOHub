import json
import os
import site
import subprocess
import sys
from pathlib import Path

from yao_geo.paths import repository_root


def _run(arguments, *, cwd, env):
    return subprocess.run(
        arguments,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_offline_wheel_install_runs_diagnose_outside_repository(tmp_path):
    root = repository_root()
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--no-index",
            "--wheel-dir",
            str(wheels),
        ],
        cwd=root,
        env=environment,
    )
    wheel = next(wheels.glob("yao_geo-0.1.0-*.whl"))
    virtualenv = tmp_path / "venv"
    _run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(virtualenv)],
        cwd=tmp_path,
        env=environment,
    )
    python = virtualenv / "bin" / "python"
    console = virtualenv / "bin" / "yao-geo"
    dependency_site = next(
        Path(candidate).resolve()
        for candidate in site.getsitepackages()
        if (Path(candidate) / "jsonschema").is_dir()
        and (Path(candidate) / "yaml").is_dir()
    )
    child_site = Path(
        _run(
            [str(python), "-c", "import site; print(site.getsitepackages()[0])"],
            cwd=tmp_path,
            env=environment,
        ).stdout.strip()
    )
    (child_site / "yao_geo_test_dependencies.pth").write_text(
        f"{dependency_site}\n",
        encoding="utf-8",
    )
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--ignore-installed",
            str(wheel),
        ],
        cwd=tmp_path,
        env=environment,
    )

    outside = tmp_path / "outside"
    outside.mkdir()
    data_check = _run(
        [
            str(python),
            "-c",
            (
                "import sys; from pathlib import Path; import yao_geo; "
                "prefix=Path(sys.prefix).resolve(); "
                "assert Path(yao_geo.__file__).resolve().is_relative_to(prefix); "
                "assert (prefix/'share/yao-geo/registry/skills.yaml').is_file(); "
                "assert (prefix/'share/yao-geo/skills/geo-diagnose/SKILL.md').is_file(); "
                "print(prefix)"
            ),
        ],
        cwd=outside,
        env=environment,
    )
    assert data_check.stdout.strip() == str(virtualenv.resolve())

    runs_root = tmp_path / "installed-runs"
    completed = _run(
        [
            str(console),
            "diagnose",
            "--input",
            str(root / "tests" / "fixtures" / "diagnosis-page.json"),
            "--output",
            str(runs_root),
        ],
        cwd=outside,
        env=environment,
    )
    payload = json.loads(completed.stdout)
    run = Path(payload["output"])
    expected = {
        "input/diagnosis-brief.json",
        "input/sources/source-html-1.html",
        "diagnosis.json",
        "report.md",
        "evidence-ledger.json",
        "query-map.json",
        "opportunity-map.json",
        "quality-report.json",
        "run-manifest.json",
    }
    actual = {
        path.relative_to(run).as_posix()
        for path in run.rglob("*")
        if path.is_file()
    }
    assert actual == expected
    manifest = json.loads((run / "run-manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["artifacts"]) == expected - {"run-manifest.json"}
