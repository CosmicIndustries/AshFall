import pandas as pd, numpy as np
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import json, textwrap

# --- 1. Auto-discover CSV/DMP/log ---
exts = [".csv", ".dmp", ".log", ".txt"]
cwd = Path(__file__).parent
cands = [f for f in cwd.iterdir() if f.suffix.lower() in exts]

if not cands:
    raise FileNotFoundError("No CSV/DMP/LOG/TXT file found in current folder.")
fp = cands[0]  # pick first match
print(f"[+] Using input: {fp.name}")

# --- 2. Read file (CSV, fallback TSV) ---
try:
    df = pd.read_csv(fp, low_memory=False)
except Exception:
    df = pd.read_csv(fp, sep="\t", low_memory=False)

report = {}

# --- 3. Basic profiling ---
report['shape'] = df.shape
report['dtypes'] = df.dtypes.astype(str).to_dict()
report['null_pct'] = (df.isna().mean()*100).round(2).to_dict()
report['n_duplicates'] = int(df.duplicated().sum())
report['constant_cols'] = [c for c in df.columns if df[c].nunique(dropna=False)==1]

# --- 4. Numeric features ---
numc = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
def outlier_share(s):
    s = s.dropna()
    if s.empty: return 0.0
    q1,q3 = np.percentile(s, [25,75]); iqr = q3-q1 or 1
    lo, hi = q1-1.5*iqr, q3+1.5*iqr
    return float(((s<lo)|(s>hi)).mean())
report['outlier_share_per_numcol'] = {c: round(outlier_share(df[c]),3) for c in numc}

# --- 5. Multivariate anomalies ---
X = df[numc].fillna(df[numc].median()) if numc else pd.DataFrame()
if not X.empty and len(X)>=50:
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    iso = IsolationForest(n_estimators=300, contamination='auto', random_state=42)
    score = iso.fit_predict(Xs)
    df['anomaly_flag'] = (score==-1).astype(int)
    report['anomaly_rate'] = float(df['anomaly_flag'].mean())

    # --- NEW: anomaly table ---
    if "ProcessName" in df.columns:
        anom_tbl = (df.loc[df['anomaly_flag']==1]
                      .groupby("ProcessName")[["CPU","VM","WS","IO"]]
                      .median()
                      .sort_values("VM", ascending=False)
                      .head(10))
        report['top_anomalous_processes'] = anom_tbl.to_dict(orient="index")

# --- 6. Time profiling (safe keys) ---
time_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
if not time_cols:
    for c in df.columns:
        if any(k in c.lower() for k in ['date','time','ts']):
            try:
                df[c] = pd.to_datetime(df[c], errors='raise', utc=True, dayfirst=True)
                time_cols.append(c)
                break
            except: pass
if time_cols:
    tcol = time_cols[0]
    s = df.set_index(tcol).sort_index()
    daily = s.resample('D').size()
    report['top_daily_spikes'] = {str(k.date()): int(v) 
                                  for k,v in daily.sort_values(ascending=False).head(5).items()}

# --- 7. Output concise report ---
print("\n## Data Audit (Concise)")
for k,v in report.items():
    try:
        print(f"- **{k}**: {textwrap.shorten(json.dumps(v, default=str), width=800, placeholder='…')}")
    except Exception:
        print(f"- **{k}**: {str(v)[:800]}…")
