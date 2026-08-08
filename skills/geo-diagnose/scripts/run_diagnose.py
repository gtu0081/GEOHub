#!/usr/bin/env python3
"""Thin entry point for the geo-diagnose skill."""

import sys
from pathlib import Path

for candidate in (Path(__file__).resolve().parents[1] / "src", Path(__file__).resolve().parents[3] / "src"):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break

from yao_geo.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["diagnose", *sys.argv[1:]]))
