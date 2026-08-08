#!/usr/bin/env python3
"""Thin deterministic entry point for the geo-discover skill."""

import sys

from yao_geo.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["discover", *sys.argv[1:]]))
