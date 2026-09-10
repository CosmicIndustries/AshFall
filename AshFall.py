#!/usr/bin/env python3
"""AshFall — log anomaly analysis with human and agent modes.

User mode is visual and explanatory. Agent mode is deterministic, headless,
machine-readable JSON intended for JARVIS or other automation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib

# Agent mode must work without a display server.
if "--mode" in sys.argv:
    try:
        mode_index = sys.argv.index("--mode") + 1
        if mode_index < len(sys.argv) and sys.argv[mode_index] == "agent":
            matplotlib.use("Agg")
    except (ValueError, IndexError):
        pass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

REFRESH = 5


def detect_delimiter(fpath: Path) -> str | None:
    """Let pandas' Python engine infer common CSV/TSV delimiters."""
    return None


def audit_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "shape": [int(df.shape[0]), int(df.shape[1])],
        "columns": [str(c) for c in df.columns],
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
        "null_pct": {str(c): round(float(v), 2) for c, v in df.isna().mean().mul(100).items()},
        "n_duplicates": int(df.duplicated().sum()),
        "constant_cols": [str(c) for c in df.columns if df[c].nunique(dropna=False) <= 1],
    }


def analyze_file(fpath: Path, show_plot: bool = True) -> dict[str, Any] | None:
    try:
        df = pd.read_csv(fpath, sep=detect_delimiter(fpath), engine="python", low_memory=False)
    except Exception as exc:
        return {"status": "error", "error": f"Failed to load {fpath}: {exc}"}

    report: dict[str, Any] = {"status": "ok", "input": str(fpath.resolve())}
    report["audit"] = audit_dataframe(df)

    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    report["numeric_columns"] = [str(c) for c in num_cols]

    if num_cols and len(df) >= 50:
        X = df[num_cols].replace([np.inf, -np.inf], np.nan)
        X = X.fillna(X.median(numeric_only=True)).fillna(0)
        iso = IsolationForest(n_estimators=300, contamination="auto", random_state=42, n_jobs=-1)
        predictions = iso.fit_predict(X)
        scores = iso.decision_function(X)
        df["is_anom"] = (predictions == -1).astype(int)
        df["anomaly_score"] = scores
        report["anomaly_rate"] = round(float(df["is_anom"].mean()), 6)
    else:
        df["is_anom"] = 0
        df["anomaly_score"] = 0.0
        report["anomaly_rate"] = 0.0
        report["anomaly_note"] = "Insufficient numeric data for multivariate Isolation Forest"

    if "Basename" in df.columns:
        summary = (
            df.loc[df["is_anom"] == 1]
            .groupby("Basename")
            .size()
            .sort_values(ascending=False)
            .rename("AnomalyCount")
            .reset_index()
        )
        report["top_anomalous_processes"] = summary.head(15).to_dict(orient="records")
    elif "ProcessName" in df.columns:
        summary = (
            df.loc[df["is_anom"] == 1]
            .groupby("ProcessName")
            .size()
            .sort_values(ascending=False)
            .rename("AnomalyCount")
            .reset_index()
        )
        report["top_anomalous_processes"] = summary.head(15).to_dict(orient="records")

    time_col = None
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            time_col = col
            break
    if time_col is None:
        for col in df.columns:
            if any(k in str(col).lower() for k in ("date", "time", "timestamp", "ts")):
                parsed = pd.to_datetime(df[col], errors="coerce", utc=True)
                if parsed.notna().sum() >= max(3, len(df) // 2):
                    df[col] = parsed
                    time_col = col
                    break
    if time_col is not None:
        daily = df.set_index(time_col).sort_index().resample("D").size()
        report["time_profile"] = {
            "column": str(time_col),
            "top_daily_spikes": {str(k.date()): int(v) for k, v in daily.nlargest(5).items()},
        }

    out_dir = fpath.parent
    anomaly_path = out_dir / f"{fpath.stem}_anomalies.csv"
    df.loc[df["is_anom"] == 1].to_csv(anomaly_path, index=False)
    report["exports"] = {"anomalies_csv": str(anomaly_path)}

    if "top_anomalous_processes" in report:
        summary_path = out_dir / f"{fpath.stem}_summary.csv"
        pd.DataFrame(report["top_anomalous_processes"]).to_csv(summary_path, index=False)
        report["exports"]["summary_csv"] = str(summary_path)

    if show_plot and {"Basename", "ActionId"}.issubset(df.columns):
        import seaborn as sns
        pivot = df.pivot_table(index="Basename", columns="ActionId", values="is_anom", aggfunc="sum", fill_value=0)
        plt.figure(figsize=(12, 6))
        sns.heatmap(pivot, cmap="Reds", linewidths=0.5)
        plt.title("AshFall Anomaly Heatmap: Basename × ActionId")
        plt.tight_layout()
        plt.show(block=False)
        plt.pause(1)
        plt.close()

    return report


def user_mode(fpath: Path) -> int:
    """Human-facing console report with optional heatmap."""
    report = analyze_file(fpath, show_plot=True)
    if not report or report.get("status") != "ok":
        print(f"[!] {report.get('error', 'Analysis failed') if report else 'Analysis failed'}")
        return 1

    print("\n=== ASHFALL / USER MODE ===")
    print(f"Input: {report['input']}")
    print(f"Shape: {tuple(report['audit']['shape'])}")
    print(f"Numeric columns: {len(report['numeric_columns'])}")
    print(f"Anomaly rate: {report['anomaly_rate']:.3%}")
    for row in report.get("top_anomalous_processes", [])[:10]:
        print(f"  {row}")
    for key, value in report.get("exports", {}).items():
        print(f"Export: {key} -> {value}")
    return 0


def agent_mode(fpath: Path) -> int:
    """Headless machine-facing contract: exactly one JSON document on stdout."""
    report = analyze_file(fpath, show_plot=False)
    if report is None:
        report = {"status": "error", "error": "No report generated"}
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0 if report.get("status") == "ok" else 1


def live_mode(fpath: Path, mode: str) -> int:
    print(f"[+] Live {mode} mode enabled; refresh={REFRESH}s; watching {fpath}")
    last_size = -1
    try:
        while True:
            size = fpath.stat().st_size if fpath.exists() else -1
            if size != last_size:
                last_size = size
                if mode == "agent":
                    report = analyze_file(fpath, show_plot=False) if fpath.exists() else {"status": "waiting"}
                    print(json.dumps(report, sort_keys=True, default=str), flush=True)
                else:
                    os.system("cls" if os.name == "nt" else "clear")
                    if fpath.exists():
                        user_mode(fpath)
            time.sleep(REFRESH)
    except KeyboardInterrupt:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AshFall log anomaly analyzer")
    parser.add_argument("logfile", nargs="?", default="processlasso.log")
    parser.add_argument("--mode", choices=("user", "agent"), default="user")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    fpath = Path(args.logfile)

    if args.live:
        return live_mode(fpath, args.mode)
    if args.mode == "agent":
        return agent_mode(fpath)
    return user_mode(fpath)


if __name__ == "__main__":
    raise SystemExit(main())
