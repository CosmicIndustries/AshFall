#!/usr/bin/env python3
"""AshFall — shared system-observation layer.

USER mode is the human-facing investigation interface.
AGENT mode is the machine-facing interface.

AshFall owns observation/anomaly detection. Agent-specific interpretation,
optimization, security decisions, and UX decisions remain with the agents.
All agents consume the same shared evidence store.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
from typing import Any
import matplotlib
if "--mode" in sys.argv:
    try:
        i = sys.argv.index("--mode") + 1
        if i < len(sys.argv) and sys.argv[i] == "agent": matplotlib.use("Agg")
    except (ValueError, IndexError): pass
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from ashfall_store import DEFAULT_STORE, append_evidence, read_evidence

REFRESH = 5
AGENTS = ("jarvis", "aaron", "george", "leeloo")

def audit_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    return {"shape": [int(df.shape[0]), int(df.shape[1])], "columns": [str(c) for c in df.columns], "dtypes": {str(c): str(t) for c, t in df.dtypes.items()}, "null_pct": {str(c): round(float(v), 2) for c, v in df.isna().mean().mul(100).items()}, "n_duplicates": int(df.duplicated().sum()), "constant_cols": [str(c) for c in df.columns if df[c].nunique(dropna=False) <= 1]}

def analyze_file(fpath: Path, show_plot: bool = True) -> dict[str, Any]:
    try: df = pd.read_csv(fpath, sep=None, engine="python", low_memory=False)
    except Exception as exc: return {"schema": "ashfall.report.v1", "status": "error", "error": str(exc), "input": str(fpath.resolve())}
    report = {"schema": "ashfall.report.v1", "status": "ok", "input": str(fpath.resolve()), "observed_at": time.time(), "audit": audit_dataframe(df)}
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist(); report["numeric_columns"] = [str(c) for c in num_cols]
    if num_cols and len(df) >= 50:
        X = df[num_cols].replace([np.inf, -np.inf], np.nan); X = X.fillna(X.median(numeric_only=True)).fillna(0)
        iso = IsolationForest(n_estimators=300, contamination="auto", random_state=42, n_jobs=-1); pred = iso.fit_predict(X)
        df["is_anom"] = (pred == -1).astype(int); df["anomaly_score"] = iso.decision_function(X); report["anomaly_rate"] = round(float(df["is_anom"].mean()), 6)
    else:
        df["is_anom"] = 0; df["anomaly_score"] = 0.0; report["anomaly_rate"] = 0.0; report["anomaly_note"] = "Insufficient numeric data for multivariate Isolation Forest"
    process_col = "Basename" if "Basename" in df.columns else ("ProcessName" if "ProcessName" in df.columns else None)
    if process_col:
        summary = df.loc[df["is_anom"] == 1].groupby(process_col).size().sort_values(ascending=False).rename("AnomalyCount").reset_index(); report["top_anomalous_processes"] = summary.head(15).to_dict(orient="records")
    time_col = next((c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])), None)
    if time_col is None:
        for col in df.columns:
            if any(k in str(col).lower() for k in ("date", "time", "timestamp", "ts")):
                parsed = pd.to_datetime(df[col], errors="coerce", utc=True)
                if parsed.notna().sum() >= max(3, len(df) // 2): df[col], time_col = parsed, col; break
    if time_col is not None:
        daily = df.set_index(time_col).sort_index().resample("D").size(); report["time_profile"] = {"column": str(time_col), "top_daily_spikes": {str(k.date()): int(v) for k, v in daily.nlargest(5).items()}}
    out_dir = fpath.parent; anomaly_path = out_dir / f"{fpath.stem}_anomalies.csv"; df.loc[df["is_anom"] == 1].to_csv(anomaly_path, index=False); report["exports"] = {"anomalies_csv": str(anomaly_path)}
    if "top_anomalous_processes" in report:
        summary_path = out_dir / f"{fpath.stem}_summary.csv"; pd.DataFrame(report["top_anomalous_processes"]).to_csv(summary_path, index=False); report["exports"]["summary_csv"] = str(summary_path)
    if show_plot and {"Basename", "ActionId"}.issubset(df.columns):
        import seaborn as sns
        pivot = df.pivot_table(index="Basename", columns="ActionId", values="is_anom", aggfunc="sum", fill_value=0); plt.figure(figsize=(12, 6)); sns.heatmap(pivot, cmap="Reds", linewidths=0.5); plt.title("AshFall Anomaly Heatmap: Basename × ActionId"); plt.tight_layout(); plt.show(block=False); plt.pause(1); plt.close()
    return report

def publish(report: dict[str, Any]) -> str | None:
    if report.get("status") != "ok": return None
    return append_evidence({"kind": "observation", "source": "ashfall", "producer": "ashfall", "visibility": "shared", "audience": list(AGENTS), "report": report})

def user_mode(fpath: Path) -> int:
    report = analyze_file(fpath, show_plot=True)
    if report.get("status") != "ok": print(f"[!] {report.get('error', 'Analysis failed')}"); return 1
    evidence_id = publish(report); print("\n=== ASHFALL / USER MODE ==="); print(f"Input: {report['input']}"); print(f"Shape: {tuple(report['audit']['shape'])}"); print(f"Anomaly rate: {report['anomaly_rate']:.3%}"); print(f"Shared evidence: {evidence_id}"); print(f"Shared store: {DEFAULT_STORE}"); return 0

def agent_mode(fpath: Path) -> int:
    report = analyze_file(fpath, show_plot=False); evidence_id = publish(report)
    print(json.dumps({"schema": "ashfall.agent.v1", "producer": "ashfall", "visibility": "shared", "audience": list(AGENTS), "evidence_id": evidence_id, "report": report}, indent=2, sort_keys=True, default=str)); return 0 if report.get("status") == "ok" else 1

def shared_mode(limit: int | None = None) -> int:
    print(json.dumps({"schema": "ashfall.shared.v1", "store": str(DEFAULT_STORE), "agents": list(AGENTS), "evidence": read_evidence(limit=limit)}, indent=2, sort_keys=True, default=str)); return 0

def live_mode(fpath: Path, mode: str) -> int:
    print(f"[+] Live {mode} mode enabled; refresh={REFRESH}s; watching {fpath}"); last_size = -1
    try:
        while True:
            size = fpath.stat().st_size if fpath.exists() else -1
            if size != last_size:
                last_size = size
                if fpath.exists(): agent_mode(fpath) if mode == "agent" else user_mode(fpath)
            time.sleep(REFRESH)
    except KeyboardInterrupt: return 0

def main() -> int:
    p = argparse.ArgumentParser(description="AshFall shared log-observation layer"); p.add_argument("logfile", nargs="?", default="processlasso.log"); p.add_argument("--mode", choices=("user", "agent", "shared"), default="user"); p.add_argument("--live", action="store_true"); p.add_argument("--limit", type=int, default=None); a = p.parse_args()
    if a.mode == "shared": return shared_mode(a.limit)
    f = Path(a.logfile)
    if a.live: return live_mode(f, a.mode)
    return agent_mode(f) if a.mode == "agent" else user_mode(f)

if __name__ == "__main__": raise SystemExit(main())
