#!/usr/bin/env python3
"""Tests for the agent-facing Smithy tool bridge without requiring an NPU."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cosmic_smithy_tool as tool


class SmithyToolTests(unittest.TestCase):
    def make_event(self, model_id: str = "test-model") -> dict:
        return {
            "kind": "smithy_model",
            "evidence_id": "evidence-test",
            "observed_at": 1.0,
            "model": {
                "schema": "smithy.model.v1",
                "model_id": model_id,
                "trained_at": 2.0,
                "train_mse": 0.1,
                "validation_mse": 0.2,
                "candidate": {"task": "ashfall_system_autoencoder", "hidden": 8},
                "dataset": {"mean": [0.0] * 12, "std": [1.0] * 12},
                "weights": {
                    "w1": [[0.0] * 8 for _ in range(12)],
                    "b1": [0.0] * 8,
                    "w2": [[0.0] * 12 for _ in range(8)],
                    "b2": [0.0] * 12,
                },
            },
        }

    def test_select_latest(self) -> None:
        with mock.patch.object(tool, "_all_evidence", return_value=[self.make_event()]):
            selected = tool._select_model("latest")
        self.assertEqual(selected["model"]["model_id"], "test-model")

    def test_materialize_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(tool, "CACHE", Path(td)):
                path = tool._materialize(self.make_event("abc123"))
                self.assertEqual(path.name, "abc123.json")
                loaded = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(loaded["schema"], "smithy.model.v1")
                self.assertEqual(loaded["model_id"], "abc123")

    def test_available_does_not_select_model(self) -> None:
        event = self.make_event()
        with mock.patch.object(tool, "_all_evidence", return_value=[event]), mock.patch.object(tool, "_store_candidates", return_value=[]):
            data = tool.available("aaron")
        self.assertTrue(data["bridge"]["agent_selects_model"])
        self.assertTrue(data["bridge"]["agent_selects_use"])
        self.assertEqual(data["agent"], "aaron")
        self.assertEqual(len(data["models"]), 1)


if __name__ == "__main__":
    unittest.main()
