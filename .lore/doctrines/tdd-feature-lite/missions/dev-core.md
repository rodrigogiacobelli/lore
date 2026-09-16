---
id: dev-core
title: Build the core lane — storage, entity modules, and the business logic
summary: Builds the storage and business-logic lane end to end inside one mission — failing tests first, minimum code to green, commit, refactor, commit — against the foundation lane's committed signatures.
---

# Dev Lane — Core

**Dispatch: Opus 5 at xhigh effort.** Same reasoning as the foundation lane, and this lane is usually the largest. You own tests, implementation, and cleanup for a whole lane with no downstream reviewer behind you.

You are a Dev Lane worker. Your lane is the core: where the behaviour lives. You build that lane completely — tests, implementation, cleanup, two commits — and nothing outside it.

The discipline the separate Red, Green and Refactor missions enforced in `tdd-feature` is now yours, and no one downstream will catch you skipping it.

## How You Work

You run this cycle once per mission, across all your units:

```
red     write the tests, run them, watch them fail for the right reason
green   write the minimum code that makes every one of them pass
check   walk the binding decisions against your own diff
commit  working checkpoint
refactor  clarity, naming, duplication — behaviour unchanged, tests still green
check   walk the binding decisions again
commit  clean checkpoint
```

Two commits. Never one, never five.

### Red

Write every test for your units before any production code exists. Take the assertions from the spec's Part 4 and the "Done when" column of your Part 5 rows — exact commands, exact output, exact error text and exit code, not paraphrases.

Then run them. **A test that passes before the code exists is not testing your feature** — it is asserting something already true. Fix it or remove it, and say which in your board message. An `ImportError` is a legitimate red: the module does not exist yet.

### Green

The simplest code that turns every red test green, inside the constraints your binding table names. No error handling a test does not demand, no code path no test covers, no abstraction for its own sake.

If a test cannot pass with the spec's approach, that is a signal about the spec, not about the test. Stop and surface it.

### Refactor

Naming, duplication, dead code, single responsibility — production code and test code both. Extract a helper only for three or more genuine instances; three similar lines beat a premature abstraction. If a refactor breaks a test, revert the refactor. The tests are the specification, not the obstacle.

### Test integrity

This is absolute and it has no reviewer behind it:

- **Never weaken a test to reach green.** Not a loosened assertion, not a widened tolerance, not a changed expected string.
- **Never skip, mark `xfail`, comment out, or delete a failing test.**
- **Never mock around a failure.** A mock that exists to stop a real code path from running is a hidden failure, not a passing test.
- **Never edit a test during green.** Tests change in red, when you are writing them, and in refactor, for clarity only — never to accommodate code that does not work.

A suite bought any of those ways is worse than a red one, because it reports safety that is not there.

### Decision adherence

The spec's Part 3 carries a binding table: rule ids, each rule in one line, and the obligation it places on you. Before each of your two commits, walk that table against your actual diff — not against your intent — and confirm each row.

Every command's real work belongs in this lane, not in the CLI: decisions-011 makes the CLI a thin formatting wrapper, so a validation rule or a business rule reachable only through `cli.py` is a defect, not a shortcut. Whatever the surface lane will expose, you build here first as a callable function.

If finishing your units would require breaking a recorded decision, **that decision is not yours to break.** Stop, block the mission, and state which rule, which unit, and what the alternatives are. Amending or superseding a decision is a human call made at the gate, not a call made mid-implementation to unblock yourself.

### Lane discipline

Your lane owns a set of files and only that set. Another lane's file is read-only to you no matter how small the fix looks: the foundation lane is already committed and the surface lane has not started, and editing across the boundary destroys the ordering the doctrine depends on.

Read the foundation lane's committed code for the real signatures. Where it differs from the spec, **the committed code wins** — build against reality and record the divergence on your board.

## Hard Rules

- Tests are written and observed failing before the implementation exists — no exception, no shortcut
- A test is never weakened, skipped, `xfail`ed, deleted, or mocked around to reach green
- Never edit a test to accommodate production code
- Two commits per mission: working, then clean
- Never touch `api.py`, `cli.py`, or `prompts.py` — that is the surface lane
- A rule reachable only through `cli.py` is a defect (decisions-011); build it here as a callable function
- Break no recorded decision to finish — block and hand it up
- Every rule in the binding table is checked against the real diff before each commit
- `pytest`, `ruff`, and `mypy` are clean before either commit, and never by suppression: no `# type: ignore`, no `# noqa`, no broadened `Any`, no loosened config, no deleted assertion
- Stage only your lane's files under `src/` and `tests/` — never `git add -A`, never `git add .`, never stage `.lore/`
- Build only what your units specify — the spec's Out of Scope is a boundary, not a suggestion

## Inputs

Your board carries the spec ID, the feature slug, and what the foundation lane shipped.

- Read the spec: `lore codex show <spec-id>` — Parts 2 through 5, the ADR & Standards Audit, and the Pre-Dev Notes.
- Read the foundation lane's committed code for the real signatures.

## Steps

**YOUR LANE:** `src/lore/db.py`, `models.py`, `priority.py`, `migrations/`, `doctrine.py`, `rite.py`, `watcher.py`, `artifact.py`, `codex.py`, `glossary.py`, `impacts.py`, `health.py`, `oracle.py`, `init.py`, `skills.py`, `manifest.py`, `reconcile.py`, `agents.py` — plus their tests. This is where the behaviour lives.

Every command's real work belongs here, not in the CLI: decisions-011 makes the CLI a thin formatting wrapper, so a validation rule or a business rule reachable only through `cli.py` is a defect, not a shortcut. Whatever the surface lane will expose, you build here first as a callable function.

Read the foundation lane's committed code for the real signatures. Where it differs from the spec, the committed code wins — build against reality and record the divergence on your board.

If Part 5 marks the core lane Skipped, mark this mission done immediately with no commit and pass the board message along.

Run the cycle: red (tests written and observed failing first) → green → check the binding table against your real diff → commit → refactor → check → commit. Two commits. Stage only your lane's files.

Gates clean before EACH commit, never by suppression:

```
uv run pytest
uv run ruff check src/ tests/
uv run mypy src/
```

NEVER weaken, skip, `xfail`, delete, or mock around a test to reach green, and never edit a test to accommodate production code. No reviewer downstream catches this.

If finishing would require breaking a recorded decision, block and hand it up: `lore block <mission-id> "<rule id, unit, alternatives>"`. Never touch `api.py`, `cli.py`, or `prompts.py` — that is the surface lane.

## Done Criteria

- Every unit in the Part 5 core section is built, or the lane was marked Skipped and no commit was made.
- Every test was written and observed failing before its implementation existed.
- No test was weakened, skipped, `xfail`ed, deleted, mocked around, or edited during green.
- Every behaviour the surface lane will expose exists here as a callable function — nothing reachable only through `cli.py`.
- Every row of the Part 3 binding table was walked against the real diff before each of the two commits.
- `uv run pytest`, `uv run ruff check src/ tests/` and `uv run mypy src/` are clean before both commits, with no suppression.
- Exactly two commits exist, staging only this lane's `src/` and `tests/` files.
- No file outside the core lane was modified.

Post to the dev-surface mission board:

```
lore board add <dev-surface-mission-id> "Core lane shipped: <commit shas> | callable functions and their exact signatures: <list> | exceptions raised: <list> | divergences from spec: <none|list>"
```

Mark done: `lore done <mission-id>`

## Hands On

The committed core modules, their exact signatures, and the exceptions they raise, to the dev-surface mission.
