#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("geo", "geo-discover", "geo-diagnose", "geo-content")


def portable_text(value: str, meta_root: Path) -> str:
    replacements = ((str(ROOT.resolve()) + "/", ""), (str(meta_root.resolve()) + "/", "<yao-meta-root>/"), (str(Path(sys.executable).resolve()), "python3"))
    for source, replacement in replacements:
        value = value.replace(source, replacement)
    return value


def execute(command: list[str], meta_root: Path) -> dict:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    return {"command": [portable_text(part, meta_root) for part in command], "exit_code": result.returncode, "status": "pass" if result.returncode == 0 else "fail", "stdout_tail": portable_text(result.stdout[-2000:], meta_root), "stderr_tail": portable_text(result.stderr[-2000:], meta_root)}


def sanitize_generated_reports(paths: list[Path], meta_root: Path) -> None:
    for path in paths:
        if path.is_file() and path.suffix in {".json", ".md", ".html"}:
            text = path.read_text(encoding="utf-8")
            portable = portable_text(text, meta_root)
            if portable != text:
                path.write_text(portable, encoding="utf-8")


def current_source_digest() -> str:
    paths = [ROOT / "scripts" / "run_yao_meta_gates.py"]
    paths.extend(path for path in (ROOT / "registry").rglob("*") if path.is_file())
    for skill_id in SKILLS:
        paths.extend(path for path in (ROOT / "skills" / skill_id).rglob("*") if path.is_file() and "reports" not in path.parts and "__pycache__" not in path.parts)
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def verify_existing() -> int:
    report_path = ROOT / "reports" / "yao-meta-gates.json"
    if not report_path.is_file():
        print("existing yao-meta gate report is missing", file=sys.stderr)
        return 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    failures = []
    if report.get("status") != "pass" or report.get("failed_commands") != 0:
        failures.append("recorded gate status is not pass")
    if len(report.get("commands", [])) < 53 or any(item.get("exit_code") != 0 for item in report.get("commands", [])):
        failures.append("recorded deterministic command evidence is incomplete")
    if report.get("source_digest") != current_source_digest():
        failures.append("recorded source digest is stale")
    machine_markers = ("/" + "Users/", "AI Coding/03-Development/Skills", "C:" + "\\Users\\")
    surfaces = list((ROOT / "reports").rglob("*.json")) + list((ROOT / "reports").rglob("*.md")) + list((ROOT / "reports").rglob("*.html"))
    if any(marker in path.read_text(encoding="utf-8") for path in surfaces for marker in machine_markers):
        failures.append("machine-local path remains in public reports")
    if failures:
        print(json.dumps({"status": "fail", "failures": failures}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({"status": "pass", "commands": len(report["commands"]), "source_digest": report["source_digest"]}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta-root", type=Path)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing:
        return verify_existing()
    if args.meta_root is None:
        parser.error("--meta-root is required unless --verify-existing is used")
    yao = args.meta_root.resolve() / "scripts" / "yao.py"
    if not yao.is_file():
        raise SystemExit(f"yao-meta CLI not found: {yao}")
    out = ROOT / "reports" / "yao-meta"
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for skill_id in SKILLS:
        skill = ROOT / "skills" / skill_id
        prefix = out / skill_id
        frontmatter = yaml.safe_load((skill / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1])
        commands = [
            [sys.executable, str(yao), "validate", str(skill), "--require-manifest"],
            [sys.executable, str(args.meta_root.resolve() / "scripts" / "trigger_eval.py"), "--description", frontmatter["description"], "--cases", str(skill / "evals" / "trigger_cases.json"), "--semantic-config", str(skill / "evals" / "semantic_config.json"), "--threshold", "0.2"],
            [sys.executable, str(yao), "skill-ir", str(skill), "--output-json", str(skill / "reports" / "skill-ir.json")],
            [sys.executable, str(yao), "skill-ir", str(skill), "--output-json", str(prefix) + "-skill-ir.json"],
            [sys.executable, str(yao), "output-eval", "--cases", str(skill / "evals" / "output" / "cases.jsonl"), "--output-json", str(prefix) + "-output-eval.json", "--output-md", str(prefix) + "-output-eval.md", "--blind-pack-json", str(prefix) + "-blind-pack.json", "--blind-pack-md", str(prefix) + "-blind-pack.md", "--blind-answer-key-json", str(prefix) + "-blind-answer-key.json"],
            [sys.executable, str(yao), "trust", str(skill), "--output-json", str(prefix) + "-trust.json", "--output-md", str(prefix) + "-trust.md"],
            [sys.executable, str(yao), "review-studio", str(skill), "--output-json", str(prefix) + "-review-studio.json", "--output-html", str(prefix) + "-review-studio.html"],
        ]
        for target in ("generic", "openai", "claude"):
            commands.append([sys.executable, str(yao), "compile-skill", str(skill), "--target", target, "--output-json", str(prefix) + f"-compiled-{target}.json", "--output-md", str(prefix) + f"-compiled-{target}.md"])
            commands.append([sys.executable, str(yao), "conformance", str(skill), "--target", target, "--output-json", str(prefix) + f"-conformance-{target}.json", "--output-md", str(prefix) + f"-conformance-{target}.md"])
        results.extend({"skill_id": skill_id, **execute(command, args.meta_root)} for command in commands)
    atlas_command = [sys.executable, str(yao), "skill-atlas", "--workspace-root", str(ROOT / "skills"), "--report-json", str(ROOT / "reports" / "skill-atlas.json"), "--report-html", str(ROOT / "reports" / "skill-atlas.html")]
    results.append({"skill_id": "suite", **execute(atlas_command, args.meta_root)})
    generated = list(out.rglob("*")) + [ROOT / "reports" / "skill-atlas.json", ROOT / "reports" / "skill-atlas.html"]
    sanitize_generated_reports(generated, args.meta_root)
    failures = [item for item in results if item["exit_code"] != 0]
    report = {"status": "pass" if not failures else "fail", "commands": results, "failed_commands": len(failures), "source_digest": current_source_digest(), "evidence": {"deterministic_gates": "recorded", "human_blind_review": "missing evidence", "real_platform_benchmark": "missing evidence", "commercial_legal_review": "missing evidence"}, "note": "Any nonzero yao-meta command fails this gate; missing external evidence remains explicit."}
    (ROOT / "reports" / "yao-meta-gates.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# yao-meta Gates", "", f"Status: **{report['status']}**", "", f"Commands: {len(results)}; nonzero: {len(failures)}.", "", "Human blind review, real-platform benchmark, and commercial legal review: **missing evidence**.", "", "| Skill | Command | Exit | Status |", "| --- | --- | ---: | --- |"]
    for item in results:
        lines.append(f"| {item['skill_id']} | `{' '.join(item['command'][2:4])}` | {item['exit_code']} | {item['status']} |")
    (ROOT / "reports" / "yao-meta-gates.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "commands": len(results), "nonzero": len(failures)}, indent=2))
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
