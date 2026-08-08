#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
REPORTS = ROOT / "reports"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
EXPECTED = {
    f"yao-geo-source-{VERSION}.zip",
    f"yao-geo-unified-community-{VERSION}.zip",
    *(f"{skill}-community-{VERSION}.zip" for skill in ("geo", "geo-discover", "geo-diagnose", "geo-content")),
    f"yao-geo-codex-community-{VERSION}.zip",
    f"yao-geo-claude-community-{VERSION}.zip",
}
REQUIRED_LEGAL = {"VERSION", "LICENSE", "LICENSE-SCOPE.md", "COMMERCIAL-LICENSING.md", "THIRD_PARTY_NOTICES.md"}
FORBIDDEN_NAMES = re.compile(r"(?:^|/)(?:\.env|id_rsa|credentials|secrets?)(?:\.|/|$)", re.I)
FORBIDDEN_CONTENT = (b"BEGIN PRIVATE KEY", b"OPENAI_API_KEY=", b"/Users/", b"C:\\Users\\")
MAX_ARCHIVE_MEMBERS = 4096
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_archive(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS or sum(info.file_size for info in infos) > MAX_ARCHIVE_BYTES:
            raise ValueError(f"archive exceeds verification limits: {path.name}")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate ZIP member in {path.name}")
        for info in infos:
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts or "\\" in info.filename:
                raise ValueError(f"unsafe ZIP member in {path.name}: {info.filename}")
            mode = info.external_attr >> 16
            if mode and (mode & 0o170000) == 0o120000:
                raise ValueError(f"symlink ZIP member in {path.name}: {info.filename}")
            if FORBIDDEN_NAMES.search(info.filename):
                raise ValueError(f"sensitive filename in {path.name}: {info.filename}")
            payload = archive.read(info)
            if info.filename.endswith("scripts/verify_packages.py"):
                payload = b"\n".join(line for line in payload.splitlines() if not line.startswith(b"FORBIDDEN_CONTENT ="))
            if any(marker in payload for marker in FORBIDDEN_CONTENT):
                raise ValueError(f"sensitive or machine-local content in {path.name}: {info.filename}")
        stripped = [name.split("/", 1)[1] if path.name.startswith("yao-geo-source-") and "/" in name else name for name in names]
        members = dict(zip(stripped, infos, strict=True))
        for legal in REQUIRED_LEGAL:
            if legal not in stripped:
                raise ValueError(f"{path.name} missing {legal}")
        skill_count = sum(name.endswith("SKILL.md") for name in names)
        if not path.name.startswith("yao-geo-source-") and skill_count != 1:
            raise ValueError(f"{path.name} must contain exactly one SKILL.md; found {skill_count}")
        skill_ids = ("geo", "geo-discover", "geo-diagnose", "geo-content")
        if path.name.startswith("yao-geo-source-"):
            expected_manifests = {f"skills/{skill_id}/manifest.json": skill_id for skill_id in skill_ids}
        else:
            metadata = json.loads(archive.read(members["PACKAGE-METADATA.json"]))
            if metadata["kind"] == "provider":
                expected_manifests = {"manifest.json": metadata["skill_id"]}
            else:
                expected_manifests = {f"manifests/{skill_id}.json": skill_id for skill_id in skill_ids}
        actual_manifest_paths = {name for name in stripped if name == "manifest.json" or name.startswith("manifests/") or (name.startswith("skills/") and name.endswith("/manifest.json"))}
        if actual_manifest_paths != set(expected_manifests):
            raise ValueError(f"manifest path set mismatch in {path.name}: {sorted(actual_manifest_paths)}")
        observed_names = []
        for manifest_path, skill_id in expected_manifests.items():
            manifest = json.loads(archive.read(members[manifest_path]))
            if manifest.get("name") != skill_id:
                raise ValueError(f"manifest identity mismatch at {manifest_path} in {path.name}")
            observed_names.append(manifest["name"])
            source = json.loads((ROOT / "skills" / skill_id / "manifest.json").read_text(encoding="utf-8"))
            if manifest != source:
                raise ValueError(f"manifest parity failure for {skill_id} in {path.name}")
        if len(observed_names) != len(set(observed_names)):
            raise ValueError(f"duplicate manifest identities in {path.name}")
        if "registry/skills.yaml" not in stripped or "pyproject.toml" not in stripped:
            raise ValueError(f"{path.name} missing runtime registry or pyproject")
    return {"name": path.name, "sha256": sha256(path), "members": len(names), "skill_count": skill_count, "status": "pass"}


def load_packager():
    spec = importlib.util.spec_from_file_location("yao_geo_packager", ROOT / "scripts" / "package.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> int:
    packager = load_packager()
    first = packager.build("all")
    first_hashes = {path.name: sha256(path) for path in first}
    second = packager.build("all")
    second_hashes = {path.name: sha256(path) for path in second}
    if first_hashes != second_hashes:
        raise SystemExit("package verification failed: repeated build hashes differ")
    names = {path.name for path in second}
    if names != EXPECTED:
        raise SystemExit(f"package verification failed: expected {sorted(EXPECTED)}, got {sorted(names)}")
    disk_names = {path.name for path in DIST.glob("*.zip")}
    if disk_names != EXPECTED:
        raise SystemExit(f"package verification failed: unexpected ZIPs in dist: {sorted(disk_names - EXPECTED)}")
    try:
        results = [verify_archive(path) for path in sorted(second)]
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise SystemExit(f"package verification failed: {exc}") from exc
    report = {"status": "pass", "package_count": len(results), "deterministic_repeat": True, "packages": results}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "package-verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Package Verification", "", "Status: **pass**", "", f"Packages: {len(results)}; repeated build hashes: identical.", "", "| Package | SHA-256 | Members | SKILL.md |", "| --- | --- | ---: | ---: |"]
    lines.extend(f"| {item['name']} | `{item['sha256']}` | {item['members']} | {item['skill_count']} |" for item in results)
    (REPORTS / "package-verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "package_count": len(results), "deterministic_repeat": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
