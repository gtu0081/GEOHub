#!/usr/bin/env python3
"""Thin deterministic entry point for the geo-content skill."""

import sys

from yao_geo.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["content", *sys.argv[1:]]))
