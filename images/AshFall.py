#!/usr/bin/env python3
"""
ashfall.py — Unified Log Analyzer

Features:
- Auto-detect delimiter
- Audit summary
- IsolationForest anomaly detection
- Top anomalous processes
- Heatmap visualization
- CSV exports
- Live tail mode (--live) with TUI refresh
"""

import sys, time
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from pathlib import Path
import os

REFRESH = 5  # seconds between updates in --live mode


def analyze_file(fpath: Path, show_plot=True):
    try:
        df = pd.read_csv(fpath, sep=None, engine="python", low_memory=False)
    except Exception as e:
        print(f"[!] Failed to load {fpath}: {e}")
        return None, None

    # -------------------------------
    # Basic Audit
    # -------------------------------
    print("\n## Data Audit (Concise)")
    print(f"- shape: {df.shape}")
    print(f"- dtypes: {df.dtypes.apply(lambda x: x.name).to_dict()}")
    print(f"- null_pct: {df.isna().mean().mul(100).round(2).to_dict()}")
    print(f"- n_duplicates: {df.duplicated().sum()}")
    print(f"- constant_cols: {df.columns[df.nunique() <= 1].tolist()}")

    # -------------------------------
    # Anomaly Detection
    # -------------------------------
    num_cols = df.select_dtypes(include=[np.number]).columns
    if not num_cols.empty:
        iso = IsolationForest(contamination=0.1, random_state=42)
        df['is_anom'] = iso.fit_predict(df[num_cols])
        df['is_anom'] = df['is_anom'].map({-1: 1, 1: 0})
        anomaly_rate = df['is_anom'].mean()
        print(f"- anomaly_rate: {anomaly_rate:.3f}")
    else:
        df['is_anom'] = 0
        print("- anomaly_rate: N/A (no numeric cols)")

    # -------------------------------
    # Top Anomalous Processes
    # -------------------------------
    summary = None
    if "Basename" in df.columns:
        summary = (
            df[df['is_anom'] == 1]
            .groupby("Basename")
            .size()
            .sort_values(ascending=False)
            .rename("AnomalyCount")
            .reset_index()
        )
        print("\n## Top Anomalous Processes")
        print(summary.head(15).to_string(index=False))

    # -------------------------------
    # Heatmap
    # -------------------------------
    if show_plot and {"Basename", "ActionId"}.issubset(df.columns):
        pivot = df.pivot_table(
            index="Basename",
            columns="ActionId",
            values="is_anom",
            aggfunc="sum",
            fill_value=0
        )
        plt.figure(figsize=(12, 6))
        sns.heatmap(pivot, cmap="Reds", linewidths=0.5)
        plt.title("Anomaly Heatmap: Basename × ActionId")
        plt.tight_layout()
        plt.show(block=False)
        plt.pause(1)
        plt.close()

    # -------------------------------
    # Exports
    # -------------------------------
    out_dir = fpath.parent
    anom_path = out_dir / f"{fpath.stem}_anomalies.csv"
    df[df['is_anom'] == 1].to_csv(anom_path, index=False)
    print(f"[+] Anomalies exported: {anom_path}")

    if summary is not None:
        summary_path = out_dir / f"{fpath.stem}_summary.csv"
        summary.to_csv(summary_path, index=False)
        print(f"[+] Summary exported: {summary_path}")

    return df, summary


def live_mode(fpath: Path):
    print(f"[+] Live mode enabled. Refresh every {REFRESH}s. Watching {fpath}")
    last_size = 0
    while True:
        try:
            new_size = os.path.getsize(fpath)
            if new_size > last_size:  # file grew
                os.system("cls" if os.name == "nt" else "clear")
                print(f"[LIVE] {time.strftime('%Y-%m-%d %H:%M:%S')}")
                analyze_file(fpath, show_plot=False)
                last_size = new_size
            time.sleep(REFRESH)
        except KeyboardInterrupt:
            print("\n[!] Live mode stopped by user.")
            break


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ashfall.py <logfile> [--live]")
        sys.exit(1)

    fpath = Path(sys.argv[1])
    live = "--live" in sys.argv

    if live:
        live_mode(fpath)
    else:
        analyze_file(fpath, show_plot=True)
