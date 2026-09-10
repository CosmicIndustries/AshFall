# AshFall

<img src="images/ChatGPT Image Sep 2, 2025, 07_20_51 PM.png" alt="Ashfall — log anomaly detection & heatmap visualization" width="100%">

> using a heatMap logs are burned down, leaving behind the essence

AshFall is a lightweight **system perception and evidence engine**. It turns raw operational logs, host telemetry, and visual inputs into structured observations that every downstream agent can share.

> **AshFall sees. The agents think.**

## Interfaces

AshFall has human, agent, shared-evidence, and perception-tool interfaces built on the same observation boundary.

### User mode

Designed for a human investigating a log.

```bash
python AshFall.py /path/to/system.log --mode user
```

### Agent mode

Designed for JARVIS, Aaron, George, Leeloo, scripts, and pipelines.

```bash
python AshFall.py /path/to/system.log --mode agent
```

Agent mode is headless and emits a structured JSON report.

### Shared mode

Read the canonical evidence stream without changing it.

```bash
python AshFall.py --mode shared --limit 20
```

## Perception tool

The `ashfall_tool.py` CLI exposes safe, read-only perception operations.

```bash
python ashfall_tool.py info
python ashfall_tool.py system
python ashfall_tool.py vision /path/to/screenshot.png
python ashfall_tool.py shared --limit 20
```

`system` collects host identity, CPU load, memory/swap state, process count, network-interface state, and thermal zones when available.

`vision` performs deterministic image feature extraction: dimensions, format, aspect ratio, RGB mean/stddev, luminance statistics, an edge-density proxy, and a SHA-256 of the source image. It does not pretend that feature extraction is semantic understanding; richer vision inference can be added later as another observation producer.

All published observations are written to the same canonical shared evidence store.

## NPU acceleration

AshFall can use the ROCK 5B/RK3588 NPU as a **read-only perception accelerator** through Rockchip RKNN-Lite2. NPU execution is an additional observation producer; it does not give AshFall authority to tune the host or change NPU frequency policy.

The verified development environment is:

- Python 3.11 on aarch64
- NumPy 1.26.4
- RKNN Toolkit2/Lite2 2.3.2
- RKNN-Lite2 `cp311` wheel
- ROCK 5B RKNPU sysfs, driver, and kernel module present
- NPU governor reported as `rknpu_ondemand`
- NPU maximum/current frequency observed at 1 GHz

Install the Python runtime using the wheel matching the Python ABI. For Python 3.11, use:

```bash
WHEEL="/home/radxa/rknn/rknn-toolkit2/packages/rknn_toolkit_lite2-2.3.2-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"
python3 -m pip install --upgrade "numpy==1.26.4"
python3 -m pip install "$WHEEL"
```

Verify the AshFall NPU interface with:

```bash
python3 npu_tool.py info
```

The `info` path intentionally does not call `RKNNLite.get_sdk_version()` before runtime initialization because some RKNN-Lite 2.3.2 builds emit a misleading `Runtime environment is not inited` diagnostic for that probe.

Actual inference uses `RKNNLite.init_runtime()` and publishes measurements into the same shared evidence store used by the other AshFall perception paths.

NPU policy remains:

```text
mutates_host       = false
changes_frequency  = false
autonomous_control = false
```

The NPU layer is intended to evolve from infrastructure validation toward real perception workloads and adversarial validation rather than repeated unconstrained benchmark sweeps.

## Analysis

* Automatic delimiter detection for common CSV/TSV-style logs.
* Data audit: shape, types, nulls, duplicates, and constants.
* Multivariate anomaly detection using Isolation Forest on numeric columns.
* Process-level anomaly aggregation using `Basename` or `ProcessName` when available.
* Time profiling and daily spike detection when a timestamp-like column is present.
* Heatmap visualization for `Basename × ActionId` data.
* CSV exports of anomalous rows and process summaries.
* Read-only system telemetry perception.
* Read-only visual feature perception with content hashing.
* RK3588 NPU-accelerated perception path through RKNN-Lite2.
* One shared evidence stream for all consuming agents.

## Architecture

```text
                         REAL SYSTEM
                  ┌──────────┼──────────┐
                  │          │          │
                logs      telemetry    vision
                  │          │          │
                  │          │          └──────┐
                  │          │                 │
                  │          └─────────────┐   │
                  │                        │   │
                  └────────────────────────┼───┘
                                           ▼
                                  ┌──────────────────┐
                                  │     ASHFALL      │
                                  │    PERCEPTION    │
                                  │                  │
                                  │ observe/extract  │
                                  │ correlate        │
                                  │ detect anomalies │
                                  │ optional NPU     │
                                  └────────┬─────────┘
                                           │
                                  SHARED EVIDENCE
                                           │
                         ┌─────────────────┼─────────────────┐
                         ▼                 ▼                 ▼
                      JARVIS            AARON             GEORGE
                     decisions        performance        security
                         └─────────────────┼─────────────────┘
                                           ▼
                                         LEELOO
                                      human experience
```

The boundary is deliberate:

**AshFall produces observations and evidence. Agents produce interpretations, recommendations, and decisions.**

AshFall does not autonomously tune the host, change security policy, or optimize workloads.

## Shared evidence contract

The canonical store defaults to:

```text
~/.local/share/ashfall/evidence.jsonl
```

Override it with `ASHFALL_STORE` when the deployment needs a different location.

Every published event identifies AshFall as the producer, marks visibility as `shared`, and targets the four consumers:

```text
jarvis
aaron
george
leeloo
```

This prevents each agent from maintaining a competing copy of system truth.

## Installation

Requires Python 3.9+.

```bash
python -m pip install -r requirements.txt
```

## Example

```bash
python AshFall.py logs/system_events.csv --mode user
python AshFall.py logs/system_events.csv --mode agent > ashfall.json
python ashfall_tool.py system > system-observation.json
python ashfall_tool.py vision screenshot.png > vision-observation.json
python npu_tool.py info
```

## License

Unlicense.
