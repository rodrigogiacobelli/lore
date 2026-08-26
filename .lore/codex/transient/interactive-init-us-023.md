---
id: interactive-init-us-023
title: US-023 — Thirteen new names on the public API, with the changelog entry that must ship with them
summary: lore.api re-exports AccessMode, FileAction, AgentTarget, PlannedFile,
  InitAnswers, InitPlan, InitResult, plan_init, apply_init and the four new validators,
  and CHANGELOG.md gains the 0.10.0 entry ADR-010 requires to move with them.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-api-facade
- standards-public-api-stability
- decisions-010-public-api-stability
- conceptual-workflows-python-api
---

# US-023 — Thirteen new names on the public API, with the changelog entry that must ship with them

## Metadata

- **ID:** US-023
- **Status:** final
- **Epic:** _Release Obligations_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _Realm_, I want _every new init type and function reachable through `lore.api` and recorded in the changelog_, so that _the public surface I depend on stays the one contract that says what Lore offers_.

## Context

ADR-010 makes `lore.api.__all__` the contract, and `standards-public-api-stability` is explicit that "adding a new name to the public surface requires re-exporting it through `lore.api`, adding it to `lore.api.__all__`, and updating the changelog." Tech Spec §5.4 lists the thirteen, placed in the existing domain blocks rather than sprinkled:

- **Operational dataclasses block:** `AccessMode`, `FileAction`, `AgentTarget`, `PlannedFile`, `InitAnswers`, `InitPlan`, `InitResult`
- **Init / reports / config block:** `plan_init`, `apply_init`, beside the existing `run_init`
- **Validators block:** `validate_access_mode`, `validate_skill_family`, `validate_agent_id`, `validate_agent_selection`

All four validators are exported, not one. Every one of the twelve functions in `validators.py` is already in `__all__`; shipping three of the four as importable-but-unexported would recreate exactly the "models-only contract that nobody honours" ADR-010 was written to end.

Reconciliation #4 in Tech Spec §18 caught the omission that makes this its own story: the original spec added thirteen `__all__` names and four `Config` fields with **no mention of `CHANGELOG.md` anywhere**. ADR-010's Consequences require contributors to update `CHANGELOG.md` and `lore.api.__all__` together whenever the public API changes, and `standards-public-api-stability` repeats it twice. The entry is mandatory, not optional.

Thirteen `__all__` additions plus four new `Config` fields are all additive, so the semver table puts this at a **minor** bump — `0.9.0` → `0.10.0` — with no breaking-change notice. Nothing leaves `__all__` and no signature narrows. The retired skills are seeded files, not public API names.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Every new name is importable from `lore.api`

**Given** an installed Lore package
**When** a caller runs `from lore.api import AccessMode, FileAction, AgentTarget, PlannedFile, InitAnswers, InitPlan, InitResult, plan_init, apply_init, validate_access_mode, validate_skill_family, validate_agent_id, validate_agent_selection`
**Then** the import succeeds and each of the thirteen names is present in `lore.api.__all__`

#### Scenario 2: Nothing left the public surface

**Given** the `lore.api.__all__` list from the previous release
**When** it is compared against the current one
**Then** every previous name is still present, and the difference is exactly the thirteen additions

#### Scenario 3: The changelog carries a `0.10.0` entry naming the additions

**Given** `CHANGELOG.md`
**When** a test reads its top-most released section
**Then** it is `0.10.0`, it has an `Added` section naming the thirteen `__all__` names, the four `Config` fields, the four `init-*` config keys, the `skills` health scope and the `lore init` flag surface, and a `Changed` section naming the raised dependency floors and the skill-catalogue consolidation — and it has no `Removed` section and no `BREAKING CHANGE:` block

#### Scenario 4: `api.py` still defines nothing

**Given** `src/lore/api.py`
**When** its AST is walked
**Then** it contains zero `def` and zero `class` nodes — the facade purity `tech-arch-api-facade` pins, unchanged by thirteen additions

#### Scenario 5: The underscore aliases are complete

**Given** `src/lore/api.py`
**When** a test reads its underscore-alias block
**Then** `_prompts`, `_agents` and `_skills` are present alongside the existing twelve, and `tests/unit/test_cli_imports_only_api.py` still passes

### Unit Test Scenarios

- [ ] `lore.api.__all__`: contains all thirteen names, each exactly once
- [ ] `lore.api.__all__`: has no duplicate entries overall
- [ ] `lore.api`: every name in `__all__` resolves to a real attribute — the existing surface test, extended
- [ ] `lore.api`: the seven dataclass and enum names come from `lore.initplan`, asserted by `__module__`
- [ ] `lore.api`: `plan_init`, `apply_init` and `run_init` all come from `lore.init`
- [ ] `lore.api`: the four validators come from `lore.validators`
- [ ] `lore.api`: `_prompts` does not pull `questionary` into `sys.modules` at import time
- [ ] `CHANGELOG.md`: the top-most released version matches `pyproject.toml`'s `version`
- [ ] `tests/unit/test_api_all_matches_spec.py`: the spec list it compares against is updated to the thirteen new names

---

## Out of Scope

- The `pyproject.toml` version bump and dependency changes — US-024.
- The `Config` fields themselves — US-013; `Config` is already exported, so only the changelog obligation lands here.
- The codex updates to `ref-lore_api-core`, `api-reference`, `api-guide`, `standards-public-api-stability` and `tech-arch-api-facade` — owned by the phase-5 codex-apply mission (`lore show q-3c9c/m-d053`).

---

## References

- PRD: `lore codex show interactive-init-prd` FR-32, FR-33, FR-34
- Tech Spec: `lore codex show interactive-init-tech-spec` §3, §5.1, §5.4, §11, §18 Reconciled #3 and #4
- `lore codex show decisions-010-public-api-stability`
- `lore codex show standards-public-api-stability`
- `lore codex show tech-arch-api-facade`

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/api.py` — add the seven operational dataclasses to the `# --- Operational dataclasses (sourced from their owning modules) ---` block at `src/lore/api.py:20-23`; add `plan_init` and `apply_init` beside `run_init`; add the four validators to the block at `src/lore/api.py:32-36`; add all thirteen to `__all__`. Confirm `_prompts`, `_agents` and `_skills` are in the underscore-alias block at `src/lore/api.py:163-175` (US-016 adds two, US-018 the third).
  - `CHANGELOG.md` — a `0.10.0` entry with the `Added` and `Changed` content Tech Spec §11 states.
- **Files to create:** none.
- **Schema changes:** none.
- **Dependencies:** US-001, US-013, US-014, US-015, US-017, US-021 — every name must exist before it can be exported. This story lands late by construction.

`api.py` must stay at zero `def` and zero `class`: every one of the thirteen is an import plus an `__all__` entry, nothing else. That is what `tech-arch-api-facade` pins and what Scenario 4 re-asserts.

`tests/unit/test_api_surface.py` and `tests/unit/test_api_all_matches_spec.py` both carry lists that have to grow by thirteen. The second is the one that will fail loudest if a name is added to `__all__` without being added to the spec list — that failure is the intended signal, not an obstacle.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_api_parity_init.py` — extended | Anchor `conceptual-workflows-python-api`; the import scenario |
| Unit | `tests/unit/test_api_surface.py` — extended | `__all__` membership and resolution |
| Unit | `tests/unit/test_api_all_matches_spec.py` — extended | The spec list |
| Unit | `tests/unit/test_package_distribution.py` — extended | `CHANGELOG.md` top version matches `pyproject.toml` |

### Test Stubs

```python
# E2E — Scenario 1: Every new name is importable from lore.api
# Exercises: lore codex show conceptual-workflows-python-api — the public surface
def test_thirteen_new_names_importable_from_lore_api():
    pass


# E2E — Scenario 2: Nothing left the public surface
# Exercises: lore codex show conceptual-workflows-python-api — the public surface
def test_no_name_removed_from_all():
    pass


# E2E — Scenario 3: The changelog carries a 0.10.0 entry naming the additions
# Exercises: lore codex show conceptual-workflows-python-api — the public surface
def test_changelog_0_10_0_entry_names_every_addition():
    pass


# E2E — Scenario 4: api.py still defines nothing
# Exercises: lore codex show conceptual-workflows-python-api — facade purity
def test_api_module_contains_no_def_or_class():
    pass


# E2E — Scenario 5: The underscore aliases are complete
# Exercises: lore codex show conceptual-workflows-python-api — facade purity
def test_underscore_aliases_include_prompts_agents_and_skills():
    pass


# Unit — __all__ membership and uniqueness
# Exercises: lore codex show conceptual-workflows-python-api — the public surface
def test_all_contains_the_thirteen_names_exactly_once():
    pass


# Unit — every __all__ name resolves
# Exercises: lore codex show conceptual-workflows-python-api — the public surface
def test_every_all_name_resolves_to_an_attribute():
    pass


# Unit — provenance of the new names
# Exercises: lore codex show conceptual-workflows-python-api — the public surface
def test_new_names_come_from_their_owning_modules():
    pass


# Unit — the prompts alias stays cheap
# Exercises: lore codex show conceptual-workflows-python-api — facade purity
def test_prompts_alias_does_not_import_questionary():
    pass


# Unit — changelog and pyproject agree on the version
# Exercises: lore codex show conceptual-workflows-python-api — release obligations
def test_changelog_top_version_matches_pyproject():
    pass
```

### Complexity Estimate

**M** — mechanically small (imports, `__all__` entries and a changelog section) but it touches the project's tightest contract, and three existing surface tests carry lists that must be updated in lockstep.

### Standards References

- `lore codex show decisions-010-public-api-stability` — `CHANGELOG.md` and `__all__` move together
- `lore codex show standards-public-api-stability` — the semver table putting this at a minor bump
- `lore codex show tech-arch-api-facade` — zero `def`, zero `class`
- `lore codex show technical-test-guidelines`
