---
id: decisions-001-dumb-infrastructure
title: "Dumb infrastructure design principles"
summary: "ADR recording the core design principles of Lore: dumb infrastructure, short commands, single-file no-server, and minimise tool calls. The context-aware principle is noted as an unimplemented intention deferred to US-30."
related: ["decisions-004-mission-type-dumb-storage", "decisions-008-help-as-teaching-interface"]
stability: stable
---

# ADR 001 — Dumb Infrastructure Design Principles

## Context

Lore is a task-management tool designed to be used by AI coding agents (specifically Claude Code orchestrators and workers). Early design required explicit principles to constrain scope and prevent feature creep.

Two forces pulled in opposite directions:

1. **Simplicity pressure.** Agents interact via CLI. Every flag, mode, or behavioural nuance costs context window. A tool that "does too much" increases the cognitive load on agents and the probability of misuse.
2. **Convenience pressure.** Agents repeat themselves frequently (re-specifying quest IDs, re-reading output). A smarter tool could reduce that repetition.

The principles below resolve that tension in favour of simplicity, with one principle (context-awareness) deferred rather than implemented.

## Decision

Lore is **dumb infrastructure**. It stores data and answers queries. It does not orchestrate, enforce workflow, or spawn agents. All intelligence lives in the instructions given to the consuming agent. Lore is the notepad with structure.

The following design principles are adopted and implemented:

- **Single file, no server.** SQLite database. No background processes, no ports, no startup/shutdown. `uv tool install` and go.
- **Short commands.** Most operations are `lore [verb]` or `lore [verb] [thing]`. No flags required for common operations.
- **Smart defaults.** `lore list` shows open quests. `lore ready` shows the top unblocked mission. The common case requires zero configuration.
- **JSON output.** All commands support `--json` for programmatic consumption by agents. Human-readable by default.
- **Cross-platform.** Targets Linux and Windows. Python and SQLite are cross-platform; no OS-specific code is used.
- **Metadata is automatic.** Timestamps and status transitions are managed by code, never by the AI. Agents only set business fields (title, description, priority, knight).
- **Minimise tool calls.** Every CLI invocation costs context window. Commands return all relevant information in one call. Bulk operations (`lore claim`, `lore done`, `lore needs`) accept multiple arguments. Creation commands remain one-at-a-time for accuracy.
- **Auto-cascade.** Closing a mission automatically unblocks dependents. Quests with `auto_close` enabled are automatically closed when all missions are done.

## Rationale

- **Dumb infrastructure** keeps Lore's behaviour predictable. Agents can rely on Lore doing exactly what they ask and nothing more. No hidden state transitions, no autonomous decisions.
- **Short commands** reduce token consumption and the probability of flag errors. The most common operations (show status, mark done, claim work) are designed to be one-word verbs.
- **Single file** eliminates the operational overhead of server management, port conflicts, and process lifetime. SQLite WAL mode provides sufficient concurrency for the single-machine, multi-agent use case.
- **Minimise tool calls** directly addresses the constraint that every CLI invocation consumes context window. Bulk operations and information-dense responses reduce the number of round trips an agent must make.
- **Auto-cascade** removes the need for agents to manually update dependent mission statuses, reducing the number of operations required to close out completed work.

## The Context-Aware Principle — Unimplemented / Deferred

The original `docs/spec.md` included a **context-aware** principle:

> *Context-aware. If there's only one active quest, commands infer it. Don't make the user or agent repeat themselves.*

This principle is **not implemented** in the current codebase. No command infers a quest ID from context. It was an intended convenience feature that was deferred.

The feature is specified in user story US-30 (Draft status) and tracked as a documentation gap in the migration audit. It should not be treated as a current design property of Lore.

See: `documentation/user-stories/user-story-30.md`, `documentation/specs/context-aware-quest-inference.md`.

## Alternatives Rejected

**Active orchestration (Lore decides who handles what).** Rejected because it conflates the task registry with the task dispatcher. The consuming tool (initially AGENTS.md instructions, later Realm) owns dispatch logic. Lore owning it would require Lore to understand agent capabilities, availability, and failure modes — all out of scope.

**Rich query language / filtering.** Rejected in favour of `--json` output and consumer-side filtering. Adding filter flags to every command multiplies the CLI surface without proportional benefit. Agents can filter JSON output using standard tools.

**Server mode with persistent connection.** Rejected because it introduces operational complexity (process management, port conflicts, startup/shutdown ordering) that the single-machine use case does not warrant. SQLite WAL provides sufficient concurrency.

**Implicit defaults that change over time.** Rejected. Smart defaults are fixed and documented. Lore does not learn from usage or adjust its defaults based on history. Predictability is more valuable than convenience in an agent-driven context.

**Template engine in doctrines.** Rejected. No variable substitution, no inheritance, no composition. Claude interprets doctrine content. Adding a template engine would require Lore to understand and evaluate templates, which violates the dumb infrastructure principle.
