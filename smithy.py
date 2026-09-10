#!/usr/bin/env python3
"""Smithy: agent-native capability forging for AshFall.

Smithy does not import a pretrained model. It consumes AshFall evidence,
creates candidate learning tasks/architectures, trains small candidates, and
records every artifact so the four agents share one forge history.

The first task is deliberately unsupervised: learn a compact representation
of AshFall system-state observations. This gives the NPU a locally generated
perception workload without pretending that the NPU itself is a trainer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from ashfall_store import DEFAULT_STORE, append_evidence, read_evidence

AGENTS = ("jarvis", "aaron", "george", "leeloo")
SCHEMA = "smithy.forge.v1"


def _hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _system_rows(limit: int = 10000) -> list[dict[str, Any]]:
    rows = []
    for event in read_evidence(limit=limit):
        if event.get("observation_kind") != "system":
            continue
        obs = event.get("observation")
        if isinstance(obs, dict) and obs.get("schema") == "ashfall.perception.system.v1":
            rows.append(obs)
    return rows


def vectorize(obs: dict[str, Any]) -> np.ndarray:
    """Stable numeric system-state vector used by the first Smithy task."""
    cpu = obs.get("cpu", {})
    mem = obs.get("memory", {})
    proc = obs.get("process", {})
    therm = obs.get("thermal", [])
    thermal = [float(x.get("celsius", 0.0)) for x in therm if isinstance(x, dict)]
    net = obs.get("network", {})
    up = sum(bool(v.get("is_up")) for v in net.values() if isinstance(v, dict))
    speed = sum(float(v.get("speed_mbps", 0)) for v in net.values() if isinstance(v, dict))

    values = [
        float(cpu.get("load1", 0)), float(cpu.get("load5", 0)), float(cpu.get("load15", 0)),
        float(mem.get("ram_used", 0)), float(mem.get("ram_available", 0)),
        float(mem.get("swap_used", 0)), float(proc.get("count", 0)),
        float(proc.get("cpu_percent", 0)), float(np.mean(thermal) if thermal else 0),
        float(np.max(thermal) if thermal else 0), float(up), float(speed),
    ]
    return np.asarray(values, dtype=np.float32)


def dataset(limit: int = 10000) -> tuple[np.ndarray, dict[str, Any]]:
    rows = _system_rows(limit)
    if not rows:
        raise RuntimeError("No AshFall system observations found. Run: python ashfall_tool.py system")
    x = np.stack([vectorize(r) for r in rows])
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std < 1e-6] = 1.0
    z = (x - mean) / std
    meta = {"rows": int(len(rows)), "features": int(x.shape[1]), "mean": mean.tolist(), "std": std.tolist()}
    return z, meta


def propose(seed: int | None = None) -> dict[str, Any]:
    """Have each role contribute a bounded proposal; JARVIS records consensus."""
    if seed is None:
        seed = int(time.time())
    rng = np.random.default_rng(seed)
    proposals = {
        "jarvis": {"objective": "compact_system_state_representation", "hidden": int(rng.choice([8, 12, 16]))},
        "aaron": {"objective": "minimize_npu_latency", "hidden": int(rng.choice([8, 16]))},
        "george": {"objective": "bounded_and_reproducible", "activation": "relu"},
        "leeloo": {"objective": "stable_generalization", "validation_split": 0.2},
    }
    # Conservative consensus: smallest hidden size satisfying all constraints.
    hidden = min(int(p.get("hidden", 16)) for p in proposals.values() if "hidden" in p)
    spec = {
        "schema": "smithy.candidate.v1",
        "task": "ashfall_system_autoencoder",
        "input_features": 12,
        "hidden": hidden,
        "activation": "relu",
        "output_features": 12,
        "seed": seed,
        "agents": proposals,
        "constraints": {"external_pretrained_model": False, "autonomous_control": False},
    }
    evidence_id = append_evidence({
        "kind": "smithy_proposal",
        "producer": "smithy",
        "visibility": "shared",
        "audience": list(AGENTS),
        "candidate": spec,
    })
    return {"evidence_id": evidence_id, "candidate": spec}


def train(spec: dict[str, Any], epochs: int = 250, lr: float = 0.01) -> dict[str, Any]:
    """Train a tiny autoencoder using only AshFall observations."""
    x, meta = dataset()
    n = len(x)
    split = max(1, int(n * 0.8))
    rng = np.random.default_rng(int(spec["seed"]))
    order = rng.permutation(n)
    tr, va = x[order[:split]], x[order[split:] or order[:1]]
    d, h = x.shape[1], int(spec["hidden"])
    w1 = rng.normal(0, 0.15, (d, h)).astype(np.float32)
    b1 = np.zeros(h, np.float32)
    w2 = rng.normal(0, 0.15, (h, d)).astype(np.float32)
    b2 = np.zeros(d, np.float32)

    for _ in range(epochs):
        z = tr @ w1 + b1
        a = np.maximum(z, 0)
        y = a @ w2 + b2
        e = y - tr
        gy = (2.0 / len(tr)) * e
        gw2 = a.T @ gy
        gb2 = gy.sum(0)
        ga = gy @ w2.T
        gz = ga * (z > 0)
        gw1 = tr.T @ gz
        gb1 = gz.sum(0)
        w2 -= lr * gw2; b2 -= lr * gb2
        w1 -= lr * gw1; b1 -= lr * gb1

    def mse(a: np.ndarray) -> float:
        q = np.maximum(a @ w1 + b1, 0) @ w2 + b2
        return float(np.mean((q - a) ** 2))

    artifact = {
        "schema": "smithy.model.v1",
        "candidate": spec,
        "trained_at": time.time(),
        "dataset": meta,
        "train_mse": mse(tr),
        "validation_mse": mse(va),
        "weights": {"w1": w1.tolist(), "b1": b1.tolist(), "w2": w2.tolist(), "b2": b2.tolist()},
    }
    artifact["model_id"] = _hash(artifact)
    evidence_id = append_evidence({
        "kind": "smithy_model",
        "producer": "smithy",
        "visibility": "shared",
        "audience": list(AGENTS),
        "model": artifact,
    })
    artifact["evidence_id"] = evidence_id
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Smithy agent-native model forge")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("propose"); p.add_argument("--seed", type=int)
    d = sub.add_parser("dataset"); d.add_argument("--limit", type=int, default=10000)
    t = sub.add_parser("train"); t.add_argument("--candidate", required=True, help="JSON candidate file")
    args = parser.parse_args()

    if args.command == "propose":
        print(json.dumps(propose(args.seed), indent=2))
        return 0
    if args.command == "dataset":
        x, meta = dataset(args.limit)
        print(json.dumps({"schema": "smithy.dataset.v1", "metadata": meta, "shape": list(x.shape)}, indent=2))
        return 0
    if args.command == "train":
        spec = json.loads(Path(args.candidate).read_text())
        print(json.dumps(train(spec), indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
