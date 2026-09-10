# AshFall

<img src="images/ChatGPT Image Sep 2, 2025, 07_20_51 PM.png" alt="Ashfall — log anomaly detection & heatmap visualization" width="100%">

> using a heatMap logs are burned down, leaving behind the essence

AshFall is a lightweight **system perception and evidence engine**. It turns raw operational logs, host telemetry, and visual inputs into structured observations that every downstream agent can share.

> **AshFall sees. The agents think.**

## Interfaces

AshFall has human, agent, shared-evidence, and perception-tool interfaces built on the same observation boundary.

### User mode

```bash
python AshFall.py /path/to/system.log --mode user
```

### Agent mode

```bash
python AshFall.py /path/to/system.log --mode agent
```

### Shared mode

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

The verified development environment is Python 3.11 on aarch64, NumPy 1.26.4, RKNN Toolkit2/Lite2 2.3.2, the matching `cp311` wheel, and a visible ROCK 5B RKNPU sysfs/driver/module stack. The observed NPU governor is `rknpu_ondemand` with a 1 GHz maximum/current frequency.

The `info` path intentionally does not call `RKNNLite.get_sdk_version()` before runtime initialization because some RKNN-Lite 2.3.2 builds emit a misleading `Runtime environment is not inited` diagnostic for that probe.

NPU policy remains:

```text
mutates_host       = false
changes_frequency  = false
autonomous_control = false
```

## Smithy

**Smithy is AshFall's agent-native capability workshop.** It does not import an outside pretrained model. Its first learning task is generated from AshFall's own system observations.

```text
ASHFALL
  │ observations
  ▼
SMITHY
  │
  ├─ JARVIS  → coordination / objective
  ├─ AARON   → performance constraints
  ├─ GEORGE  → safety / reproducibility
  └─ LEELOO  → usefulness / generalization
  │
  ▼
candidate architecture
  │
  ▼
train locally from AshFall evidence
  │
  ▼
ONNX → RKNN
  │
  ▼
ROCK 5B RKNPU
  │
  ▼
AshFall validation evidence
  └──────────────→ next forge iteration
```

The first Smithy candidate is a small system-state autoencoder. It learns a compact representation from the numeric system observations already collected by AshFall. Training is performed on the host; the resulting locally generated model can then be exported to ONNX, compiled for RK3588, and executed through RKNN-Lite2 on the NPU.

Smithy records proposals, model artifacts, and NPU validation in the same shared evidence stream. Agents therefore do not maintain competing copies of system truth.

### Smithy workflow

Collect enough AshFall observations first:

```bash
python ashfall_tool.py system
```

Create an agent-consensus candidate:

```bash
python smithy.py propose --output candidate.json
```

Inspect the dataset available to Smithy:

```bash
python smithy.py dataset
```

Train the candidate using only AshFall observations:

```bash
python smithy.py train --candidate candidate.json --output model.json
```

Export the locally forged model:

```bash
python smithy_npu.py onnx model.json smithy.onnx
```

Compile it for RK3588:

```bash
python smithy_npu.py compile smithy.onnx smithy.rknn
```

Run it on the ROCK 5B NPU and publish validation evidence:

```bash
python smithy_npu.py npu model.json smithy.rknn
```

ONNX is an optional build dependency for the export stage:

```bash
python -m pip install onnx
```

Smithy deliberately separates **training from NPU execution**. The NPU is the execution/validation target, not a falsely assumed general-purpose training device.

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
* Agent-native Smithy model forging from local AshFall evidence.
* One shared evidence stream for all consuming agents.

## Architecture

```text
                         REAL SYSTEM
                  ┌──────────┼──────────┐
                  │          │          │
                logs      telemetry    vision
                  │          │          │
                  └──────────┼──────────┘
                             ▼
                    ┌──────────────────┐
                    │     ASHFALL      │
                    │    PERCEPTION    │
                    └────────┬─────────┘
                             │
                    SHARED EVIDENCE
                             │
                    ┌────────▼────────┐
                    │     SMITHY      │
                    │ capability forge│
                    └────────┬────────┘
                             │
                    ┌────────┼────────┐
                    ▼        ▼        ▼
                 JARVIS   AARON    GEORGE
                    └────────┼────────┘
                             ▼
                          LEELOO
                             │
                       forged model
                             ▼
                          RKNPU
                             │
                             └──────→ ASHFALL
```

The boundary is deliberate:

**AshFall produces observations and evidence. Smithy forges capabilities. Agents produce interpretations, recommendations, and decisions.**

AshFall and Smithy do not autonomously tune the host or change security policy.

## Shared evidence contract

The canonical store defaults to:

```text
~/.local/share/ashfall/evidence.jsonl
```

Override it with `ASHFALL_STORE` when the deployment needs a different location.

Every published event identifies its producer, marks visibility as `shared`, and targets:

```text
jarvis
aaron
george
leeloo
```

## Installation

Requires Python 3.9+ for the core. The NPU path additionally requires a compatible RKNN-Lite2 environment; Smithy ONNX export requires the optional `onnx` package.

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
