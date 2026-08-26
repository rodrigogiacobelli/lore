---
id: tfl-feature-spec
title: Feature Spec
summary: >
  The single planning document of the `tdd-feature-lite` doctrine — it replaces
  the PRD, tech spec, user stories, story index, and dev-cycle groups of the heavy
  pipeline with one file in five parts. Part 5 is the dispatch order: there is no
  separate work graph. Self-contained by contract — a dev knight builds a whole
  lane from this document without opening the recon map, the codex, or an ADR.
---

# Feature Spec — {Feature Name}

**Author:** Architect
**Date:** {date}
**Recon map:** _{recon map codex ID}_
**Upstream PRD:** _{PRD codex ID, or "none — Part 1 authored here"}_

---

## Part 1 — Intent and Requirements

### Summary

_{Two or three sentences. What this feature is and what changes for the user.}_

### Success Criteria

- _{Observable, checkable. "`lore rite list` returns grouped rites" — not "rites work well".}_

### In Scope / Out of Scope

**In scope:** _{…}_

**Out of scope:** _{…}_ — _{and why, so a dev knight does not helpfully build it}_

### Workflows

For each user-facing flow, the exact command and the exact output.

**{Workflow name}**
```
$ lore {command} {args}
{exact expected output, character for character}
```

### Requirements

| # | Requirement | Type |
|---|-------------|------|
| R1 | _{…}_ | functional |
| N1 | _{…}_ | non-functional |

> When an upstream PRD exists, carry its intent forward — do not rewrite it.
> Cite it and record only what the PRD leaves open.

---

## Part 2 — Architecture

### Core Decisions

| Decision | Choice | Rationale | Requirement |
|----------|--------|-----------|-------------|
| _{…}_ | _{…}_ | _{…}_ | R{n} |

Every decision traces to a requirement. Every requirement is covered by a decision.

### Data and Storage

_{Schema changes, migration number and direction, file formats, on-disk layout.
"No change" is a valid and useful answer.}_

### Python API Surface

Exact signatures. This is what `lore.api` re-exports; ADR-010 makes `lore.api.__all__`
the public contract and ADR-011 makes the CLI a thin wrapper over it.

```python
def {function}({args}) -> {ReturnType}: ...
```

| Name | Module it lives in | In `lore.api.__all__`? | Raises |
|------|-------------------|------------------------|--------|
| `{name}` | `lore.{module}` | yes \| no (internal) | `{Error}` on `{condition}` |

### CLI Surface

Exact invocation, exact human output, exact `--json` envelope, exact error text and
exit code. Not descriptions — text.

```
$ lore {command}
{exact stdout}
```

```json
{"exact": "envelope"}
```

| Failure | Message | Exit code |
|---------|---------|-----------|
| _{…}_ | `{exact text}` | {0 \| 1 \| 2} |

### Project Structure

Every file that will be created or modified, with the rule that binds it **written
out in full**. "Follow standards" is not a row.

| Path | Lane | New/Modified | Binding rule, stated |
|------|------|--------------|---------------------|
| `src/lore/{module}.py` | foundation | modified | _{e.g. "imports nothing from `lore.*` — `standards-dependency-inversion`"}_ |

---

## Part 3 — Decision and Standards Impact

### Binding Table

Carried forward from the recon map, with the obligation each rule places on the dev
knight filled in.

| Rule id | The rule, in one line | Obligation on the dev knight |
|---------|----------------------|------------------------------|
| `{id}` | _{…}_ | _{what the knight must do or must not do}_ |

### Conflicts

Genuine contradictions between this feature and a settled decision. **Leave
Resolution empty** — the human gate fills it. An unresolved row blocks the gate.

| Rule id | The conflict | Options | Resolution |
|---------|-------------|---------|------------|
| `{id}` | _{…}_ | comply / amend the ADR / supersede | _{empty until the gate}_ |

### New Decisions Needing an ADR

Load-bearing choices this feature makes that no existing ADR governs. Draft the ADR
here; the human gate approves, amends, or rejects it; the scribe writes the permanent
document after the code lands.

**Draft ADR — {title}**
- **Context:** _{…}_
- **Decision:** _{…}_
- **Alternatives rejected:** _{…}_ — _{this section tells a future agent what not to suggest}_

### Expected Codex Updates

The scribe's worklist. Docs to create, update, or retire, and the seeds under
`src/lore/defaults/` this feature moves.

| Codex ID or seed path | Create / Update / Retire | What changed |
|----------------------|--------------------------|--------------|
| `{id}` | update | _{…}_ |

---

## Part 4 — Test Strategy

Every workflow in Part 1 has an E2E scenario. Every module in Part 2 has unit targets.
This section is never empty and never vague.

### E2E

| Scenario | Test file | Exact command | Exact expected output | Workflow codex ID |
|----------|-----------|---------------|----------------------|-------------------|
| _{…}_ | `tests/e2e/test_{x}.py` | `lore {…}` | _{…}_ | `{id}` |

### Unit

| Module / function | Test file | What to assert |
|-------------------|-----------|----------------|
| `lore.{module}.{fn}` | `tests/unit/test_{module}.py` | _{specific cases, including the error paths}_ |

### Conventions

_{Fixture strategy, in-memory SQLite, `CliRunner` usage, what may and may not be
mocked. Name the rule that forbids mocking around a failure.}_

---

## Part 5 — Implementation Plan

The dispatch order. There is no separate work graph — the orchestrator creates one
mission per in-scope lane, in this order, and each dev knight executes its own
section end to end.

### Lane: foundation

_Skipped_ | _In scope_

| # | Unit | Files | Tests first | Done when |
|---|------|-------|-------------|-----------|
| F1 | _{…}_ | _{…}_ | _{which test, asserting what}_ | _{…}_ |

### Lane: core

| # | Unit | Files | Tests first | Done when |
|---|------|-------|-------------|-----------|
| C1 | _{…}_ | _{…}_ | _{…}_ | _{…}_ |

### Lane: surface

| # | Unit | Files | Tests first | Done when |
|---|------|-------|-------------|-----------|
| S1 | _{…}_ | _{…}_ | _{…}_ | _{…}_ |

### Suggested Splits

When one lane carries many units, name the split points here. The orchestrator turns
each into its own mission on the same knight, run **sequentially** — never in
parallel, because concurrent committing agents race the git index.

- _{e.g. "core splits at C4: C1–C3 (registry loading), C4–C7 (health integration)"}_

---

## Pre-Dev Notes

_{Filled at the human gate. Every conflict resolved, every draft ADR ruled on,
every open question closed. Development does not start until this section is
non-empty and no Part 3 Resolution cell is blank.}_
