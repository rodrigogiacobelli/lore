---
id: conceptual-relationships-lore-camelot-system
title: Lore in the Camelot System
summary: How Lore relates to the other two projects in the Camelot system — Realm (the AI orchestration layer) and Citadel (the human-facing UI). Covers Lore's two consumers (humans via CLI, Realm via Python import), the design constraint that Lore has zero dependencies on the other systems, and which described features are shipped versus planned.
related: ["tech-api-surface", "decisions-010", "decisions-011", "tech-overview"]
stability: stable
---

# Lore in the Camelot System

Lore is one of three projects in the Camelot system. Understanding where Lore sits clarifies why certain features exist and who consumes them.

## The Big Picture

```
Citadel  →  Realm  →  Lore (you are here)
```

- **Lore** is the task engine — stores all knowledge and state.
- **Realm** is an orchestrator that consumes Lore to run AI agents automatically.
- **Citadel** is a UI that humans use to monitor and control everything.

Lore has zero dependencies on Realm or Citadel. It does not import them, call them, or know they exist. But it is designed to be consumed by them.

## Lore's Two Consumers

**1. Humans via CLI** — A developer types `lore new quest`, `lore ready`, `lore done`. This is the primary developer experience today.

**2. Realm via Python import** — Realm imports from `lore.models` to get typed representations of Lore entities (Quest, Mission, BoardMessage, Artifact, Doctrine, Knight, and others). Realm does this inside automated loops — AI agents running continuously, creating missions, updating statuses, reading state. The canonical import pattern is:

```python
from lore.models import Quest, Mission, QuestStatus, MissionStatus
```

`lore.models.__all__` defines the public API surface — the complete set of names Realm can safely depend on. Any name not in `__all__` is an internal implementation detail. See decisions-010-public-api-stability (lore codex show decisions-010-public-api-stability) for the semver and stability policy.

Every feature in Lore is designed to work cleanly as both a CLI command and a Python API call. The CLI is a thin wrapper; the real interface is the Python modules underneath.

## What This Means for Feature Design

When features appear to exceed what a simple task list needs, the Realm consumer is the reason:

**Mission (lore codex show conceptual-entities-mission) types (knight, constable, human)** — These tell a consuming orchestrator what kind of actor should handle the work. Lore stores and exposes the type; Realm (or AGENTS.md instructions today) interprets it to decide whether to spawn a worker agent, handle inline, or pause for a human.

**Doctrines (lore codex show conceptual-entities-doctrine)** — Pipeline blueprints that define workflow patterns. Lore defines and stores the template; an orchestrator (human or Realm) interprets and executes it.

**Knights (lore codex show conceptual-entities-knight)** — Agent persona definitions (Markdown files). Lore stores them; Realm (and human-driven worker agents today) load them as behavioural context.

## Guardrails

- **Never import from Realm or Citadel.** Not even as an optional dependency.
- **Every CLI command is backed by a Python function** that Realm can call directly.
- **State is authoritative.** If Lore says a Mission is `blocked`, it is `blocked`. No other system maintains a parallel copy.

---

> **Shipped scope vs. future scope**
>
> The sections above describe what is **implemented in `src/lore/` today**.
>
> The original `camelot.md` source document also describes features that are **not yet implemented**. To avoid misleading readers, these are listed here explicitly as future scope:
>
> - **Weapons** — Capability definitions (MCP servers, bash commands, executables). Described as Lore's responsibility for storage; not implemented in `src/lore/`. No `weapons` table, model, or CLI command exists.
> - **Session file pointers** — A path field on each Mission pointing to a JSONL conversation history file. Described as Lore's responsibility for path storage; not implemented in `src/lore/`. No such column exists in the current schema.
>
> Note: per-Quest and per-Mission **message boards** (`lore board add`, `lore board delete`) are implemented — they are no longer future scope. See conceptual-entities-mission (lore codex show conceptual-entities-mission) and conceptual-entities-quest (lore codex show conceptual-entities-quest) for the board behaviour.
>
> These features are part of the intended long-term design of the Camelot system but are deferred to future work.

## Related

- conceptual-entities-mission (lore codex show conceptual-entities-mission) — Mission entity and its types
- conceptual-entities-doctrine (lore codex show conceptual-entities-doctrine) — Doctrine entity
- conceptual-entities-knight (lore codex show conceptual-entities-knight) — Knight entity
- tech-overview (lore codex show tech-overview) — Technology choices and out-of-scope boundaries
