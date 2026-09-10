#!/usr/bin/env python3
"""Command-line tool interface for the AshFall perception layer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ashfall_perception import (
    observe_image_and_publish,
    observe_system_and_publish,
    tool_metadata,
)
from ashfall_store import DEFAULT_STORE, read_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="AshFall perception tool")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("info", help="show tool contract")
    sub.add_parser("system", help="collect and publish a read-only system frame")
    image = sub.add_parser("vision", help="extract and publish image features")
    image.add_argument("path", type=Path)
    shared = sub.add_parser("shared", help="read the canonical shared evidence")
    shared.add_argument("--limit", type=int, default=20)

    args = parser.parse_args()
    if args.command == "info":
        print(json.dumps(tool_metadata(), indent=2))
        return 0
    if args.command == "system":
        evidence_id, obs = observe_system_and_publish()
        print(json.dumps({"evidence_id": evidence_id, "observation": obs}, indent=2, default=str))
        return 0
    if args.command == "vision":
        if not args.path.is_file():
            parser.error(f"image not found: {args.path}")
        evidence_id, obs = observe_image_and_publish(args.path)
        print(json.dumps({"evidence_id": evidence_id, "observation": obs}, indent=2, default=str))
        return 0
    if args.command == "shared":
        print(json.dumps({"schema": "ashfall.shared.v1", "store": str(DEFAULT_STORE), "evidence": read_evidence(limit=max(0, args.limit))}, indent=2, default=str))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
