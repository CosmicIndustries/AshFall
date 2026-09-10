# AshFall

<img src="images/ChatGPT Image Sep 2, 2025, 07_20_51 PM.png" alt="Ashfall — log anomaly detection & heatmap visualization" width="100%">

> using a heatMap logs are burned down, leaving behind the essence

AshFall is a lightweight log analyzer that turns raw operational logs into structured evidence: audits, anomaly signals, process summaries, time patterns, and heatmaps.

## Two operating modes

AshFall has two explicit interfaces built on the same analysis engine.

### User mode

Designed for a human investigating a log.

```bash
python AshFall.py /path/to/system.log --mode user
```

User mode provides a concise console report, anomaly exports, and the `Basename × ActionId` heatmap when those fields exist.

### Agent mode

Designed for JARVIS, scripts, pipelines, and other machine consumers.

```bash
python AshFall.py /path/to/system.log --mode agent
```

Agent mode is headless and emits a structured JSON report to stdout. It does not open a graphical window, making it suitable for remote systems and automated orchestration.

The report contains the input path, data audit, numeric feature inventory, anomaly rate, anomalous-process summaries, time-profile information when discoverable, and generated export paths.

Live operation is supported in either mode:

```bash
python AshFall.py /path/to/system.log --mode user --live
python AshFall.py /path/to/system.log --mode agent --live
```

## Analysis

* Automatic delimiter detection for common CSV/TSV-style logs.
* Data audit: shape, types, nulls, duplicates, and constants.
* Multivariate anomaly detection using Isolation Forest on numeric columns.
* Process-level anomaly aggregation using `Basename` or `ProcessName` when available.
* Time profiling and daily spike detection when a timestamp-like column is present.
* Heatmap visualization for `Basename × ActionId` data.
* CSV exports of anomalous rows and process summaries.

## Architecture

```text
                    ┌──────────────┐
                    │   raw logs   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ AshFall core │
                    │   analysis   │
                    └──────┬───────┘
                     ┌─────┴─────┐
                     ▼           ▼
                ┌────────┐  ┌────────┐
                │  USER  │  │ AGENT  │
                │ visual │  │  JSON  │
                └────────┘  └───┬────┘
                                 │
                              JARVIS
```

The important boundary is that **AshFall produces evidence; JARVIS consumes and reasons over that evidence.** AshFall does not autonomously modify the host system.

## Installation

Requires Python 3.9+.

```bash
python -m pip install -r requirements.txt
```

## Example

```bash
python AshFall.py logs/system_events.csv --mode user
python AshFall.py logs/system_events.csv --mode agent > ashfall.json
```

## License

Unlicense.
