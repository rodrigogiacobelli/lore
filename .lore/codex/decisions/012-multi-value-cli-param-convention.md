---
id: decisions-012-multi-value-cli-param-convention
title: "ADR-012: Multi-value CLI parameters use space-separated syntax"
summary: ADR establishing that CLI parameters accepting multiple values use space-separated syntax (--param a b) not repeatable flags (--param a --param b). Matches the --filter precedent. Applies to all multi-value flags including --scope on lore health.
related: ["conceptual-workflows-filter-list", "conceptual-workflows-health", "tech-cli-commands"]
---

# ADR-012: Multi-value CLI parameters use space-separated syntax

**Status:** ACCEPTED

## Context

Two conflicting conventions exist in Click for multi-value CLI parameters:

1. **Repeatable flag** — `--filter a --filter b` — each occurrence adds one value.
2. **Space-separated multi-value** — `--filter a b` — one flag accepts multiple space-separated tokens via `nargs=-1`.

When the `--filter GROUP...` flag was introduced for the five entity list commands, the project chose space-separated multi-value (`nargs=-1`) over repeatable flags. The syntax `lore codex list --filter conceptual decisions` is the established pattern.

When designing `--scope` for `lore health`, the initial tech spec draft specified repeatable flags. This was corrected in Tech Spec v1.1 to match the `--filter` convention. Without a recorded decision, future features risk reintroducing inconsistency.

## Decision

**All CLI parameters that accept multiple values use space-separated multi-value syntax, not repeatable flags.**

Concretely:
- Click parameter definition uses `nargs=-1` (or `multiple=True` with nargs=-1 semantics) — not `multiple=True` with single-value repetition.
- The CLI documentation form is `--param VALUE [VALUE ...]` — not `--param VALUE --param VALUE`.
- The Python API counterpart uses `param: list[str] | None = None` — identical to `filter_groups` on list functions.

**Examples following this convention:**

```
lore codex list --filter conceptual decisions         # two tokens
lore health --scope doctrines knights                 # two tokens
lore health --scope watchers                          # one token
lore health                                           # no flag = all scopes
```

**Counter-examples — do not use:**

```
lore codex list --filter conceptual --filter decisions   # repeatable flag — wrong
lore health --scope doctrines --scope knights            # repeatable flag — wrong
```

## Consequences

- Any new multi-value flag must use space-separated syntax to match `--filter` and `--scope`.
- The `--scope` flag on `lore health` uses `nargs=-1` in Click. `scope=None` in the Python API means all scopes. `scope=["codex", "watchers"]` means only those two.
- Code review must reject repeatable flags on new parameters accepting multiple values.
- Documentation must always show space-separated examples, not repeated-flag examples.

## Alternatives Rejected

**Repeatable flags (`--param a --param b`).** Rejected — inconsistent with the existing `--filter` precedent. Agents and scripts already expect space-separated multi-value syntax. Diverging creates a two-pattern API where the rule is not learnable from examples.

**Comma-separated single string (`--param "a,b"`).** Rejected — requires callers to parse delimiters manually; breaks shell quoting ergonomics; inconsistent with both existing patterns.
