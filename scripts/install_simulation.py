#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
REPORTS = ROOT / "reports"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
MAX_ARCHIVE_MEMBERS = 4096
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


def safe_extract(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS or sum(info.file_size for info in infos) > MAX_ARCHIVE_BYTES:
            raise ValueError("archive exceeds safe extraction limits")
        for info in infos:
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts or "\\" in info.filename:
                raise ValueError(f"unsafe archive member: {info.filename}")
            mode = info.external_attr >> 16
            if mode and (mode & 0o170000) == 0o120000:
                raise ValueError(f"symlink archive member: {info.filename}")
        archive.extractall(destination)


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\nstdout: {result.stdout}\nstderr: {result.stderr}")
    return result


def source_smoke(source_zip: Path, temp_root: Path) -> tuple[dict, Path, Path]:
    extracted = temp_root / "source"
    extracted.mkdir()
    safe_extract(source_zip, extracted)
    source_root = next(extracted.iterdir())
    wheelhouse = temp_root / "wheelhouse"
    wheelhouse.mkdir()
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    clean_env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    run([sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "-w", str(wheelhouse), "."], source_root, clean_env)
    wheel = next(wheelhouse.glob("yao_geo-*.whl"))
    venv = temp_root / "venv"
    run([sys.executable, "-m", "venv", str(venv)], temp_root, clean_env)
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([str(python), "-m", "pip", "install", "--no-index", "--find-links", str(wheelhouse), str(wheel)], temp_root, clean_env)
    run([str(python), "-c", "from pathlib import Path; import sys, yao_geo; assert Path(yao_geo.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())"], temp_root, clean_env)
    fixtures = temp_root / "fixtures"
    fixtures.mkdir()
    brief = fixtures / "brief.json"
    brief.write_text(json.dumps({"protocol_version":"1.0.0","brief_id":"synthetic-install","subject":"Synthetic knowledge base","locale":"en","seed_queries":["synthetic query"],"audiences":["tester"],"scenarios":["test"],"competitors":[],"evidence":[]}), encoding="utf-8")
    diagnosis = fixtures / "diagnosis.json"
    diagnosis.write_text(json.dumps({"subject":"Synthetic brand","scope":"brand","evidence":[{"evidence_id":"synthetic","claim":"Synthetic brand has a documented page.","source_uri":"https://example.invalid/synthetic"}]}), encoding="utf-8")
    content = fixtures / "content.json"
    content.write_text(json.dumps({"mode":"explainer","topic":"Synthetic GEO topic","evidence":[],"desired_formats":["markdown","json","html"]}), encoding="utf-8")
    runs = temp_root / "runs"
    commands = [
        [str(python), "-m", "yao_geo", "route", "--text", "Discover AI search questions"],
        [str(python), "-m", "yao_geo", "discover", "--input", str(brief), "--output", str(runs)],
        [str(python), "-m", "yao_geo", "diagnose", "--input", str(diagnosis), "--output", str(runs)],
        [str(python), "-m", "yao_geo", "content", "--input", str(content), "--output", str(runs)],
    ]
    for command in commands:
        run(command, temp_root, clean_env)
    result = {"package": source_zip.name, "wheel": wheel.name, "cli_smokes": ["route", "discover", "diagnose", "content"], "status": "pass"}
    return result, wheelhouse, wheel


def structural_smoke(path: Path, temp_root: Path, wheelhouse: Path, wheel: Path) -> dict:
    destination = temp_root / path.stem
    destination.mkdir()
    safe_extract(path, destination)
    skill_files = list(destination.rglob("SKILL.md"))
    registry = list(destination.rglob("registry/skills.yaml"))
    schemas = list(destination.rglob("schemas/*.schema.json"))
    if len(skill_files) != 1 or not registry or not schemas:
        raise ValueError(f"structure smoke failed for {path.name}")
    skill_text = skill_files[0].read_text(encoding="utf-8")
    referenced = set(re.findall(r"(?:scripts|references)/[A-Za-z0-9_.\-/]+", skill_text))
    missing = [relative for relative in sorted(referenced) if not (skill_files[0].parent / relative).is_file()]
    if missing:
        raise ValueError(f"entry references missing packaged files for {path.name}: {missing}")
    wrappers = list(destination.rglob("scripts/run_*.py"))
    if len(wrappers) != 1:
        raise ValueError(f"expected one wrapper in {path.name}; found {len(wrappers)}")
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    clean_env["PYTHONNOUSERSITE"] = "1"
    venv = temp_root / "package-venvs" / path.stem
    venv.parent.mkdir(exist_ok=True)
    run([sys.executable, "-m", "venv", str(venv)], temp_root, clean_env)
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([str(python), "-m", "pip", "install", "--no-index", "--find-links", str(wheelhouse), str(wheel)], temp_root, clean_env)
    run([str(python), str(wrappers[0]), "--help"], destination, clean_env)
    return {"package": path.name, "entry": str(skill_files[0].relative_to(destination)), "wrapper": str(wrappers[0].relative_to(destination)), "runtime_data": True, "status": "pass"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("all",), default="all")
    parser.parse_args()
    source = DIST / f"yao-geo-source-{VERSION}.zip"
    packages = sorted(path for path in DIST.glob("*.zip") if path.name != source.name)
    with tempfile.TemporaryDirectory(prefix="yao-geo-install-") as raw:
        temp_root = Path(raw)
        source_result, wheelhouse, wheel = source_smoke(source, temp_root)
        structural = [structural_smoke(path, temp_root, wheelhouse, wheel) for path in packages]
    report = {"status": "pass", "target": "all", "source": source_result, "structural_packages": structural, "scratch_retained": False}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "install-simulation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Install Simulation", "", "Status: **pass**", "", f"Fresh wheel/CLI smoke: {', '.join(source_result['cli_smokes'])}.", f"Fresh isolated ZIP wrapper smokes with declared dependencies: {len(structural)}.", "Temporary install roots were removed."]
    (REPORTS / "install-simulation.md").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "source_cli_smokes": len(source_result["cli_smokes"]), "structural_packages": len(structural)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
