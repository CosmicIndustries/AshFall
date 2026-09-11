#!/usr/bin/env python3
"""Agent-facing runtime for using Smithy-generated models when useful.

This is an interface for the existing agents, not an agent simulator.
JARVIS/AARON/GEORGE/LEELOO remain independent agents and decide whether a
Smithy artifact is useful. This module supplies discovery and execution.

The first Smithy model is an AshFall system-state autoencoder. It can be used
as a compact state encoder/reconstructor and as a reconstruction-error signal.
The model never becomes an autonomous decision-maker or host controller.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np

from ashfall_store import append_evidence, read_evidence
from smithy import vectorize

AGENTS = ("jarvis", "aaron", "george", "leeloo")
DEFAULT_MODEL_DIR = Path(os.environ.get("SMITHY_MODEL_DIR", "~/.local/share/ashfall/smithy/models")).expanduser()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _latest_models() -> list[dict[str, Any]]:
    rows = []
    for event in read_evidence(limit=10000):
        if event.get("kind") != "smithy_model":
            continue
        model = event.get("model")
        if isinstance(model, dict) and model.get("schema") == "smithy.model.v1":
            rows.append({"evidence": event, "model": model})
    rows.sort(key=lambda item: float(item["model"].get("trained_at", 0)))
    return rows


def available() -> dict[str, Any]:
    """Return models the agents can inspect without selecting one for them."""
    models = []
    for item in _latest_models():
        model = item["model"]
        models.append({
            "model_id": model.get("model_id"),
            "task": model.get("candidate", {}).get("task"),
            "hidden": model.get("candidate", {}).get("hidden"),
            "trained_at": model.get("trained_at"),
            "train_mse": model.get("train_mse"),
            "validation_mse": model.get("validation_mse"),
            "evidence_id": item["evidence"].get("evidence_id"),
        })
    return {
        "schema": "smithy.agent.capabilities.v1",
        "models": models,
        "agents": list(AGENTS),
        "policy": {
            "agent_decides_use": True,
            "model_is_not_agent": True,
            "mutates_host": False,
            "autonomous_control": False,
        },
    }


def _load_model(model_path: Path) -> dict[str, Any]:
    artifact = json.loads(model_path.read_text(encoding="utf-8"))
    if artifact.get("schema") != "smithy.model.v1":
        raise ValueError("Not a Smithy model artifact")
    return artifact


def _normalized_input(artifact: dict[str, Any], observation: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    raw = vectorize(observation).astype(np.float32)
    meta = artifact.get("dataset", {})
    mean = np.asarray(meta.get("mean", []), dtype=np.float32)
    std = np.asarray(meta.get("std", []), dtype=np.float32)
    if len(mean) != len(raw) or len(std) != len(raw):
        raise ValueError("Model dataset normalization metadata does not match input features")
    std = np.where(np.abs(std) < 1e-6, 1.0, std)
    return raw, (raw - mean) / std


def _cpu_infer(artifact: dict[str, Any], z: np.ndarray) -> np.ndarray:
    w = artifact["weights"]
    w1 = np.asarray(w["w1"], dtype=np.float32)
    b1 = np.asarray(w["b1"], dtype=np.float32)
    w2 = np.asarray(w["w2"], dtype=np.float32)
    b2 = np.asarray(w["b2"], dtype=np.float32)
    hidden = np.maximum(z @ w1 + b1, 0.0)
    return hidden @ w2 + b2


def _npu_infer(rknn_path: Path, z: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    try:
        from rknnlite.api import RKNNLite
    except ImportError as exc:
        raise RuntimeError("RKNNLite is required for --accelerator npu") from exc
    r = RKNNLite()
    try:
        ret = r.load_rknn(str(rknn_path))
        if ret != 0:
            raise RuntimeError(f"RKNNLite load failed: {ret}")
        ret = r.init_runtime()
        if ret != 0:
            raise RuntimeError(f"RKNNLite init_runtime failed: {ret}")
        result = r.inference(inputs=[z.astype(np.float32)])
        output = np.asarray(result[0], dtype=np.float32)
        return output, {"rknn": str(rknn_path), "runtime": "rknnlite", "output_shapes": [list(np.asarray(x).shape) for x in result]}
    finally:
        r.release()


def _latest_system_observation() -> tuple[str, dict[str, Any]]:
    rows = []
    for event in read_evidence(limit=10000):
        if event.get("observation_kind") != "system":
            continue
        obs = event.get("observation")
        if isinstance(obs, dict) and obs.get("schema") == "ashfall.perception.system.v1":
            rows.append(event)
    if not rows:
        raise RuntimeError("No AshFall system observation found")
    event = rows[-1]
    return str(event.get("evidence_id")), event["observation"]


def use(agent: str, model_path: Path, accelerator: str = "cpu", rknn_path: Path | None = None,
        observation_evidence_id: str | None = None, reason: str = "agent-requested evaluation") -> dict[str, Any]:
    """Execute a Smithy model for an agent and publish the resulting evidence."""
    if agent not in AGENTS:
        raise ValueError(f"Unknown agent: {agent}")
    artifact = _load_model(model_path)
    if observation_evidence_id:
        matched = [e for e in read_evidence(limit=10000) if e.get("evidence_id") == observation_evidence_id]
        if not matched:
            raise ValueError(f"Unknown evidence_id: {observation_evidence_id}")
        obs = matched[0].get("observation")
        if not isinstance(obs, dict):
            raise ValueError("Requested evidence does not contain an AshFall observation")
    else:
        observation_evidence_id, obs = _latest_system_observation()

    raw, z = _normalized_input(artifact, obs)
    t0 = time.perf_counter()
    if accelerator == "npu":
        if rknn_path is None:
            raise ValueError("--rknn is required for --accelerator npu")
        reconstruction, accel_meta = _npu_infer(rknn_path, z.reshape(1, -1))
    elif accelerator == "cpu":
        reconstruction = _cpu_infer(artifact, z.reshape(1, -1))
        accel_meta = {"runtime": "numpy"}
    else:
        raise ValueError("accelerator must be cpu or npu")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    reconstruction = np.asarray(reconstruction, dtype=np.float32).reshape(z.shape)
    mse = float(np.mean((reconstruction - z) ** 2))
    payload = {
        "kind": "smithy_model_use",
        "producer": "smithy_agent_runtime",
        "visibility": "shared",
        "audience": list(AGENTS),
        "requested_by": agent,
        "reason": reason,
        "model_id": artifact.get("model_id"),
        "model_sha256": _sha256(model_path),
        "model_path": str(model_path),
        "observation_evidence_id": observation_evidence_id,
        "task": artifact.get("candidate", {}).get("task"),
        "accelerator": accelerator,
        "latency_ms": float(elapsed_ms),
        "reconstruction_mse": mse,
        "input_features": int(z.size),
        "output_shape": list(reconstruction.shape),
        "normalization": "dataset_zscore",
        "sample_mean": raw.tolist(),
        "runtime": accel_meta,
        "policy": {
            "agent_selects_use": True,
            "model_is_not_agent": True,
            "mutates_host": False,
            "changes_frequency": False,
            "autonomous_control": False,
        },
    }
    payload["evidence_id"] = append_evidence(payload)
    return payload


def main() -> int:
    p = argparse.ArgumentParser(description="Agent-facing Smithy model runtime")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("available", help="list Smithy models recorded in shared evidence")
    u = sub.add_parser("use", help="execute a selected Smithy model for an agent")
    u.add_argument("--agent", required=True, choices=AGENTS)
    u.add_argument("--model", required=True)
    u.add_argument("--accelerator", choices=("cpu", "npu"), default="cpu")
    u.add_argument("--rknn")
    u.add_argument("--observation-evidence-id")
    u.add_argument("--reason", default="agent-requested evaluation")
    args = p.parse_args()
    if args.command == "available":
        print(json.dumps(available(), indent=2))
        return 0
    if args.command == "use":
        result = use(args.agent, Path(args.model).expanduser(), args.accelerator,
                     Path(args.rknn).expanduser() if args.rknn else None,
                     args.observation_evidence_id, args.reason)
        print(json.dumps(result, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
