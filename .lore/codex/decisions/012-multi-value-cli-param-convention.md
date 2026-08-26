---
id: decisions-012-multi-value-cli-param-convention
title: "ADR-012: Multi-value CLI parameters use space-separated syntax"
summary: ADR establishing that CLI parameters accepting multiple values use space-separated syntax (--param a b) not repeatable flags (--param a --param b). Matches the --filter precedent. Applies to all multi-value flags including --scope on lore health.
related: ["conceptual-workflows-filter-list", "conceptual-workflows-health", "ref-lore_cli-commands"]
---

# ADR-012: Multi-value CLI parameters use space-separated syntax

## Context

Two conflicting conventions exist in Click for multi-value CLI parameters:

1. **Repeatable flag** — `--filter a --filter b` — each occurrence adds one value.
2. **Space-separated multi-value** — `--filter a b` — one flag accepts multiple space-separated tokens via `nargs=-1`.

When the `--filter GROUP...` flag was introduced for the five entity list commands, the project chose space-separated multi-value (`nargs=-1`) over repeatable flags. The syntax `lore codex list --filter conceptual decisions` is the established pattern.

When designing `--scope` for `lore health`, the initial tech spec draft specified repeatable flags. This was corrected in Tech Spec v1.1 to match the `--filter` convention. Without a recorded decision, future features risk reintroducing inconsistency.

## Decision

**All CLI parameters that accept multiple values use space-separated multi-value syntax, not repeatable flags.**

Concretely:
- The CLI documentation form is `--param VALUE [VALUE ...]` — not `--param VALUE --param VALUE`.
- The Python API counterpart uses `param: list[str] | None = None` — identical to `filter_groups` on list functions.
- Click offers no built-in option that consumes an unbounded run of tokens: `nargs=-1` on an option raises `TypeError: nargs=-1 is not supported for options`. Two mechanisms deliver the syntax instead, and which one a command uses depends on how many multi-value flags it has.

### One multi-value flag per command: `multiple=True` plus a trailing variadic argument

A command with a single multi-value flag pairs `multiple=True` on the option with a `nargs=-1` positional argument that catches the tokens after the first, then concatenates the two lists in the handler. `lore health --scope` and `--filter` on the five entity `list` commands both use this shape:

```python
@click.option("--scope", "scope", multiple=True, type=click.Choice(list(_VALID_SCOPES)))
@click.argument("extra_scopes", nargs=-1)
def health_cmd(ctx, scope, extra_scopes, json_mode):
    combined = list(scope) + list(extra_scopes)
```

A command may have only one variadic positional, so this shape serves exactly one multi-value flag.

### More than one multi-value flag: `SpaceSeparatedChoice`

A command needing two or more multi-value flags uses `SpaceSeparatedChoice`, a `click.Option` subclass in `cli.py` that greedily consumes the following non-flag tokens into its own value list. `lore init --agent` and `lore init --skills` are its callers. Because the extra tokens are attributed to the flag that opened them, two multi-value flags coexist on one command.

`SpaceSeparatedChoice` changes the parser, not the validator. `type=click.Choice(...)` still owns the closed set, so `decisions-017-constrained-flags-use-click-choice` holds untouched: an out-of-set token — first or greedily consumed — is a `BadParameter` on stderr at exit 2, in Click's standard wording.

The subclass overrides `Option.add_to_parser` and reaches `parser._long_opt`, `parsed.process`, `state.rargs` and `state.opts` — all private to Click. That dependency is why `pyproject.toml` pins `click>=8.3,<9.0`: the hook is exercised against 8.3, and an older in-range Click that stopped consuming the greedy tail would break ADR-017's exit-2 contract on a user's machine rather than at install time.

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
- The `--scope` flag on `lore health` uses `multiple=True` with a trailing `extra_scopes` variadic positional. `scope=None` in the Python API means all scopes. `scope=["codex", "watchers"]` means only those two.
- A command that grows a second multi-value flag moves that flag to `SpaceSeparatedChoice`; the trailing-positional shape cannot be extended to serve two.
- The `click` floor is a load-bearing part of this convention, not a packaging detail. Lowering it without re-verifying the parser hook breaks the space-separated form silently.
- Code review must reject repeatable flags on new parameters accepting multiple values.
- Documentation must always show space-separated examples, not repeated-flag examples.

## Alternatives Rejected

**Repeatable flags (`--param a --param b`).** Rejected — inconsistent with the existing `--filter` precedent. Agents and scripts already expect space-separated multi-value syntax. Diverging creates a two-pattern API where the rule is not learnable from examples.

**Comma-separated single string (`--param "a,b"`).** Rejected — requires callers to parse delimiters manually; breaks shell quoting ergonomics; inconsistent with both existing patterns.

**A standalone ADR for `SpaceSeparatedChoice`.** Rejected — it would put two decision records over one subject and leave this ADR's mechanism prose standing beside it. The decision here is the space-separated syntax; how Click is made to deliver it belongs in the same record.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-04-10 | accepted | Initial decision. Recorded after the `lore health --scope` draft proposed repeatable flags against the `--filter` precedent. |
| 2026-08-25 | accepted (mechanism corrected) | `nargs=-1` is not available on a Click option; the recorded mechanism is corrected to the two shapes that deliver the syntax. `SpaceSeparatedChoice` named as the mechanism for a command with more than one multi-value flag, with the `click>=8.3` floor recorded as the guard on its private-parser dependency. The decision — space-separated, never repeatable — is unchanged. |
