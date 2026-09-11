# Smithy Agent Tool

This is the operational bridge between the real Cosmic agents and Smithy-generated computational artifacts.

The agents remain independent of models. The tool is simply another capability available to them. A model can be inspected, selected, used, rejected, retrained, or replaced without changing the identity of JARVIS, AARON, GEORGE, or LEELOO.

## Install

From the AshFall checkout on the ROCK 5B:

```bash
sudo ./install_smithy_agent_tools.sh
```

The installer places the tool at `/usr/local/sbin/cosmic-agent-smithy` and publishes a machine-readable manifest at `/var/lib/agent-bus/tools/SMITHY.json`. It deliberately leaves `/usr/local/sbin/cosmic-agent-core` and `agent-conversation.service` intact.

## Agent interaction

Inspect available artifacts:

```bash
sudo cosmic-agent-smithy available --agent jarvis
sudo cosmic-agent-smithy available --agent aaron
sudo cosmic-agent-smithy available --agent george
sudo cosmic-agent-smithy available --agent leeloo
```

Use the latest Smithy artifact on CPU:

```bash
sudo cosmic-agent-smithy use \
  --agent aaron \
  --model latest \
  --accelerator cpu \
  --reason "AARON-selected model evaluation"
```

Use the latest artifact with automatic accelerator selection. The bridge prefers RKNPU only when an RKNN artifact for that model can be found; otherwise it uses CPU:

```bash
sudo cosmic-agent-smithy use \
  --agent aaron \
  --model latest \
  --accelerator auto \
  --reason "AARON-selected accelerated evaluation"
```

The agent may pin an exact model ID and exact AshFall observation when reproducibility requires it:

```bash
sudo cosmic-agent-smithy use \
  --agent george \
  --model <model_id> \
  --accelerator auto \
  --observation-evidence-id <evidence_id> \
  --reason "GEORGE-selected reproducibility check"
```

## Shared evidence

Model artifacts are discovered from the AshFall evidence history. The bridge searches the configured `ASHFALL_STORE`, the canonical `/var/lib/ashfall/evidence.jsonl`, and discovered user AshFall stores. A selected artifact is materialized into `/var/lib/ashfall/smithy/models/<model_id>.json` so the same model can be executed repeatedly without copying private agent state.

Model-use results are published through the existing Smithy/AshFall runtime as shared evidence. Other agents can inspect the same model identity, source observation, accelerator, latency, and reconstruction error.

## Agent independence

The bridge does not infer that a model should be used. It does not create a scheduled model invocation. It does not substitute a model response for agent cognition. The requesting agent remains the authority for whether the capability is useful.

## Safety boundary

Current Smithy agent-tool policy is read-only with respect to the host:

- no host mutation;
- no NPU frequency/governor changes;
- no autonomous host control;
- no external pretrained-model download;
- model execution results are evidence, not commands.

This lets the existing agents gain a real computational capability without turning the capability layer into a second agent implementation.
