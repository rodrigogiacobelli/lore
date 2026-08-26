---
id: interactive-init-us-017
title: US-017 — The same tokens are rejected on both surfaces
summary: Four new validators own the agent, access-mode and skill-family token sets
  plus the rule that --agent none cannot be combined with another agent, and both
  plan_init and cli.py call them, so a Python caller and a terminal user get the same
  verdict on the same input.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- decisions-011-api-parity-with-cli
- decisions-017-constrained-flags-use-click-choice
- decisions-010-public-api-stability
- conceptual-workflows-validators
- conceptual-workflows-error-handling
---

# US-017 — The same tokens are rejected on both surfaces

## Metadata

- **ID:** US-017
- **Status:** final
- **Epic:** _CLI Surface_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a Python caller of `lore.api`_, I want _an invalid agent selection rejected exactly as the CLI rejects it_, so that _the same input never produces a different outcome depending on which surface I used_.

## Context

This story exists because the ADR & Standards Enforcer moved a rule. The original spec raised `--agent none` exclusivity "as `click.UsageError` in the handler body", with no `plan_init` counterpart anywhere — and ADR-011 is explicit that "any rule that exists only in the CLI is a bug". Reconciliation #2 in Tech Spec §18 moved it into `validators.validate_agent_selection`, and the spec gate's closing note to Tech Planning is unambiguous: **acceptance criteria must test that rule through both surfaces. A story that only asserts the CLI `UsageError` recreates the breach the enforcer removed.** Every criterion below therefore comes in a matched pair.

`none`-exclusivity is a business rule about a selection, not argv parsing. `validate_agent_selection(agents) -> str | None` uses the error-message-or-`None` shape every validator except `validate_rite_id` already uses. `plan_init` calls it and raises `ValueError` on a non-`None` return; `cli.py` calls the same validator for UX and translates the message into a `click.UsageError`. Neither layer owns a second copy — the pattern `_validate_mission_id` already follows.

All four validators are exported, not one. Every one of the twelve functions in `validators.py` is already in `lore.api.__all__`, and shipping three of the four as importable-but-unexported would recreate the "models-only contract that nobody honours" ADR-010 was written to end (§5.4, §16).

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: `--agent none claude` is a usage error on the CLI

**Given** an empty project directory
**When** the caller runs `lore init --agent none claude`
**Then** exit is 2, stdout carries the usage preamble `Usage: lore init [OPTIONS]` and `Try 'lore init --help' for help.`, stderr carries `Error: --agent none cannot be combined with other agents.`, and no `.lore/` directory is created — the error is raised before any I/O

#### Scenario 2: The identical selection raises through the Python surface

**Given** the same empty directory
**When** a caller runs `plan_init(project_root=tmp, agents=["none", "claude"])`
**Then** `ValueError` is raised whose message is exactly `--agent none cannot be combined with other agents.` — the same string `cli.py` puts in its `UsageError`, from the same `validate_agent_selection` call — and no file is written

#### Scenario 3: `none` alone is accepted on both surfaces

**Given** an empty project directory
**When** the caller runs `lore init --agent none --yes`, and separately `plan_init(project_root=tmp2, agents=["none"])`
**Then** both succeed, both select the `none` target, and both place skills under `.lore/skills/` with no instruction file outside `.lore/`

#### Scenario 4: An unknown agent id is rejected on both surfaces

**Given** an empty project directory
**When** the caller runs `lore init --agent bogus`, and separately `plan_init(project_root=tmp2, agents=["bogus"])`
**Then** the CLI exits 2 with Click's `Invalid value for '--agent': 'bogus' is not one of ...` wording, and the Python call raises `ValueError: Unknown agent: 'bogus'. Known agents: agents-md, claude, cursor, gemini, none, qwen.`

#### Scenario 5: An invalid access mode is rejected on both surfaces

**Given** an empty project directory
**When** the caller runs `lore init --access agentic`, and separately `plan_init(project_root=tmp2, access_mode="agentic")`
**Then** the CLI exits 2 with `Error: Invalid value for '--access': 'agentic' is not one of 'cli', 'native'.`, and the Python call raises `ValueError` naming the token and the accepted set

#### Scenario 6: An invalid skill family is rejected on both surfaces

**Given** an empty project directory
**When** the caller runs `lore init --skills memory typo`, and separately `plan_init(project_root=tmp2, skill_families=["memory", "typo"])`
**Then** the CLI exits 2 with Click's wording listing `'memory', 'machinery', 'workflow', 'all', 'none'`, and the Python call raises `ValueError` naming the token and the accepted set

#### Scenario 7: The four validators are reachable from `lore.api`

**Given** an installed Lore package
**When** a caller runs `from lore.api import validate_access_mode, validate_skill_family, validate_agent_id, validate_agent_selection`
**Then** the import succeeds and all four names are present in `lore.api.__all__`

### Unit Test Scenarios

- [ ] `lore.validators.validate_access_mode`: returns `None` for `"cli"` and `"native"`; returns a message naming the token and the accepted set for anything else, including `None` and a non-string
- [ ] `lore.validators.validate_skill_family`: returns `None` for `"memory"`, `"machinery"`, `"workflow"`, `"all"`, `"none"`; returns a message for anything else
- [ ] `lore.validators.validate_agent_id`: returns `None` for each id in `agents.agent_ids()`; returns a message listing the known ids for anything else
- [ ] `lore.validators.validate_agent_selection`: returns `None` for `[]`, for `["none"]`, and for any combination of non-`none` ids; returns `--agent none cannot be combined with other agents.` for `["none", "claude"]` and for `["claude", "none"]`
- [ ] `lore.validators.validate_agent_selection`: returns the unknown-id message when the selection contains an id absent from the registry, checked before the exclusivity rule
- [ ] `lore.validators.validate_agent_selection`: duplicate ids in the selection are not an error
- [ ] `lore.validators`: the four new functions follow the error-message-or-`None` contract — asserted alongside the existing twelve
- [ ] `tests/unit/test_adr011_no_click_in_operational.py`: still passes — `validators.py` imports no `click`
- [ ] `tests/unit/test_api_surface.py` and `tests/unit/test_api_all_matches_spec.py`: the four names are present in `lore.api.__all__`

---

## Out of Scope

- Declaring the flags themselves — US-016.
- The other nine `lore.api.__all__` additions and the changelog entry — US-023.
- `click.Choice`'s own wording, which ADR-017 pins and this story does not touch.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-8
- Tech Spec: `lore codex show interactive-init-tech-spec` §3.3, §4.2, §5.3, §5.4, §16, §18 Reconciled #2, §19
- `lore codex show decisions-011-api-parity-with-cli` — "any rule that exists only in the CLI is a bug"
- `lore codex show decisions-017-constrained-flags-use-click-choice`
- `lore codex show conceptual-workflows-validators` — the two-layer model

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/validators.py` — add `validate_access_mode(mode) -> str | None`, `validate_skill_family(family) -> str | None`, `validate_agent_id(agent_id) -> str | None`, `validate_agent_selection(agents) -> str | None`, following the shape of `validate_group` at `src/lore/validators.py:124`. The module must stay `click`-free (pinned by `tests/unit/test_adr011_no_click_in_operational.py`) and must not import `lore.agents` at module level if that would create a cycle — resolve the registry lazily inside the function.
  - `src/lore/init.py` — `plan_init` raises `ValueError(message)` on any non-`None` validator return.
  - `src/lore/cli.py` — the `init` handler calls `validators.validate_agent_selection` (through the `lore.api` re-export) and raises `click.UsageError(message)` on a non-`None` return, before any I/O. This is the same mechanism and exit code `lore codex map` uses for conflicting depth flags.
  - `src/lore/api.py` — re-export the four validators in the existing Validators block at `src/lore/api.py:32-36` and add them to `__all__`.
- **Files to create:** none.
- **Schema changes:** none.
- **Dependencies:** US-002 (`agent_ids()`), US-003 (`family_ids()`), US-014 (`plan_init` to raise from), US-016 (the `--agent` flag to translate for).

**Test both surfaces or the story is not done.** Every scenario above is a pair. A CLI-only assertion recreates the ADR-011 breach reconciliation #2 removed, and the spec gate called it out by name.

`click.Choice` still handles the closed-set rejection at the CLI boundary — `--agent bogus` never reaches the validator, because Click rejects it first with the exit-2 wording ADR-017 pins. The validators are what make the **Python** surface reject the same tokens, and `validate_agent_selection` is additionally what makes the `none` rule exist on both. That asymmetry is deliberate and is what §2's three-layer validation row describes.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_error_handling.py` — extended | Anchor `conceptual-workflows-error-handling`; both the CLI exit-2 half and the `plan_init` `ValueError` half of each pair |
| E2E | `tests/e2e/test_api_parity_init.py` — extended | Anchor `conceptual-workflows-python-api`; the `lore.api` import of the four validators |
| Unit | `tests/unit/test_validators.py` — extended | The four functions in isolation |
| Unit | `tests/unit/test_api_surface.py`, `tests/unit/test_api_all_matches_spec.py` — extended | `__all__` membership |

### Test Stubs

```python
# E2E — Scenario 1: `--agent none claude` is a usage error on the CLI
# Exercises: lore codex show conceptual-workflows-error-handling — usage errors exit 2
def test_agent_none_combined_exits_two_on_the_cli(tmp_path, runner):
    pass


# E2E — Scenario 2: The identical selection raises through the Python surface
# Exercises: lore codex show conceptual-workflows-validators — the two-layer model
def test_agent_none_combined_raises_valueerror_through_plan_init(tmp_path):
    pass


# E2E — Scenario 3: `none` alone is accepted on both surfaces
# Exercises: lore codex show conceptual-workflows-validators — the two-layer model
def test_agent_none_alone_accepted_on_both_surfaces(tmp_path, runner):
    pass


# E2E — Scenario 4: An unknown agent id is rejected on both surfaces
# Exercises: lore codex show conceptual-workflows-error-handling — usage errors exit 2
def test_unknown_agent_rejected_on_both_surfaces(tmp_path, runner):
    pass


# E2E — Scenario 5: An invalid access mode is rejected on both surfaces
# Exercises: lore codex show conceptual-workflows-error-handling — usage errors exit 2
def test_invalid_access_mode_rejected_on_both_surfaces(tmp_path, runner):
    pass


# E2E — Scenario 6: An invalid skill family is rejected on both surfaces
# Exercises: lore codex show conceptual-workflows-error-handling — usage errors exit 2
def test_invalid_skill_family_rejected_on_both_surfaces(tmp_path, runner):
    pass


# E2E — Scenario 7: The four validators are reachable from lore.api
# Exercises: lore codex show conceptual-workflows-python-api — the public surface
def test_four_validators_importable_from_lore_api():
    pass


# Unit — validate_access_mode
# Exercises: lore codex show conceptual-workflows-validators — validator contracts
def test_validate_access_mode_accepts_two_tokens_and_rejects_the_rest():
    pass


# Unit — validate_skill_family
# Exercises: lore codex show conceptual-workflows-validators — validator contracts
def test_validate_skill_family_accepts_three_families_plus_two_aggregates():
    pass


# Unit — validate_agent_id
# Exercises: lore codex show conceptual-workflows-validators — validator contracts
def test_validate_agent_id_accepts_every_registry_id():
    pass


# Unit — validate_agent_selection, exclusivity
# Exercises: lore codex show conceptual-workflows-validators — validator contracts
def test_validate_agent_selection_rejects_none_combined_in_either_order():
    pass


# Unit — validate_agent_selection, empty and singleton
# Exercises: lore codex show conceptual-workflows-validators — validator contracts
def test_validate_agent_selection_accepts_empty_and_none_alone():
    pass


# Unit — unknown id checked before exclusivity
# Exercises: lore codex show conceptual-workflows-validators — validator contracts
def test_unknown_id_message_wins_over_the_exclusivity_message():
    pass


# Unit — duplicates are not an error
# Exercises: lore codex show conceptual-workflows-validators — validator contracts
def test_duplicate_agent_ids_are_accepted():
    pass


# Unit — validators.py stays click-free
# Exercises: lore codex show conceptual-workflows-validators — the two-layer model
def test_validators_module_imports_no_click():
    pass
```

### Complexity Estimate

**M** — four short functions, but each acceptance criterion is a matched CLI/API pair and the wiring touches `validators.py`, `init.py`, `cli.py` and `api.py` at once.

### Standards References

- `lore codex show decisions-011-api-parity-with-cli` — the rule this story exists to honour
- `lore codex show decisions-017-constrained-flags-use-click-choice` — the CLI half's wording and exit code, untouched
- `lore codex show conceptual-workflows-validators`
- `lore codex show technical-test-guidelines`
