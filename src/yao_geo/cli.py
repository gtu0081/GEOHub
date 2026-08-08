from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .discover import discover
from .router import route


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yao-geo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    route_parser = subparsers.add_parser("route", help="Route a GEO request")
    route_parser.add_argument("--text", required=True, help="Natural-language request")

    discover_parser = subparsers.add_parser("discover", help="Generate discover artifacts")
    discover_parser.add_argument("--input", required=True, type=Path, help="GEO brief JSON")
    discover_parser.add_argument("--output", required=True, type=Path, help="Runs root directory")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "route":
            result = route(args.text)
        else:
            result = discover(args.input, args.output)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
