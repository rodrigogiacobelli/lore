---
id: decisions-042-index-search-prints-a-no-match-sentence
title: "ADR-042: lore index search prints a no-match sentence"
summary: >
  ADR recording that lore index search answers an empty result with
  'No clusters matching "<keyword>".' on stdout at exit 0, matching every
  sibling Lore read command rather than printing nothing. The --json envelope
  keeps returning {"clusters": []}. This overrides codex-index-prd, which
  specified exit 0 with no output; the exit code is unchanged.
binds:
  - src/lore/cli.py
related:
  - decisions-001-dumb-infrastructure
  - decisions-034-missing-required-combination-is-a-usage-error
  - conceptual-workflows-index
  - conceptual-workflows-error-handling
  - conceptual-workflows-json-output
  - ref-lore_cli-commands
---

# ADR-042: lore index search prints a no-match sentence

## Context

Every existing Lore read command answers an empty result with a sentence.
`lore codex search` prints `No documents matching "<kw>".`, `lore codex list`
prints `No codex documents found.`, and `lore index build` itself prints
`No codex documents to index.` on an empty codex.

`codex-index-prd` specified that `lore index search` print nothing at all and
exit 0. The convention the other commands follow was enforced by prior code
alone — no ADR and no standards document stated it — which is the condition
`decisions-034-missing-required-combination-is-a-usage-error` was written to end
for a neighbouring contract.

## Decision

`lore index search` answers an empty result with one line on stdout:

```
No clusters matching "<keyword>".
```

The exit code is **0**. The `--json` envelope is unchanged and keeps returning
`{"clusters": []}`.

This overrides `codex-index-prd`, which specified "exit 0 with no output when
nothing matches". Only the human-format output gains a line; the exit code was
0 before and is 0 now.

## Rationale

- **An agent that learns the rule once should not meet an exception here.**
  Every sibling read command answers an empty result with a sentence.
- **`decisions-001-dumb-infrastructure` budgets round trips.** Distinguishing
  "no cluster matched" from "the command produced nothing" without a confirming
  call is exactly what that budget buys.
- **Option (b)'s argument is already answered.** Machine-clean stdout is what
  the `--json` envelope is for, and it returns `{"clusters": []}`.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Empty stdout at exit 0, recorded as a deliberate divergence** | Keeps stdout machine-clean for a caller piping the human format — which the `--json` envelope already answers — at the cost of one rule an agent can otherwise learn once. |
| **Exit non-zero on no match** | A search that finds nothing has not failed, and exit 1 is reserved for a command that ran and failed. |
| **A count line only under a TTY** | Behaviour that differs by terminal is behaviour an agent cannot predict. |

## Consequences

**Easier:**
- A caller distinguishes an empty result from a silent failure without a second
  call.
- One no-match convention covers `lore codex search`, `lore codex list`,
  `lore index build` and `lore index search`.

**Harder:**
- A caller piping the human format gets a line it has to filter; the `--json`
  envelope is the supported machine surface.

## Constraints Imposed

1. **A Lore read command answers an empty result with a sentence on stdout at
   exit 0.** Printing nothing is a defect.
2. **The literal is `No clusters matching "<keyword>".`** — the keyword as
   given, in double quotes, following `lore codex search`'s shape with ADR-035's
   noun.
3. **The `--json` envelope is unaffected.** An empty result is
   `{"clusters": []}` in both cases.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded with the `lore index` command group; overrides `codex-index-prd`'s no-output specification for the no-match case. |
