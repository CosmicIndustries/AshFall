# Smithy Agent Runtime

Smithy-generated models are optional tools for the existing agents.

The runtime does **not** create or simulate JARVIS, AARON, GEORGE, or LEELOO. An agent decides whether a model is useful; the runtime only provides a controlled way to inspect and execute the selected artifact.

## Capabilities

```bash
python smithy_agent_runtime.py available
```

Use a Smithy artifact against the latest AshFall system observation on CPU:

```bash
python smithy_agent_runtime.py use \
  --agent aaron \
  --model ~/path/to/model.json \
  --accelerator cpu \
  --reason "evaluate the current system-state representation"
```

Use an exported RKNN artifact on the RKNPU:

```bash
python smithy_agent_runtime.py use \
  --agent aaron \
  --model ~/path/to/model.json \
  --accelerator npu \
  --rknn ~/path/to/model.rknn \
  --reason "accelerated evaluation of current system state"
```

A specific AshFall observation can be selected with `--observation-evidence-id` rather than using the latest observation.

## First model semantics

The first Smithy artifact is an AshFall system-state autoencoder. The runtime reconstructs the normalized 12-feature state vector and reports reconstruction MSE. That score is evidence available to the agents; it is **not** itself an anomaly decision, policy decision, or command to the host.

## Shared evidence

Every model-use event is written to the canonical AshFall evidence store with:

- requesting agent;
- model identity and SHA-256;
- source AshFall observation;
- accelerator and execution latency;
- reconstruction error;
- runtime/output metadata; and
- explicit non-autonomous policy state.

This lets all four agents inspect the same result and independently interpret it.

## Architectural rule

**Agents choose when to use models. Models do not choose when to use agents.**

A model can be replaced, rejected, retrained, or ignored without changing the identity of the agent using it.
