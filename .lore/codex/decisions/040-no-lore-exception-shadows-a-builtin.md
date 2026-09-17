---
id: decisions-040-no-lore-exception-shadows-a-builtin
title: "ADR-040: A Lore exception is never named after a Python builtin"
summary: >
  ADR recording that no name in lore.api.__all__ equals a Python builtin. The
  codex index raises CodexIndexError(ValueError) and
  CodexIndexNotAuthoredError(CodexIndexError) rather than the IndexError the PRD
  named, because a consumer writing except IndexError around a lore.api call
  would otherwise catch two unrelated failures and be unable to tell them apart.
binds:
  - src/lore/api.py
  - src/lore/index.py
related:
  - decisions-010-public-api-stability
  - standards-public-api-stability
  - standards-facade
  - ref-lore_api-core
  - tech-arch-api-facade
---

# ADR-040: A Lore exception is never named after a Python builtin

## Context

`codex-index-prd` named the codex index's exception `IndexError`, which shadows
a builtin. A consumer writing `except IndexError` around a `lore.api` call would
then catch two unrelated failures and could not tell them apart. Every existing
Lore exception — `ImpactsError`, `GlossaryError`, `OverlayError`, `RiteError`,
`ConflictingDepthFlags`, `ProjectNotFoundError`, `UnknownProjectError`,
`ForeignEntityError` — is builtin-safe, but nothing recorded the rule.

## Decision

A name in `lore.api.__all__` never equals a Python builtin.

The codex index raises `CodexIndexError(ValueError)` and
`CodexIndexNotAuthoredError(CodexIndexError)`.

## Rationale

- **`lore.api` is the one namespace consumers import from.** A name in it that
  collides with a builtin makes an `except` clause ambiguous at the call site,
  and the ambiguity is invisible in the source.
- **Every existing Lore exception already obeys the rule.** Recording it costs
  nothing and stops the first exception that would have broken it.
- **A rule enforced only by prior code earns a record, not another precedent** —
  the same reasoning `decisions-034-missing-required-combination-is-a-usage-error`
  applies to a neighbouring contract.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **`IndexError`, as the PRD named it** | Shadows a builtin in the one namespace consumers import from, so `except IndexError` catches two unrelated failures. |
| **`LoreIndexError`** | A `Lore` prefix on one name in a facade where no other name carries one. |
| **Leave the rule unrecorded** | Every existing exception already obeys it; the first that does not is the one that costs a consumer a debugging session. |

## Consequences

**Easier:**
- A consumer's `except <Name>` around a `lore.api` call catches exactly the Lore
  failure it names.
- Naming a new exception is a lookup against `builtins`, not a judgment call.

**Harder:**
- The obvious short name is unavailable for a handful of concepts (`IndexError`,
  `KeyError`, `LookupError`), so Lore's exception names carry their subject.

## Constraints Imposed

1. **No name in `lore.api.__all__` equals a Python builtin.** A new export whose
   name appears in `builtins` is a defect.
2. **The codex index exceptions are `CodexIndexError(ValueError)` and
   `CodexIndexNotAuthoredError(CodexIndexError)`.** Both are public; renaming
   either is a major bump under ADR-010.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded with the `lore index` command group, whose PRD proposed the first builtin-shadowing export. |
