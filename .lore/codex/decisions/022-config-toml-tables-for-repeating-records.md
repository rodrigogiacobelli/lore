---
id: decisions-022-config-toml-tables-for-repeating-records
title: "ADR-022: .lore/config.toml admits tables for repeating records, and only for those"
summary: >
  ADR narrowing ADR-013's flat key-value shape for .lore/config.toml: a TOML
  table or array-of-tables is permitted when a setting is a multi-field or
  repeating record ([shared], [[descendants]]), and stays forbidden for a
  single scalar, boolean, or flat string list, which stay root-level keys.
binds:
  - src/lore/config.py
related:
  - decisions-013-toml-for-config-yaml-for-glossary
  - decisions-021-health-reports-are-ephemeral-by-default
  - conceptual-workflows-nested-projects
  - tech-arch-initialized-project-structure
---

# ADR-022: .lore/config.toml admits tables for repeating records, and only for those

## Context

ADR-013 chose TOML for `.lore/config.toml` on the strength of a flat, human-edited
key-value shape. ADR-021 later rejected a `[health]` table proposed for a single
scalar setting (`health-report-retention`), reasoning that a table sets a
precedent that splits the file's namespace for every setting after it.

Nested Projects' export configuration needs two settings a flat key cannot express
cleanly: `[shared]`, a two-field record (`exports`, `glossary`), and
`[[descendants]]`, a repeating three-field record (`name`, `path`, `exports`). A
flat encoding of a repeating record needs an index convention —
`descendant-1-name`, `descendant-1-path`, `descendant-2-name`, … — that no reader
can guess and no loader can validate cleanly.

## Decision

A TOML table or array-of-tables in `.lore/config.toml` is permitted when, and only
when, the setting is a **record with more than one field**, or a **repeating
record**. A setting that is a single scalar, a boolean, or a flat list of strings
stays a root-level key. Each table parses into a frozen dataclass on `Config`
(`SharedExports`, `DescendantExport`) with the same fail-soft contract as a flat
key: an invalid or malformed entry falls back to the default and emits at most
one stderr warning per process.

## Rationale

- **ADR-021's reasoning was scoped to a single scalar setting.** A table
  genuinely does not help express one boolean or one string; it does help
  express a repeating record with named fields, which is a different shape of
  problem.
- **`[[descendants]]` cannot be flattened without inventing a convention.** An
  indexed key scheme (`descendant-1-name = …`) is unguessable for a human editor
  who has not read the loader's source, and unvalidatable without extra
  bookkeeping to detect a skipped index or a mismatched field count.
- **The fail-soft contract carries over unchanged.** A malformed table degrades
  to the default the same way a malformed flat key already does — this ADR
  changes what shapes are representable, not how a bad value is handled.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Flat indexed keys (`descendant-1-name`, `descendant-1-path`, …)** | Unguessable for a human editor and unvalidatable without inventing index bookkeeping — worse on both axes than the table it replaces. |
| **A separate `.lore/projects.toml`** | A fourth path-discovered config file for one feature, when ADR-018 already classes `config.toml` as the home for exactly this kind of project-level setting. |
| **Permit tables freely, with no boundary** | Reopens the question ADR-021 closed and invites `[health]`, `[init]`, `[codex]` namespacing — the exact cost ADR-021 named when it rejected a table for one scalar. |

## Consequences

**Easier:**
- `[shared]` and `[[descendants]]` are validatable, human-editable records with
  named fields, with no index convention to invent or document.
- ADR-021's default stays intact for every setting that is genuinely a scalar —
  this ADR narrows the boundary rather than reopening it.

**Harder:**
- `.lore/config.toml`'s grammar is no longer purely flat; a reader must know
  which settings are records (and may nest) and which are scalars (and must
  not).

## Constraints Imposed

1. **A table or array-of-tables is permitted only for a multi-field or
   repeating record.** A single scalar, boolean, or flat list of strings stays
   a root-level key. Reopening tables for a scalar setting requires amending
   this ADR, not citing it.
2. **Each table parses into a frozen dataclass on `Config`**, with the same
   fail-soft contract as a flat key — an invalid entry falls back to the
   default and warns at most once per process.
3. **ADR-021's constraint still binds for scalar settings.** This ADR narrows
   its scope to admit records; it does not reverse the rejection of a table for
   a single scalar.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-02 | accepted | Recorded alongside `[shared]` and `[[descendants]]` in `.lore/config.toml`, the two tables Nested Projects introduces. |
