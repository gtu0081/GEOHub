#!/usr/bin/env python3
"""Thin entry point for the geo-diagnose skill."""

import sys

from yao_geo.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["diagnose", *sys.argv[1:]]))
