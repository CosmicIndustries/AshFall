#!/usr/bin/env python3
"""AshFall shared evidence store.

AshFall owns observation and anomaly evidence. Every agent may read the same
canonical store; no agent owns or mutates another agent's interpretation.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

DEFAULT_STORE = Path(os.environ.get("ASHFALL_STORE", "~/.local/share/ashfall/evidence.jsonl")).expanduser()


def _stable_id(event: dict[str, Any]) -> str:
    body = json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:24]


def append_evidence(event: dict[str, Any], store: Path = DEFAULT_STORE) -> str:
    store.parent.mkdir(parents=True, exist_ok=True)
    record = dict(event)
    record.setdefault("schema", "ashfall.evidence.v1")
    record.setdefault("observed_at", time.time())
    record.setdefault("evidence_id", _stable_id(record))
    fd, tmp = tempfile.mkstemp(prefix="ashfall-", dir=store.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            if store.exists():
                out.write(store.read_text(encoding="utf-8"))
            out.write(json.dumps(record, sort_keys=True, default=str) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, store)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return record["evidence_id"]


def read_evidence(store: Path = DEFAULT_STORE, limit: int | None = None) -> list[dict[str, Any]]:
    if not store.exists():
        return []
    rows = []
    with store.open("r", encoding="utf-8") as src:
        for line in src:
            if line.strip():
                rows.append(json.loads(line))
    return rows[-limit:] if limit else rows


def write_snapshot(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)
