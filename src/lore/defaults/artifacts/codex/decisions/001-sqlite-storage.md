---
id: example-decision-001
title: "ADR-001: {Decision Title}"
related: []
stability: stable
summary: >
  _One to three sentences. What was decided and why is this ADR worth reading?
  Mention the key trade-off that was resolved._
---

# ADR-001: {Decision Title}

## Context

_Describe the situation that forced this decision. What were the constraints? What was the team trying to achieve? What made this non-obvious?_

Key forces:
- **{Force 1}:** _Why this mattered._
- **{Force 2}:** _Why this mattered._
- **{Force 3}:** _Why this mattered._

## Decision

_State the decision in one or two clear sentences. What was chosen? Where does it apply?_

> Example: Use SQLite as the sole storage backend. Enable WAL journal mode on every connection. Manage schema migrations with `PRAGMA user_version`.

## Rationale

_Why was this the right choice given the forces above? This should be direct, not exhaustive. Two to four bullet points._

- _Reason 1_
- _Reason 2_

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **{Alternative 1}** | _Specific reason. What constraint ruled it out?_ |
| **{Alternative 2}** | _Specific reason._ |
| **{Alternative 3}** | _Specific reason._ |

> The alternatives section is particularly valuable for AI agents — it tells them what not to suggest without reading the full rationale.

## Consequences

**Easier:**
- _What becomes simpler because of this decision._

**Harder:**
- _What becomes more constrained or complex. Be honest._

## Constraints Imposed

_List the specific rules or invariants that exist in the codebase as a direct consequence of this decision. These are the things implementers must not accidentally reverse._

1. **{Constraint 1}:** _Description. Where to look for more detail._
2. **{Constraint 2}:** _Description._

## Status History

| Date | Status | Note |
|------|--------|------|
| {date} | accepted | Initial decision |
