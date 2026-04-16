---
id: decisions-004-mission-type-dumb-storage
title: mission_type is stored and exposed, never interpreted
summary: ADR recording the decision that Lore stores and exposes mission_type but
  does not interpret it or change behaviour based on it. Dispatch semantics belong
  to the consuming tool, not to Lore.
related:
- decisions-001-dumb-infrastructure
- conceptual-workflows-mission-type
---

# ADR 004 — mission_type Is Stored and Exposed, Never Interpreted

## Context

The mission types feature (spec: `docs/specs/mission-types.md`, now archived) introduced a `mission_type` column to the missions table with three values: `knight`, `constable`, and `human`.

The motivation was that not all missions represent worker tasks. Some require human judgment (checkpoints), and others are lightweight orchestration chores that the coordinating agent should handle inline rather than by spawning a dedicated worker. Without a type field, the consuming tool had no signal for deciding how to handle a mission.

The design question was: should Lore change its own behaviour based on `mission_type`, or should it store the value and leave interpretation entirely to the consumer?

## Decision

Lore is dumb infrastructure. The `mission_type` field is stored and exposed, never interpreted by Lore.

- No status transitions differ by type.
- No commands behave differently based on type.
- No dispatch logic exists in Lore.
- No type-based filtering flags are added to `lore ready` or `lore missions`.
- All dependency, blocking, cascade, and closing logic operates identically regardless of `mission_type`.

Lore stores the value and returns it in command output (`lore show`, `lore ready`, `lore missions`, `lore oracle` reports). The consuming tool reads the type and decides what to do.

Today, that consuming tool is an AI agent following instructions in `AGENTS.md`. The instructions describe the dispatch loop: read `lore ready`, check the type, and act according to the team's workflow convention. In future, Realm will replace those instructions with programmatic dispatch.

## Rationale

**Consistency with the dumb infrastructure principle** (see ADR 001). Lore does not orchestrate. Giving Lore dispatch logic based on `mission_type` would violate the principle that all intelligence lives in the consumer, not the storage layer.

**Separation of concerns.** The definition of "what a constable mission means" and "what an orchestrator should do when it sees one" are consumer concerns. They may evolve independently of Lore's storage schema. By keeping interpretation out of Lore, the consuming tool can change dispatch behaviour without a Lore code change.

**Instruction-driven dispatch is sufficient today.** The AGENTS.md instructions provide the dispatch loop. Lore exposing `mission_type` in `lore ready` output is all that is needed for the orchestrator to make correct decisions.

**Simplicity.** Adding type-based behaviour to Lore would require Lore to understand the semantics of each type — what it means for a mission to be `human`, whether a `constable` mission can be claimed by a worker agent, etc. These are policy decisions that belong to the consumer, not the infrastructure.

**No validation is the correct completion of this decision.** If `mission_type` is stored and never interpreted by Lore, then Lore has no principled basis for defining which values are valid. Any fixed set of valid values would itself be an implicit interpretation — it would encode a vocabulary assumption into the storage layer. The original implementation included a `click.Choice` constraint and a DB `CHECK` constraint defending three specific values (`knight`, `constable`, `human`). Those constraints contradicted the decision's own stated intent. Removing all validation — CLI `click.Choice`, DB `CHECK` constraint, and doctrine validator enum — is the logical completion of the ADR's stated decision. Teams define their own type vocabulary; Lore stores whatever string they provide.

**Column naming.** The column is named `mission_type` rather than `type` to avoid ambiguity with the `dependencies` table's existing `type` column (`CHECK (type IN ('blocks'))`). This is self-documenting in SQL queries and joins.

## Alternatives Rejected

**Lore enforces type semantics (e.g., only orchestrators can claim `constable` missions).** Rejected because Lore has no concept of "who is calling." It cannot distinguish an orchestrator agent from a worker agent from a human operator. Enforcing caller-based rules would require authentication and role concepts that are entirely out of scope.

**Type-based filtering flags on `lore ready` and `lore missions` (e.g., `--type knight`).** Rejected because the consumer already reads the type from output and can filter client-side. Adding filter flags to Lore multiplies the CLI surface without proportional benefit. "Lore is a dumb notepad" — the consumer processes the data, not Lore.

**Separate queues or priority lanes per type.** Rejected because the existing priority queue (`lore ready`) is sufficient. Type is orthogonal to priority. A `human` checkpoint at priority 0 should surface before a `knight` task at priority 2 — the existing priority ordering handles this correctly without type-aware queue logic.

**Lore auto-claims `constable` missions.** Rejected because auto-claiming is an orchestration decision. Lore does not know when the orchestrator is ready to handle a constable task. The orchestrator reads `lore ready`, sees the type, and decides.

**Dispatch logic lives in a Lore plugin or extension point.** Rejected as premature. Today's use case is fully served by AGENTS.md instructions. Realm will provide programmatic dispatch in future. No plugin architecture is needed at this stage.
