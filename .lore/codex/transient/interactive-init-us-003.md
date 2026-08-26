---
id: interactive-init-us-003
title: US-003 — The skill catalogue ships as data with a retirement ledger
summary: A packaged src/lore/defaults/skills-catalogue.yaml records the ten skills,
  their three families and the thirteen retired skills with the successor each was
  renamed or merged into, loaded by lore.skills with family resolution that accepts
  the aggregate tokens all and none on both surfaces.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-skill-catalogue
- decisions-006-no-seed-content-tests
- decisions-011-api-parity-with-cli
- conceptual-workflows-init-interactive
---

# US-003 — The skill catalogue ships as data with a retirement ledger

## Metadata

- **ID:** US-003
- **Status:** final
- **Epic:** _Type and Data Foundations_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a developer upgrading Lore across several releases_, I want _the release to carry a record of which skills exist, which family each belongs to, and where every retired skill went_, so that _the upgrade can explain each removal instead of leaving me to guess_.

## Context

FR-20 puts ten seeded skills into three families. FR-29 requires Lore to report, for every skill it retires, the skill that replaced it. Tech Spec §7.1 makes both facts one shipped file: `src/lore/defaults/skills-catalogue.yaml`, a sibling of `agents.yaml` at the `defaults/` root and deliberately **not** inside `skills/`, so the skills tree stays exactly one directory per skill and the renderer never has to exclude a file.

`retired` rows are append-only: a user hopping several releases needs every intermediate rename explained, and `reason` is quoted verbatim in the removal report.

Tech Spec §5.3 and reconciliation item #10 of the §18 audit settle where the aggregate tokens resolve: `all` and `none` are accepted identically by `--skills` and by `plan_init(skill_families=[...])`, resolved by `skills.resolve_families()` in the business layer and never by `cli.py` (ADR-011). Only the expanded family list is ever persisted, which is why `init-skill-families` allows the three concrete families and never an aggregate.

---

## Acceptance Criteria

### E2E Scenarios

_This story has no CLI surface of its own: every scenario below calls a `lore.*` function directly, so all of them are written in `tests/unit/` (`technical-test-guidelines` §2, §8). See Test File Locations._

#### Scenario 1: The catalogue is reachable and complete

**Given** an installed Lore package
**When** a caller runs `from lore.skills import load_catalogue, family_ids, resolve_families, retirement_for` and calls `family_ids()`
**Then** the call returns `("machinery", "memory", "workflow")` in sorted order, and `load_catalogue()` returns a structure listing exactly ten skills whose ids match the directory names under `src/lore/defaults/skills/` in both directions

#### Scenario 2: Aggregate family tokens resolve identically on both surfaces

**Given** an installed Lore package
**When** a caller calls `resolve_families(["all"])`, then `resolve_families(["none"])`, then `resolve_families(["memory", "workflow"])`
**Then** the results are `("machinery", "memory", "workflow")`, `()` and `("memory", "workflow")` respectively — sorted, deduplicated tuples in every case

#### Scenario 3: A retired skill names its successor and its reason

**Given** an installed Lore package
**When** a caller calls `retirement_for("new-doctrine")` and `retirement_for("explore-codex")`
**Then** the first returns a record whose `into` is `"update-doctrine"` and whose `reason` is a non-empty string, the second returns `into == "retrieve-memory"`, and `retirement_for("start-quest")` returns `None`

#### Scenario 4: An unknown family token is rejected

**Given** an installed Lore package
**When** a caller calls `resolve_families(["memory", "typo"])`
**Then** `ValueError` is raised naming `typo` and listing the accepted tokens `machinery, memory, workflow, all, none`

### Unit Test Scenarios

- [ ] `lore.skills.load_catalogue`: returns the parsed catalogue; `lru_cache(maxsize=1)` asserted via `cache_info()`
- [ ] `lore.skills.family_ids`: sorted, cached, exactly the keys of the catalogue's `families` map
- [ ] `lore.skills.resolve_families`: `["all"]` expands to every family; `["none"]` yields the empty tuple; a concrete list is sorted and deduplicated; `["all", "memory"]` still yields every family exactly once
- [ ] `lore.skills.resolve_families`: an unknown token raises `ValueError` listing the five accepted tokens
- [ ] `lore.skills.skills_in_families`: given `("memory",)` returns exactly the catalogue's memory-family skill ids; given `()` returns an empty tuple
- [ ] `lore.skills.retirement_for`: a retired id returns `into` and `reason`; a current id returns `None`; an unknown id returns `None`
- [ ] `lore.skills`: a catalogue payload failing `lore://schemas/skill-catalogue` raises `RuntimeError` naming the packaged file, injected by monkeypatching the read step
- [ ] `src/lore/defaults/skills-catalogue.yaml`: parses; has `version`, `families`, `skills`, `retired`; every `skills[].family` is a key of `families`; every `retired[].into` is a current skill id; `store-memory`'s declared `references` all exist on disk (structural assertions only — ADR-006)
- [ ] `src/lore/schemas/skill-catalogue.yaml`: loads through `schemas.load_schema("skill-catalogue")` and carries `$id: lore://schemas/skill-catalogue`
- [ ] `lore.skills`: validates through `load_schema` and never `resolve_merged_schema`, asserted by AST inspection

---

## Out of Scope

- The `SKILL.md` bodies themselves — US-005 (memory family) and US-006 (machinery and workflow families).
- The access-mode block renderer that also lives in `lore.skills` — US-004.
- Which directory a resolved skill installs into — US-011.
- The `--skills` flag and its `click.Choice` set — US-016.
- Persisting the resolved families to `.lore/config.toml` — US-013.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-20, FR-29
- Tech Spec: `lore codex show interactive-init-tech-spec` §7.1, §5.3, §18 Reconciled #10
- `lore codex show tech-arch-skill-catalogue` — the doc that governs `src/lore/skills.py` and the catalogue file
- `lore codex show decisions-011-api-parity-with-cli`

---

## Tech Notes

### Implementation Approach

- **Files to create:**
  - `src/lore/skills.py` — catalogue half only in this story: `load_catalogue()`, `family_ids()`, `resolve_families(tokens)`, `skills_in_families(families)`, `retirement_for(skill_id)`. Same loading pattern as `src/lore/agents.py`: `importlib.resources`, `yaml.safe_load`, `functools.lru_cache(maxsize=1)`, schema-validated at load, `RuntimeError` on a build defect.
  - `src/lore/defaults/skills-catalogue.yaml` — Tech Spec §7.1 verbatim: `version: 2`, three families, ten skills, thirteen `retired` rows. No per-skill `description` — that is authored once in each `SKILL.md` frontmatter (`standards-dry`).
  - `src/lore/schemas/skill-catalogue.yaml` — `$id: lore://schemas/skill-catalogue`; requires `version`, `families`, `skills`; `retired` optional; each skill requires `id` and `family`, `references` optional array of strings; each `retired` value requires `into` and `reason`.
- **Files to modify:** none beyond a schema-kind registration in `src/lore/schemas/__init__.py` if that module carries an explicit kind list.
- **Schema changes:** one new packaged schema kind, not overlayable (ADR-018, Tech Spec §8.2).
- **Dependencies:** US-001 (the module will later construct `PlannedFile` values); the catalogue ids must match the directory names delivered by US-005 and US-006, so the two-way id/directory cross-check test lands green only once those ship — the implementer should write it in this story and expect it to drive US-005/US-006.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_skills.py` — NEW | **Every scenario above is a unit test.** All four call `lore.skills` directly and invoke no CLI (`technical-test-guidelines` §2, §8). The user-visible half — the prompt 3 checkbox and the `--skills` flag — is covered by US-016, US-018 and US-019 |
| Unit | `tests/unit/test_skills.py` — NEW | Catalogue loading, family resolution, retirement lookup, structural checks over the shipped file |
| Unit | `tests/unit/test_schemas.py` — extended | `lore://schemas/skill-catalogue` loads |

### Test Stubs

```python
# E2E — Scenario 1: The catalogue is reachable and complete
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_catalogue_ids_match_shipped_directories_both_ways():
    # Given: an installed package
    # When: compare catalogue skills[].id against the directory names under defaults/skills/
    # Then: the two sets are equal (structure only — no content assertions, ADR-006)
    pass


# E2E — Scenario 2: Aggregate family tokens resolve identically on both surfaces
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_all_and_none_resolve_in_the_business_layer():
    # resolve_families(["all"]) / (["none"]) / (["memory","workflow"])
    pass


# E2E — Scenario 3: A retired skill names its successor and its reason
# Exercises: lore codex show conceptual-workflows-init-reconcile — Removals (the ledger reason); ledger format in tech-arch-skill-catalogue — The Catalogue
def test_retirement_lookup_returns_into_and_reason():
    pass


# E2E — Scenario 4: An unknown family token is rejected
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_unknown_family_token_raises_valueerror():
    pass


# Unit — load_catalogue is cached
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_load_catalogue_is_lru_cached():
    pass


# Unit — family_ids sorted and cached
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_family_ids_sorted_and_cached():
    pass


# Unit — resolve_families aggregates, dedup and sort
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_resolve_families_handles_all_none_and_duplicates():
    pass


# Unit — resolve_families rejects an unknown token
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_resolve_families_rejects_unknown_token():
    pass


# Unit — skills_in_families
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_skills_in_families_selects_by_family_and_empty_for_no_families():
    pass


# Unit — retirement_for
# Exercises: lore codex show conceptual-workflows-init-reconcile — Removals (the ledger reason); ledger format in tech-arch-skill-catalogue — The Catalogue
def test_retirement_for_returns_none_for_current_and_unknown_ids():
    pass


# Unit — a schema-invalid catalogue is a build defect
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_invalid_catalogue_payload_raises_runtimeerror_naming_the_file(monkeypatch):
    pass


# Unit — the shipped catalogue is structurally complete (ADR-006: no value assertions)
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_shipped_catalogue_is_structurally_complete():
    # families keys cover every skills[].family; every retired[].into is a current id;
    # store-memory's declared references exist on disk
    pass
```

### Complexity Estimate

**M** — a second loader in the `agents.py` mould plus two data/schema files, with aggregate-token resolution and a two-way cross-check against the shipped skills tree.

### Standards References

- `lore codex show decisions-006-no-seed-content-tests`
- `lore codex show decisions-011-api-parity-with-cli` — aggregates resolve in the business layer, not in `cli.py`
- `lore codex show technical-test-guidelines`
