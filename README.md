# AshFall       <img src="images/ChatGPT Image Sep 2, 2025, 07_20_51 PM.png" alt="Ashfall — log anomaly detection & heatmap visualization" width="100%">
using a heatMap logs are burned down, leaving behind the essence
---

# Ashfall

**Ashfall** is a lightweight log analyzer that detects anomalies and visualizes them with heatmaps.
It transforms raw logs into actionable insights, highlighting unusual patterns in processes and actions.

---
<p align="center">
  <img src="images/ashfall.svg" alt="Ashfall — log anomaly detection & heatmap visualization" width="100%">
</p>
---
## Features

* 🔎 **Automatic delimiter detection** – works with common CSV/TSV-style logs.
* 📊 **Data audit** – quick summary of shape, types, nulls, duplicates, constants.
* ⚠️ **Anomaly detection** – uses *Isolation Forest* on numeric columns to flag outliers.
* 🧾 **Top anomalous processes** – aggregates unusual behavior by process name (`Basename`).
* 🌡️ **Heatmap visualization** – Basename × ActionId anomalies in a red-shaded matrix.
* 📂 **Exports results** – anomalies and summary tables as CSV files.

---

## Installation

Requires **Python 3.9+**.

```bash
pip install pandas numpy seaborn scikit-learn matplotlib
```

Clone or copy `ashfall.py` into your working directory.

---

## Usage

```bash
python ashfall.py /path/to/your/logfile.log
```

* If no file is specified, defaults to `processlasso.log`.
* Outputs analysis to console, displays a heatmap, and writes CSV results next to the input file.

---

## Output

1. **Console Audit**

   * Shape, dtypes, null percentages, duplicates, constants.
   * Anomaly rate and top anomalous processes.

2. **CSV Files**

   * `<logname>_anomalies.csv` → rows flagged as anomalous.
   * `<logname>_summary.csv` → aggregated anomaly counts by process.

3. **Heatmap**

   * Matrix of anomalies by **Basename × ActionId**, red intensity indicates anomaly density.

---

## Example

```bash
python ashfall.py logs/system_events.csv
```

Output:

* `system_events_anomalies.csv`
* `system_events_summary.csv`
* Heatmap figure displayed inline.

---

## Notes

* Only numeric columns are used for anomaly detection.
* If no numeric data exists, anomalies default to `0`.
* Designed for **process-level log analysis**, but adaptable to other structured log sources.

---

