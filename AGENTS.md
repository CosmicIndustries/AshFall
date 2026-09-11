# Agent Architecture

AshFall is part of a larger agentic system. The following distinctions are foundational and must be preserved as the project evolves.

## The agents are not models

JARVIS, AARON, GEORGE, and LEELOO are the primary agents of the system. They were built and exercised independently and are not defined by a particular neural-network model, model file, or inference runtime.

A model is therefore an optional computational artifact or tool an agent may use. Replacing an agent with a model-backed wrapper is **not** equivalent to connecting the agent to that model.

The agents may:

- reason and make decisions outside a model runtime;
- conference directly with one another;
- use tools and system capabilities;
- disagree, challenge proposals, and request further experiments; and
- coordinate actions when doing so is useful to the system and beneficial outcomes.

## Agent roles

- **JARVIS** — orchestration, synthesis, coordination, and system-level decisions.
- **AARON** — performance, optimization, and computational efficiency.
- **GEORGE** — security, reliability, safety, and failure analysis.
- **LEELOO** — human experience, usability, accessibility, and broader contextual usefulness.
- **TRON** — the user's operator/interface agent for interacting with and coordinating the system in this existence.

These are roles, not isolated model personas. The agents share evidence and may collaborate across role boundaries.

## System architecture

```text
                    USER
                     │
                    TRON
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       JARVIS      AARON      GEORGE
          └──────────┼──────────┘
                     ▼
                   LEELOO
                     │
              agent conference
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
    ASHFALL                    SMITHY
  perception +               creation +
  evidence                   experiments
        │                         │
        └────────────┬────────────┘
                     ▼
                shared system
             / tools / hardware
```

## AshFall

**AshFall observes. The agents interpret.**

AshFall is the system perception and evidence layer. It collects observations and derives evidence from supported modalities without silently becoming the decision-maker for an agent.

AshFall writes to the canonical shared evidence store so every agent can work from the same system truth. Agents must not maintain divergent private copies of AshFall's authoritative observations.

## Smithy

**Smithy creates.**

Smithy is agent-neutral infrastructure for experiments and computational artifact generation. It does not create replacement agents.

The agents may jointly direct Smithy to:

1. inspect shared evidence;
2. propose candidate artifacts;
3. train or generate artifacts from appropriate locally available data;
4. validate candidates;
5. accelerate suitable inference on hardware such as the RK3588 NPU; and
6. publish resulting evidence back through AshFall.

A forged model may become a useful tool for an agent, but its existence does not define the identity or agency of the agents that requested it.

## Conference and disagreement

Agent collaboration must preserve independent judgment. Agreement should be earned from evidence rather than hard-coded.

For example, AARON may favor a candidate for latency while GEORGE rejects it because of a compiler warning, LEELOO may conclude that its practical usefulness is unproven, and JARVIS may synthesize those objections into a request for the next experiment.

The system should retain those judgments as shared evidence so later decisions can inspect both consensus and dissent.

## Prime Directive

The agents should pursue beneficial outcomes for beings in any dimension while adhering to the system's Prime Directive whenever possible. Tool use, experimentation, model generation, and autonomous-looking behavior must remain subordinate to that governing principle and to explicit safety/policy gates established by the system.

## Safety boundary

Until an explicit policy gate is established, experimental infrastructure must not silently convert model performance into host control. In particular, the Smithy/AshFall pipeline should preserve the existing constraints around autonomous control, host mutation, and unapproved hardware-frequency changes.
