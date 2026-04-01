---
id: example-entity-{entity-name}
title: "{Entity Name}"
related: []
stability: stable
summary: >
  _One to three sentences. What this entity is and what it does in the system.
  Mention its key attributes and lifecycle if it has one._
---

# {Entity Name}

_One paragraph. Define what this entity is, what problem it solves, and how it fits into the system. State what is central about it._

## Core Concepts

| Term | Definition |
|------|------------|
| **{Term 1}** | _Definition_ |
| **{Term 2}** | _Definition_ |

> Add a row per key concept an agent needs to understand before reading the rest of this document.

## How It Works

_Describe the entity's lifecycle, state machine, or key behaviours. Use sub-sections for complex concepts._

### {Lifecycle or Status}

_If this entity has states or transitions, describe them here. Use a diagram and a table._

```
{state-a} ──→ {state-b} ──→ {state-c}
```

| State | Description | Allowed transitions |
|-------|-------------|---------------------|
| `{state-a}` | _Description_ | → `{state-b}` |
| `{state-b}` | _Description_ | → `{state-c}` |
| `{state-c}` | _Terminal state_ | (none) |

### {Other Key Concept}

_Describe another important aspect of how this entity behaves._

## Edge Cases

_List invariants, immutable fields, default values, and rejection rules. These are the things that trip up implementers._

- **{Rule 1}:** _Description_
- **{Rule 2}:** _Description_
