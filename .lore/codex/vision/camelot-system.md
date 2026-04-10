---
id: vision-camelot-system
title: Camelot System Vision
summary: >
  What Camelot is, why it exists, and how its three projects — Lore, Realm, and Citadel — fit
  together to form a complete AI-driven development platform. Covers the dependency direction,
  Lore's role as the authoritative state engine, and the future capabilities planned for the system.
related: ["tech-api-surface", "decisions-010-public-api-stability", "decisions-011-api-parity-with-cli", "tech-overview", "conceptual-workflows-typical-workflow"]
stability: stable
---

# Camelot System Vision

Camelot is an AI-driven development platform built to let software teams run continuous, autonomous development workflows with human oversight. It is composed of three projects — Lore, Realm, and Citadel — each with a single, well-defined responsibility.

## What It Is

Camelot is a platform for AI-driven development. It manages tasks, runs AI agents that execute those tasks, and gives humans a control surface to monitor and intervene. The system is designed so that AI agents can work continuously and autonomously while humans remain in control of what gets built and when.

The three projects are:

- **Lore** — the task engine. Stores all knowledge and state. It is the authoritative source of truth for every quest, mission, agent persona, doctrine, and board message in the system.
- **Realm** — the orchestrator. Consumes Lore to run AI agents automatically. It reads state from Lore, spawns worker agents, and writes outcomes back to Lore.
- **Citadel** — the human-facing UI. Humans monitor and control everything through it — approving work, reviewing output, and steering the system.

## How It Fits Together

The dependency direction is strict and one-way:

```
Citadel  →  Realm  →  Lore
```

Lore has zero dependencies on Realm or Citadel. It does not import them, call them, or know they exist. Realm depends on Lore. Citadel depends on Realm (and indirectly on Lore). This direction is a design constraint, not a convention — it keeps Lore stable and independently usable.

## Lore's Role

Lore is the foundation. It has two consumers:

**Humans via CLI** — A developer types `lore new quest`, `lore ready`, `lore done`. This is the primary developer experience today.

**Realm via Python import** — Realm imports from `lore.models` to get typed representations of Lore entities. The canonical import pattern is:

```python
from lore.models import Quest, Mission, QuestStatus, MissionStatus
```

`lore.models.__all__` defines the public API surface — the complete set of names Realm can safely depend on. Any name not in `__all__` is an internal implementation detail.

Every feature in Lore is designed to work as both a CLI command and a Python API call. The CLI is a thin wrapper; the real interface is the Python modules underneath. State is authoritative: if Lore says a Mission is `blocked`, it is `blocked`. No other system maintains a parallel copy.

## Why It Exists

Software development involves large amounts of repetitive, structured work — writing specs, implementing features, reviewing code, updating documentation. AI agents can handle much of this work if they have reliable state, clear instructions, and a way for humans to stay in control.

Camelot exists to provide that infrastructure. Lore stores the state. Realm runs the agents. Citadel gives humans the control surface. Together they form a loop: humans steer, agents execute, state accumulates, humans review.

## Future Scope

The following capabilities are part of the long-term vision for the Camelot system but are not yet implemented in the current codebase:

- **Weapons** — Capability definitions (MCP servers, bash commands, executables). Lore will be responsible for storing weapon definitions so that Realm can equip agents with the right tools for each mission. No `weapons` table, model, or CLI command exists today.
- **Session file pointers** — A path field on each Mission pointing to a JSONL conversation history file. Lore will store the path; Realm will write the file. No such column exists in the current schema.

Note: per-Quest and per-Mission message boards (`lore board add`, `lore board delete`) are fully implemented and are no longer future scope.
