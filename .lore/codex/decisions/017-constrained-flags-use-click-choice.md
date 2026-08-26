---
id: decisions-017-constrained-flags-use-click-choice
title: "ADR-017: Constrained-value CLI flags use click.Choice; invalid values are usage errors (exit 2)"
summary: >
  ADR pinning the previously-implicit contract for CLI flags that accept a fixed
  set of tokens (e.g. lore health --scope): the allowed set is enforced with
  click.Choice, so an out-of-set value is a Click BadParameter (a UsageError
  subclass) → exit code 2 with Click's standard "Invalid value for ..." message.
  Commands must NOT hand-roll a custom validator that rewords the message or
  changes the exit code. Adding a new valid token is allowed; changing the
  error mechanism, wording, or exit code is a breaking contract change.
binds:
  - src/lore/cli.py
related:
  - conceptual-workflows-error-handling
  - conceptual-workflows-health
  - decisions-012-multi-value-cli-param-convention
  - ref-lore_cli-commands
---

# ADR-017: Constrained-value CLI flags use `click.Choice`; invalid values are usage errors (exit 2)

## Context

Several CLI flags accept a value from a fixed, closed set of tokens. The
canonical example is `lore health --scope`, whose tokens are `codex`,
`artifacts`, `doctrines`, `knights`, `watchers`, `schemas`, `glossary`,
`bindings`, `rites` (multi-value, space-separated per ADR-012). The set is
enforced declaratively with `click.Choice`, so passing an out-of-set token
(`lore health --scope xyz`) raises Click's `BadParameter` — a subclass of
`UsageError` — which prints `Error: Invalid value for '--scope': 'xyz' is not
one of '...'` to stderr and exits with **code 2**.

This behaviour was never written down. It fell out of using
`click.Choice`, and downstream authors learned it only by reading existing
commands. That implicitness caused a concrete failure: during the Rites feature,
the spec pipeline proposed replacing `click.Choice` with a hand-rolled validator
that reworded the message to `Invalid scope: ...` and changed the exit code from
2 to 1. That is a breaking change to the CLI error contract, dressed up as an
"operational expansion." It reached implementation before being caught, because
no ADR or standards doc said the existing mechanism was deliberate.

`conceptual-workflows-error-handling` documents the general exit-code contract
(0 success, 1 error, `UsageError` → 2 for invalid option usage) but does not
name `click.Choice` as the required mechanism for constrained-value flags, nor
state that the exit-2 behaviour for a bad value is a contract, not an accident.

## Decision

A CLI flag whose value is constrained to a fixed set of tokens **must** enforce
that set with `click.Choice`. The resulting behaviour for an out-of-set value is
the contract:

- The error is a Click `BadParameter` / `UsageError`.
- It is printed by Click in the standard `Error: Invalid value for '<flag>': ...`
  form, to **stderr**.
- The process exits with **code 2**.

Commands **must not** bypass `click.Choice` with a custom validator in order to
reword the message, change the exit code, or move validation into the business
layer. Validation of a closed token set belongs at the CLI boundary, where Click
already owns it.

**What is allowed:** adding a new valid token to the set (e.g. adding `rites` to
`--scope`). The token set is expected to grow as the system gains entity types.

**What is a breaking change:** changing the enforcement mechanism away from
`click.Choice`, rewording the invalid-value message, or changing the exit code
from 2. Any of the three is recorded by amending this ADR in place — a body edit
plus a dated row in the Status History table below. This project does not create
superseding ADRs and does not mark an ADR superseded.

Changing how Click *parses* the tokens is not a change to this contract.
`SpaceSeparatedChoice` (`decisions-012-multi-value-cli-param-convention`) is a
`click.Option` subclass that consumes a space-separated run of tokens while
leaving `type=click.Choice(...)` as the validator, so all three points above hold
unchanged for a flag that uses it.

## Rationale

- **The exit code is part of the CLI's machine contract.** Tooling and CI branch
  on exit 2 (misuse) vs exit 1 (the command ran and found problems). Collapsing
  misuse into exit 1 makes "you typed a bad flag" indistinguishable from "the
  audit found errors."
- **`click.Choice` is the single source of truth for the allowed set.** It keeps
  the `--help` listing, tab-completion, and validation in sync automatically. A
  hand-rolled validator drifts from the help text.
- **Closed-set validation is a boundary concern, not business logic.** This is
  consistent with ADR-011 (api-parity): the *business* function may also reject
  an unknown token (so the Python API is safe), but the CLI's user-facing misuse
  contract is Click's, at exit 2.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Hand-rolled validator with a friendlier message + exit 1** | Breaks the misuse-vs-error exit-code distinction CI relies on; drifts from the `--help` set; this is the exact regression that prompted the ADR. |
| **Leave it as implicit convention** | Already failed once — an architect re-proposed changing it because nothing said it was deliberate. |
| **Document only in the error-handling doc, no ADR** | Architects scan `decisions/` for binding constraints; a workflow-doc note is weaker signal and was already insufficient. |

## Consequences

**Easier:**
- The invalid-flag contract is now discoverable by anyone designing a new
  constrained-value flag; the next architect inherits the rule instead of
  guessing.

**Harder:**
- New constrained-value flags must route through `click.Choice` even when a
  custom message would read marginally nicer; the uniform machine contract wins.

## Constraints Imposed

1. **Constrained-value flags use `click.Choice`.** No hand-rolled closed-set
   validators at the CLI layer.
2. **Out-of-set value → Click `BadParameter`/`UsageError` → stderr → exit 2.**
   This message text and exit code are a contract.
3. **Adding a valid token is a non-breaking change; changing the mechanism,
   wording, or exit code requires an in-place amendment to this ADR** — a body
   edit plus a dated Status History row. Never a superseding ADR.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-06-02 | accepted | Recorded after the Rites US-006 cycle surfaced a proposed (and rejected) change to the `lore health --scope` invalid-value contract; pins the previously-implicit `click.Choice` / exit-2 behaviour |
| 2026-08-25 | accepted (prose corrected) | Constraint 3 asked for a superseding ADR, which this project does not produce; corrected to require an in-place amendment with a Status History row. A parser-level change such as `SpaceSeparatedChoice` is recorded as outside this contract. The decision — `click.Choice`, Click's wording, exit 2 — is unchanged. |
