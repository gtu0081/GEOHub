#!/usr/bin/env python3
from __future__ import annotations

import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
OUTPUT = ROOT / "dist" / f"yao-geo-{VERSION}.zip"


def trusted_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    files: list[Path] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe tracked path: {relative}")
        path = root / relative
        mode = path.lstat().st_mode
        if path.is_symlink() or not stat.S_ISREG(mode):
            raise ValueError(f"tracked package entry must be a regular file: {relative}")
        files.append(relative)
    return sorted(files, key=lambda path: path.as_posix())


def build_archive(root: Path, output: Path) -> list[Path]:
    files = trusted_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            path = root / relative
            info = zipfile.ZipInfo(
                f"yao-geo-{version}/{relative.as_posix()}",
                date_time=(2026, 8, 8, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return files


def main() -> int:
    subprocess.run([sys.executable, "scripts/verify_repository.py"], cwd=ROOT, check=True)
    build_archive(ROOT, OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
