---
id: interactive-init-us-013
title: US-013 — The answers are recorded in config.toml and reused
summary: Four init- prefixed root keys join .lore/config.toml, config.py gains support
  for list-typed keys with per-item token sets, and an invalid value drops its key to
  the default with one warning — the same fail-soft parity the scalar keys already have.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- decisions-013-toml-for-config-yaml-for-glossary
- decisions-021-health-reports-are-ephemeral-by-default
- decisions-010-public-api-stability
- conceptual-workflows-lore-init
---

# US-013 — The answers are recorded in config.toml and reused

## Metadata

- **ID:** US-013
- **Status:** final
- **Epic:** _Configuration_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a developer who has already told Lore which agent I use_, I want _that answer stored in my project's config_, so that _a second `lore init` does not ask me again_.

## Context

FR-10 requires a re-run not to ask for answers already recorded. Tech Spec §9.1 names the four keys, all `init-` prefixed to match the command-scoped naming `health-report-retention` established:

| Key | Type | Default |
|---|---|---|
| `init-agents` | array of strings | `[]` |
| `init-access-mode` | `"cli"` \| `"native"` | `"native"` |
| `init-skill-families` | array of strings | `["memory", "machinery", "workflow"]` |
| `init-skills-gitignore` | `"lore-only"` \| `"none"` \| `"all"` | `"lore-only"` |

`config.py` handles `bool` and `str` today. Two of the four keys are lists, which is new: `_EXPECTED_TYPE` gains `list` entries and a new `_ALLOWED_ITEM_VALUES` table carries the per-item token sets. Fail-soft parity with the scalar path is the rule — a list containing an unknown token drops the **whole key** to its default with one stderr warning, under the existing one-warning-per-process latch.

§9.2 settles a place where the PRD says two different things, and both are right for their context: the **non-interactive** default is all three families (so a Realm deployment depending on `update-doctrine` keeps it across the upgrade), while the **interactive** checkbox preselects memory and workflow. Whichever the human confirms is written to `init-skill-families` and reused thereafter.

`init-skill-families` allows only the three concrete families and never `all` or `none`: aggregates resolve in `skills.resolve_families()` before anything is persisted (§5.3).

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: A config carrying the four keys loads them

**Given** a `.lore/config.toml` containing `init-agents = ["claude"]`, `init-access-mode = "cli"`, `init-skill-families = ["memory", "workflow"]` and `init-skills-gitignore = "all"`
**When** a caller runs `load_config(project_root)`
**Then** the returned `Config` carries `init_agents == ["claude"]`, `init_access_mode == "cli"`, `init_skill_families == ["memory", "workflow"]` and `init_skills_gitignore == "all"`, and no warning is emitted

#### Scenario 2: An absent key takes its documented default

**Given** a `.lore/config.toml` naming none of the four keys
**When** a caller runs `load_config(project_root)`
**Then** `init_agents == []`, `init_access_mode == "native"`, `init_skill_families == ["memory", "machinery", "workflow"]`, `init_skills_gitignore == "lore-only"`, and no warning is emitted

#### Scenario 3: An out-of-set item drops the whole key with one warning

**Given** a `.lore/config.toml` containing `init-skill-families = ["memory", "typo"]`
**When** a caller runs `load_config(project_root)`
**Then** `init_skill_families` is the default three-family list, and stderr carries exactly one line `lore: invalid value for init-skill-families at <path> (expected items from: machinery, memory, workflow); using default`

#### Scenario 4: The answers a run confirms are written back

**Given** an empty project
**When** the caller runs `lore init --agent claude --access cli --skills memory workflow --skills-gitignore none --yes`
**Then** `.lore/config.toml` afterwards carries `init-agents = ["claude"]`, `init-access-mode = "cli"`, `init-skill-families = ["memory", "workflow"]` and `init-skills-gitignore = "none"`, and a second `lore init --yes` produces no change to any of the four values

#### Scenario 5: An aggregate token is never persisted

**Given** an empty project
**When** the caller runs `lore init --skills all --yes`
**Then** `.lore/config.toml` carries `init-skill-families = ["machinery", "memory", "workflow"]` — the expanded list — and never the token `all`

### Unit Test Scenarios

- [ ] `lore.config._FROM_TOML`: carries the four new key-to-attribute mappings; every key in `_FROM_TOML` has an entry in `_EXPECTED_TYPE`
- [ ] `lore.config.Config`: gains `init_agents`, `init_access_mode`, `init_skill_families`, `init_skills_gitignore` as frozen fields with the §9.1 defaults
- [ ] `lore.config.load_config`: a list-typed key with the wrong outer type (a string where a list is expected) drops to the default with one `invalid type` warning
- [ ] `lore.config.load_config`: a list containing a non-string element drops the key with one warning
- [ ] `lore.config.load_config`: a list containing an out-of-set token drops the **whole** key rather than only the offending item
- [ ] `lore.config.load_config`: `init-agents` accepts only ids present in `agents.agent_ids()`; an unknown id drops the key with one warning
- [ ] `lore.config.load_config`: an empty list is a valid value for `init-agents` and is not treated as absent
- [ ] `lore.config.load_config`: the one-warning-per-process latch still holds across a scalar failure followed by a list failure — only the first warning is emitted
- [ ] `lore.config.load_config`: unknown root keys still land in `Config.extras` unchanged
- [ ] `lore.config._ALLOWED_ITEM_VALUES`: covers every list-typed key in `_EXPECTED_TYPE` and no other

---

## Out of Scope

- Regenerating the known-key comment header — US-020.
- Reading the keys during planning — US-014; `plan_init` is their **only** reader (Tech Spec §3.3, ADR-021 constraint 2), and `cli.py` never reads a config key.
- Writing the values at the end of an apply — US-015.
- Exporting the four new `Config` fields' effect on `lore.api.__all__` — `Config` is already exported; US-023 carries the changelog obligation.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-3, FR-6, FR-10, FR-16, FR-17
- Tech Spec: `lore codex show interactive-init-tech-spec` §9.1, §9.2, §5.3, §3.3
- `lore codex show decisions-013-toml-for-config-yaml-for-glossary` — flat root keys, forward-compatible
- `lore codex show decisions-021-health-reports-are-ephemeral-by-default` — the worked precedent for a command-scoped key and its single reader

---

## Tech Notes

### Implementation Approach

- **Files to modify:** `src/lore/config.py`
  - `_FROM_TOML` at `src/lore/config.py:45` — four new entries.
  - `_EXPECTED_TYPE` at `src/lore/config.py:53` — `list` for `init-agents` and `init-skill-families`, `str` for the other two.
  - `_ALLOWED_VALUES` at `src/lore/config.py:60` — token sets for `init-access-mode` and `init-skills-gitignore`.
  - New `_ALLOWED_ITEM_VALUES: dict[str, tuple[str, ...]]` — per-item token sets for the two list keys.
  - `Config` at `src/lore/config.py:71` — four new frozen fields with the §9.1 defaults, plus docstring entries matching the existing style.
  - `load_config` at `src/lore/config.py:125` — a list branch beside the scalar branch, warning through the existing `_warn_once` at `src/lore/config.py:107`.
- **Files to create:** none.
- **Schema changes:** none — `.lore/config.toml` is TOML with no JSON Schema.
- **Dependencies:** US-002 (`agents.agent_ids()` supplies `init-agents`'s item set). Importing `lore.agents` from `lore.config` is acceptable: `agents.py` imports only `lore.initplan`, so no cycle forms.

Default fields on a frozen dataclass cannot be mutable, so the two list defaults use `dataclasses.field(default_factory=...)` — matching how `extras` is already declared at `src/lore/config.py:90`.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_lore_init.py` — extended | Anchor `conceptual-workflows-lore-init`. **Not** `tests/e2e/test_config.py`: that file is anchored to `conceptual-workflows-glossary`, and `technical-test-guidelines` §3 allows one anchor per E2E file. The observable behaviour of the four `init-*` keys is `lore init` behaviour, so it belongs under the init anchor |
| Unit | `tests/unit/test_config.py` — extended | The type tables, the list branch, the warning latch |

### Test Stubs

```python
# E2E — Scenario 1: A config carrying the four keys loads them
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_four_init_keys_load_from_config(project_dir):
    pass


# E2E — Scenario 2: An absent key takes its documented default
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_absent_init_keys_take_documented_defaults(project_dir):
    pass


# E2E — Scenario 3: An out-of-set item drops the whole key with one warning
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_out_of_set_family_token_drops_key_with_one_warning(project_dir, capsys):
    pass


# E2E — Scenario 4: The answers a run confirms are written back
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_flags_are_persisted_and_reused_on_a_second_run(project_dir, runner):
    pass


# E2E — Scenario 5: An aggregate token is never persisted
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_skills_all_persists_the_expanded_family_list(project_dir, runner):
    pass


# Unit — the registry tables agree with each other
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_every_from_toml_key_has_an_expected_type():
    pass


# Unit — Config gains four frozen fields with the documented defaults
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_config_defaults_for_the_four_init_keys():
    pass


# Unit — wrong outer type drops the key
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_string_where_a_list_is_expected_drops_the_key(tmp_path, capsys):
    pass


# Unit — non-string element drops the key
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_non_string_list_element_drops_the_key(tmp_path, capsys):
    pass


# Unit — one bad item drops the whole key
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_one_out_of_set_item_drops_the_whole_key(tmp_path, capsys):
    pass


# Unit — init-agents is checked against the registry
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_unknown_agent_id_in_config_drops_the_key(tmp_path, capsys):
    pass


# Unit — an empty list is a real value
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_empty_init_agents_list_is_valid(tmp_path):
    pass


# Unit — the warning latch spans scalar and list failures
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_one_warning_per_process_across_scalar_and_list_failures(tmp_path, capsys):
    pass


# Unit — extras still preserved
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_unknown_root_keys_still_preserved_in_extras(tmp_path):
    pass


# Unit — _ALLOWED_ITEM_VALUES covers exactly the list keys
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_allowed_item_values_covers_every_list_key():
    pass
```

### Complexity Estimate

**M** — four keys across four registry tables plus a new list branch in a loader whose fail-soft semantics and warning latch are already pinned by existing tests that must keep passing.

### Standards References

- `lore codex show decisions-013-toml-for-config-yaml-for-glossary`
- `lore codex show decisions-021-health-reports-are-ephemeral-by-default` — constraint 2: one reader per command-scoped key
- `lore codex show decisions-011-api-parity-with-cli`
- `lore codex show technical-test-guidelines`
