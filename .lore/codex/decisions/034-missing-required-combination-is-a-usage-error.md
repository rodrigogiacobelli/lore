---
id: decisions-034-missing-required-combination-is-a-usage-error
title: "ADR-034: A missing required flag combination is a usage error at exit 2"
summary: >
  ADR recording that when a command requires at least one of a set of flags and
  receives none, it raises click.UsageError — exit 2, stderr, Click's standard
  Error prefix — rather than emitting its own message at exit 1. Covers lore
  edit and lore doctrine edit, and binds any future command with the same
  at-least-one-of shape.
binds:
  - src/lore/cli.py
related:
  - decisions-017-constrained-flags-use-click-choice
  - decisions-011-api-parity-with-cli
  - conceptual-workflows-error-handling
  - conceptual-workflows-doctrine-edit
---

# ADR-034: A missing required flag combination is a usage error at exit 2

## Context

`lore edit` raised `click.UsageError` when no field flag was supplied, giving
exit 2 with Click's `Error: ` prefix on stderr. That behaviour was enforced by
nothing but prior code — no ADR, no standards document, one workflow document
describing it as observed behaviour. `lore doctrine edit` gained the identical
condition: a run with none of `-d`, `-m` or `--remove-mission` has nothing to
do. Without a recorded rule, the two commands were free to answer one class of
mistake two different ways.

## Decision

When a command requires at least one of a set of flags and receives none, it
raises `click.UsageError` — exit 2, stderr, Click's standard `Error: ` prefix —
rather than emitting its own message at exit 1.

`lore doctrine edit` with no flags raises
`click.UsageError("Nothing to update: pass -d, -m, or --remove-mission")`.

The error is raised through Click, never hand-rolled: ADR-017 forbids rewording
or re-coding a usage error.

## Rationale

- **A missing flag is a usage error, and Click already has an exit code for
  it.** Exit 2 is what every other malformed invocation produces, so an agent
  that learns "2 means I called it wrong" learns one rule.
- **Two commands answering one class of mistake two ways is a contract with a
  hole in it.** `lore edit` set the precedent; a second command diverging from
  it makes the exit code unpredictable per command.
- **A contract enforced only by prior code earns a record, not another
  precedent.** This is exactly the case where the next author has nothing to
  read and guesses.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Emit the message directly and exit 1** | Would give two commands two answers for one class of mistake, and exit 1 already means "the operation ran and failed", which this did not. |
| **Follow the existing precedent without recording it** | Leaves the contract enforced only by prior code and one workflow document, which is the condition that produced the ambiguity. |
| **Hand-roll the message to control its wording** | ADR-017 forbids rewording or re-coding a usage error; Click's prefix and exit code are the contract. |

## Consequences

**Easier:**
- An agent reading an exit code can distinguish "I called it wrong" (2) from
  "it ran and failed" (1) without a per-command table.
- A new command with the same at-least-one-of shape has a rule to follow rather
  than a precedent to infer.

**Harder:**
- The message text is Click's to format, so a command cannot present this
  particular failure in its own voice.
- A caller that treats any non-zero exit as one condition sees no difference,
  and gets the distinction only by reading the code.

## Constraints Imposed

1. **A command requiring at least one of a set of flags raises
   `click.UsageError` when it receives none.** Emitting a bespoke message at
   exit 1 for that condition is a defect.
2. **The error is raised through Click.** Hand-rolling the prefix, the stream
   or the exit code is forbidden by ADR-017.
3. **The rule is about a missing *combination*, not a missing value.** A flag
   with an out-of-set value is ADR-017's territory.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded alongside `lore doctrine edit`'s no-flag `click.UsageError`, following `lore edit`'s existing behaviour. |
