#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
OUTPUT = ROOT / "dist" / f"yao-geo-{VERSION}.zip"
EXCLUDED_PARTS = {".git", ".pytest_cache", ".venv", "__pycache__", "dist", "runs"}


def main() -> int:
    subprocess.run([sys.executable, "scripts/verify_repository.py"], cwd=ROOT, check=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
        and not any(part.endswith(".egg-info") for part in path.relative_to(ROOT).parts)
    ]
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo(
                f"yao-geo-{VERSION}/{path.relative_to(ROOT).as_posix()}",
                date_time=(2026, 8, 8, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
