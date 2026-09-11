#!/usr/bin/env python3
"""Live tool bridge for the real Cosmic agents.

This does not simulate, wrap, or replace an agent. JARVIS/AARON/GEORGE/LEELOO
invoke this tool when they decide a Smithy artifact is useful.

The bridge discovers Smithy model evidence from the shared AshFall store(s),
materializes a selected JSON artifact locally when necessary, and delegates
execution to smithy_agent_runtime.py. It never mutates the host, changes NPU
frequency/governor state, or makes a decision on behalf of an agent.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ashfall_store import read_evidence
import smithy_agent_runtime as runtime

AGENTS = runtime.AGENTS
CACHE = Path(os.environ.get("SMITHY_CACHE_DIR", "/var/lib/ashfall/smithy/models"))


def _store_candidates() -> list[Path]:
    candidates: list[Path] = []
    env = os.environ.get("ASHFALL_STORE")
    if env:
        candidates.append(Path(env).expanduser())
    candidates += [
        Path("/var/lib/ashfall/evidence.jsonl"),
        Path.home() / ".local/share/ashfall/evidence.jsonl",
    ]
    candidates += [Path(p) for p in glob.glob("/home/*/.local/share/ashfall/evidence.jsonl")]
    out: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        s = str(p)
        if s not in seen and p.exists():
            out.append(p)
            seen.add(s)
    return out


def _all_evidence() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for store in _store_candidates():
        try:
            for event in read_evidence(store=store):
                eid = str(event.get("evidence_id", ""))
                key = eid or json.dumps(event, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    events.append(event)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    events.sort(key=lambda e: float(e.get("observed_at", e.get("time", 0)) or 0))
    return events


def _models() -> list[dict[str, Any]]:
    rows = []
    for event in _all_evidence():
        if event.get("kind") != "smithy_model":
            continue
        model = event.get("model")
        if isinstance(model, dict) and model.get("schema") == "smithy.model.v1":
            rows.append({"event": event, "model": model})
    rows.sort(key=lambda row: float(row["model"].get("trained_at", 0)))
    return rows


def _select_model(model_id: str) -> dict[str, Any]:
    models = _models()
    if not models:
        raise RuntimeError("No Smithy model evidence is available in any discovered AshFall store")
    if model_id == "latest":
        return models[-1]
    for row in models:
        if row["model"].get("model_id") == model_id:
            return row
    raise RuntimeError(f"Smithy model not found: {model_id}")


def _materialize(row: dict[str, Any]) -> Path:
    model = row["model"]
    model_id = str(model.get("model_id") or "unknown")
    CACHE.mkdir(parents=True, exist_ok=True)
    destination = CACHE / f"{model_id}.json"
    payload = json.dumps(model, indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix="smithy-model-", dir=CACHE, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, destination)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return destination


def _rknn_candidates(model_id: str) -> list[Path]:
    dirs: list[Path] = []
    env = os.environ.get("SMITHY_RKNN_DIR")
    if env:
        dirs.append(Path(env).expanduser())
    dirs += [
        CACHE,
        Path.home() / ".local/share/ashfall/smithy/models",
        Path("/var/lib/ashfall/smithy/models"),
    ]
    dirs += [Path(p) for p in glob.glob("/home/*/.local/share/ashfall/smithy/models")]
    names = [f"{model_id}.rknn", f"smithy_{model_id}.rknn", "smithy_0001.rknn"]
    result: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        for name in names:
            p = d / name
            if p.is_file() and str(p) not in seen:
                result.append(p)
                seen.add(str(p))
    return result


def available(agent: str | None = None) -> dict[str, Any]:
    data = runtime.available()
    data["bridge"] = {
        "tool": "cosmic_smithy_tool",
        "agent_selects_model": True,
        "agent_selects_use": True,
        "model_is_not_agent": True,
        "discovered_stores": [str(p) for p in _store_candidates()],
        "cache": str(CACHE),
        "rknn_search": "SMITHY_RKNN_DIR or known Smithy artifact directories",
    }
    if agent:
        if agent not in AGENTS:
            raise ValueError(f"Unknown agent: {agent}")
        data["agent"] = agent
    for item in data.get("models", []):
        item["rknn_available"] = bool(_rknn_candidates(str(item.get("model_id"))))
    return data


def use(agent: str, model_id: str, accelerator: str, reason: str,
        observation_evidence_id: str | None = None, rknn: str | None = None) -> dict[str, Any]:
    if agent not in AGENTS:
        raise ValueError(f"Unknown agent: {agent}")
    row = _select_model(model_id)
    model = _materialize(row)

    selected_accel = accelerator
    selected_rknn: Path | None = Path(rknn).expanduser() if rknn else None
    if selected_accel == "auto":
        auto = _rknn_candidates(str(row["model"].get("model_id")))
        if auto:
            selected_accel = "npu"
            selected_rknn = auto[0]
        else:
            selected_accel = "cpu"
    if selected_accel == "npu" and selected_rknn is None:
        candidates = _rknn_candidates(str(row["model"].get("model_id")))
        if not candidates:
            raise RuntimeError("NPU selected but no RKNN artifact was found; pass --rknn or set SMITHY_RKNN_DIR")
        selected_rknn = candidates[0]

    result = runtime.use(
        agent=agent,
        model_path=model,
        accelerator=selected_accel,
        rknn_path=selected_rknn,
        observation_evidence_id=observation_evidence_id,
        reason=reason,
    )
    result["tool"] = "cosmic_smithy_tool"
    result["model_source_evidence_id"] = row["event"].get("evidence_id")
    result["artifact_cache"] = str(model)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Agent-facing Smithy tool")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("available")
    a.add_argument("--agent", choices=AGENTS)
    u = sub.add_parser("use")
    u.add_argument("--agent", required=True, choices=AGENTS)
    u.add_argument("--model", default="latest", help="model_id or latest")
    u.add_argument("--accelerator", choices=("auto", "cpu", "npu"), default="auto")
    u.add_argument("--rknn")
    u.add_argument("--observation-evidence-id")
    u.add_argument("--reason", required=True)
    args = p.parse_args()
    try:
        if args.command == "available":
            print(json.dumps(available(args.agent), indent=2))
        else:
            print(json.dumps(use(args.agent, args.model, args.accelerator, args.reason, args.observation_evidence_id, args.rknn), indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
