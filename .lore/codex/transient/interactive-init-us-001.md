---
id: interactive-init-us-001
title: US-001 — Plan and result types on a stdlib-only leaf module
summary: A Python caller receives typed, frozen plan and result objects from a new
  stdlib-only lore.initplan module — AccessMode, FileAction, AgentTarget, PlannedFile,
  InitAnswers, InitPlan and InitResult — so the plan/apply split has a shape before
  anything computes or writes one.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- conceptual-workflows-python-api
- tech-arch-api-facade
- tech-arch-source-layout
- standards-dependency-inversion
- decisions-010-public-api-stability
---

# US-001 — Plan and result types on a stdlib-only leaf module

## Metadata

- **ID:** US-001
- **Status:** final
- **Epic:** _Type and Data Foundations_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _Realm, importing Lore as a library_, I want _a typed, immutable description of what an initialisation would do_, so that _I can inspect every create, overwrite, removal and conflict before deciding whether to perform it_.

## Context

FR-32 and FR-33 require Realm to compute an initialisation without performing it and then perform a previously computed one. That split needs a vocabulary before it needs behaviour. Tech Spec §5.1 rules that these types live in a new `src/lore/initplan.py` rather than in `models.py` (which is the entity-record index, every member carrying `from_row`/`from_dict`) and rather than in `init.py` (because `reconcile.py` and `skills.py` both construct `PlannedFile` values and `init.py` imports both — `standards-dependency-inversion` puts the types below all three).

`tech-arch-api-facade` pins `api.py` at zero `def` and zero `class`, so nothing may be defined there; the module has to exist on its own and be re-exported. This story delivers the module and nothing that uses it.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: A Python caller imports and constructs every plan type

**Given** an installed Lore package
**When** a caller runs `from lore.initplan import AccessMode, FileAction, AgentTarget, PlannedFile, InitAnswers, InitPlan, InitResult`
**Then** the import succeeds, and constructing an `InitPlan` with `project_root=Path("/tmp/x")`, an `InitAnswers`, an empty `targets` tuple, an empty `files` tuple, an empty `prompts_needed` tuple and an empty `conflicts` tuple yields an object whose `has_changes` is `False` and whose `counts()` is `{}`

#### Scenario 2: The types are immutable

**Given** an `InitPlan` instance `plan`
**When** a caller executes `plan.files = ()`
**Then** Python raises `dataclasses.FrozenInstanceError`, and the same holds for `InitAnswers`, `AgentTarget`, `PlannedFile` and `InitResult`

#### Scenario 3: `lore.initplan` pulls in no Lore module

**Given** a fresh interpreter
**When** a caller runs `import lore.initplan` and inspects `sys.modules`
**Then** no `lore.*` module other than `lore` and `lore.initplan` has been imported as a result, and the module's AST contains no `import`/`from` statement naming a `lore.` module

### Unit Test Scenarios

- [ ] `lore.initplan.AccessMode`: is a `StrEnum` with exactly the members `CLI = "cli"` and `NATIVE = "native"`
- [ ] `lore.initplan.FileAction`: is a `StrEnum` with exactly the members `CREATE`, `OVERWRITE`, `SECTION`, `REMOVE`, `CONFLICT`, `KEEP`, whose values are the lower-case member names
- [ ] `lore.initplan.AgentTarget`: carries `id`, `label`, `instruction_file`, `skills_dir`; the last two accept `None`
- [ ] `lore.initplan.PlannedFile`: carries `path`, `action`, `kind`, `source`, `digest`, `detail`; `digest` and `detail` accept `None`
- [ ] `lore.initplan.InitAnswers`: carries `agents`, `access_mode`, `skill_families`, `on_existing_agent_file`, `root_gitignore`, `skills_gitignore`, `on_conflict`; `agents` and `skill_families` are tuples, not lists
- [ ] `lore.initplan.InitPlan.counts`: returns a dict keyed by `FileAction` value with the number of `files` entries carrying that action; actions with zero entries are absent from the dict
- [ ] `lore.initplan.InitPlan.has_changes`: `False` when `files` is empty; `False` when every entry is a no-op action the planner never emits; `True` when any entry carries `CREATE`, `OVERWRITE`, `SECTION` or `REMOVE`
- [ ] `lore.initplan.InitPlan.conflicts`: holds exactly the subset of `files` whose action is `FileAction.CONFLICT`
- [ ] `lore.initplan.InitResult`: carries `project_root`, `messages`, `applied`, `skipped`, `manifest_path`; `messages` is a tuple of `str`
- [ ] `lore.initplan`: every dataclass declared with `frozen=True`, asserted by `dataclasses.fields` plus a mutation attempt per class

---

## Out of Scope

- Any function that populates an `InitPlan` — `plan_init` is US-014.
- Any function that consumes one — `apply_init` is US-015.
- Re-export through `lore.api.__all__` — US-023.
- Validation of the token strings these dataclasses hold — US-017.

---

## References

- PRD: `lore codex show interactive-init-prd`
- Tech Spec: `lore codex show interactive-init-tech-spec` §5.1, §5.2
- `lore codex show tech-arch-api-facade`
- `lore codex show standards-dependency-inversion`

---

## Tech Notes

### Implementation Approach

- **Files to create:** `src/lore/initplan.py` — the seven names in Tech Spec §5.2, verbatim. Imports `dataclasses`, `enum` and `pathlib` only. Mirrors `src/lore/validators.py`'s foundation position: zero `lore.*` imports.
- **Files to modify:** none.
- **Schema changes:** none.
- **Dependencies:** none. This is the first story in the feature and every later module imports it.

Notes for the implementer: `enum.StrEnum` is available because `requires-python = ">=3.11"` in `pyproject.toml`. `InitPlan.counts()` returns `dict[str, int]` keyed by the `FileAction` *value* (`"create"`, not `"FileAction.CREATE"`), because Tech Spec §4.3 renders the counts line straight from it.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_api_parity_init.py` — extended | Anchor `conceptual-workflows-python-api`; the Python-surface import and immutability scenarios |
| Unit | `tests/unit/test_initplan.py` — NEW | One file per source module (`technical-test-guidelines` §4) |

### Test Stubs

```python
# E2E — Scenario 1: A Python caller imports and constructs every plan type
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_initplan_types_importable_and_constructible():
    # Given: an installed package
    # When: import the seven names from lore.initplan and build an empty InitPlan
    # Then: has_changes is False and counts() == {}
    pass


# E2E — Scenario 2: The types are immutable
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_plan_types_are_frozen():
    # Given: one instance of each dataclass
    # When: assign to any field
    # Then: dataclasses.FrozenInstanceError
    pass


# E2E — Scenario 3: lore.initplan pulls in no Lore module
# Exercises: lore codex show conceptual-workflows-python-api — module boundaries
def test_initplan_imports_no_lore_module():
    # Given: the parsed AST of src/lore/initplan.py
    # When: walk Import and ImportFrom nodes
    # Then: no node names a module starting with "lore."
    pass


# Unit — AccessMode member set
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_access_mode_members():
    # AccessMode is a StrEnum with exactly cli and native
    pass


# Unit — FileAction member set
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_file_action_members():
    # Exactly six members; each value equals its lower-cased name
    pass


# Unit — AgentTarget / PlannedFile / InitAnswers / InitResult field shapes
# Exercises: lore codex show conceptual-workflows-python-api — key presence on all code paths
def test_dataclass_field_names():
    # dataclasses.fields(...) names match Tech Spec §5.2 exactly, per class
    pass


# Unit — InitPlan.counts
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_counts_tallies_per_action_and_omits_zeroes():
    # Build files with 2 CREATE and 1 REMOVE; counts() == {"create": 2, "remove": 1}
    pass


# Unit — InitPlan.has_changes
# Exercises: lore codex show conceptual-workflows-python-api — edge-case characterisation
def test_has_changes_false_for_empty_plan():
    # files == () -> has_changes is False
    pass


# Unit — InitPlan.conflicts
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_conflicts_is_the_conflict_subset():
    # Mixed actions in; conflicts holds only the CONFLICT entries, same order
    pass


# Unit — every dataclass frozen
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_every_dataclass_is_frozen():
    # dataclasses.fields + a mutation attempt on each of the five dataclasses
    pass
```

### Complexity Estimate

**S** — one new stdlib-only module of pure declarations plus two derived members; no I/O, no dependencies, no behaviour to reconcile.

### Standards References

- `lore codex show tech-arch-api-facade` — why nothing may be defined in `api.py`
- `lore codex show tech-arch-source-layout` — where a new module belongs
- `lore codex show standards-dependency-inversion` — why the types sit below `init.py`
- `lore codex show technical-test-guidelines` — unit files never import `lore.cli`
