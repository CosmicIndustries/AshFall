#!/usr/bin/env python3
"""Smithy -> RKNN -> RKNPU bridge.

This bridge only accepts models produced by Smithy. It does not download or
load a pretrained model. Conversion and inference are explicit operations;
no NPU frequency/governor changes are performed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from ashfall_store import append_evidence

AGENTS = ["jarvis", "aaron", "george", "leeloo"]


def export_onnx(model_path: Path, output_path: Path) -> Path:
    """Export a Smithy MLP artifact to a minimal ONNX graph."""
    try:
        import onnx
        from onnx import TensorProto, helper, numpy_helper
    except ImportError as exc:
        raise RuntimeError("ONNX is required for Smithy export: python -m pip install onnx") from exc

    artifact = json.loads(model_path.read_text())
    if artifact.get("schema") != "smithy.model.v1":
        raise ValueError("Not a Smithy model artifact")
    spec = artifact["candidate"]
    w = artifact["weights"]
    w1 = np.asarray(w["w1"], dtype=np.float32)
    b1 = np.asarray(w["b1"], dtype=np.float32)
    w2 = np.asarray(w["w2"], dtype=np.float32)
    b2 = np.asarray(w["b2"], dtype=np.float32)
    d = int(spec["input_features"])
    h = int(spec["hidden"])

    inp = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, d])
    out = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, d])
    nodes = [
        helper.make_node("Gemm", ["input", "w1", "b1"], ["hidden_pre"], transB=0),
        helper.make_node("Relu", ["hidden_pre"], ["hidden"]),
        helper.make_node("Gemm", ["hidden", "w2", "b2"], ["output"], transB=0),
    ]
    # Gemm computes A * B, while Smithy stores w1 as [d,h] and w2 as [h,d].
    initializers = [
        numpy_helper.from_array(w1, "w1"), numpy_helper.from_array(b1, "b1"),
        numpy_helper.from_array(w2, "w2"), numpy_helper.from_array(b2, "b2"),
    ]
    graph = helper.make_graph(nodes, "smithy_system_autoencoder", [inp], [out], initializers)
    model = helper.make_model(graph, producer_name="Smithy", opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = min(model.ir_version, 9)
    onnx.checker.check_model(model)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, output_path)
    return output_path


def compile_rknn(onnx_path: Path, rknn_path: Path) -> Path:
    """Compile only the locally generated Smithy ONNX artifact to RKNN."""
    try:
        from rknn.api import RKNN
    except ImportError as exc:
        raise RuntimeError("RKNN Toolkit2 is not installed/importable") from exc

    r = RKNN(verbose=False)
    try:
        ret = r.config(target_platform="rk3588")
        if ret != 0:
            raise RuntimeError(f"RKNN config failed: {ret}")
        ret = r.load_onnx(model=str(onnx_path))
        if ret != 0:
            raise RuntimeError(f"RKNN ONNX load failed: {ret}")
        ret = r.build(do_quantization=False)
        if ret != 0:
            raise RuntimeError(f"RKNN build failed: {ret}")
        ret = r.export_rknn(str(rknn_path))
        if ret != 0:
            raise RuntimeError(f"RKNN export failed: {ret}")
    finally:
        r.release()
    return rknn_path


def infer_rknn(rknn_path: Path, model_path: Path, repeat: int = 20) -> dict[str, Any]:
    """Run the Smithy-generated model on the RKNPU and publish evidence."""
    from rknnlite.api import RKNNLite

    artifact = json.loads(model_path.read_text())
    meta = artifact["dataset"]
    x = np.asarray(meta["mean"], dtype=np.float32)[None, :]
    r = RKNNLite()
    try:
        ret = r.load_rknn(str(rknn_path))
        if ret != 0:
            raise RuntimeError(f"RKNNLite load failed: {ret}")
        ret = r.init_runtime()
        if ret != 0:
            raise RuntimeError(f"RKNNLite init_runtime failed: {ret}")
        for _ in range(5):
            r.inference(inputs=[x])
        timings = []
        import time
        for _ in range(repeat):
            t0 = time.perf_counter()
            result = r.inference(inputs=[x])
            timings.append((time.perf_counter() - t0) * 1000.0)
        timings.sort()
        evidence = {
            "kind": "smithy_npu_validation",
            "producer": "smithy",
            "visibility": "shared",
            "audience": AGENTS,
            "model_id": artifact.get("model_id"),
            "rknn": str(rknn_path),
            "latency_ms_median": float(np.median(timings)),
            "latency_ms_p95": float(np.percentile(timings, 95)),
            "fps": float(1000.0 / np.median(timings)),
            "output_shapes": [list(np.asarray(y).shape) for y in result],
            "npu_policy": {"changes_frequency": False, "autonomous_control": False},
        }
        evidence["evidence_id"] = append_evidence(evidence)
        return evidence
    finally:
        r.release()


def main() -> int:
    p = argparse.ArgumentParser(description="Smithy NPU bridge")
    sub = p.add_subparsers(dest="command", required=True)
    e = sub.add_parser("onnx"); e.add_argument("model"); e.add_argument("output")
    c = sub.add_parser("compile"); c.add_argument("onnx"); c.add_argument("output")
    n = sub.add_parser("npu"); n.add_argument("model"); n.add_argument("rknn"); n.add_argument("--repeat", type=int, default=20)
    a = p.parse_args()
    if a.command == "onnx":
        print(export_onnx(Path(a.model), Path(a.output))); return 0
    if a.command == "compile":
        print(compile_rknn(Path(a.onnx), Path(a.output))); return 0
    if a.command == "npu":
        print(json.dumps(infer_rknn(Path(a.rknn), Path(a.model), a.repeat), indent=2)); return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
