---
id: interactive-init-us-024
title: US-024 — The package ships questionary, a verified Click floor, and the new data files
summary: pyproject.toml declares questionary as a hard runtime dependency, raises the
  click floor to the verified >=8.3,<9.0, replaces a wheel artifacts entry naming a
  file that no longer exists with a glob over the whole defaults tree, and bumps the
  version to 0.10.0.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- ops-installation
- ops-publish-pypi
- tech-overview
- decisions-017-constrained-flags-use-click-choice
---

# US-024 — The package ships questionary, a verified Click floor, and the new data files

## Metadata

- **ID:** US-024
- **Status:** final
- **Epic:** _Release Obligations_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a developer installing Lore from PyPI_, I want _the wheel to carry the prompt library and every data file `lore init` reads_, so that _the interactive flow works on a fresh install rather than failing on a missing import or a missing registry_.

## Context

Tech Spec §11 collects four packaging facts this feature makes true.

`questionary>=2.0,<3.0` joins `dependencies`. It is a hard runtime dependency, not an extra — which also means `tech-overview`'s "No extras, no optional dependencies" line changes in the same pass (that doc edit is the codex-apply mission's).

**The `click` floor moves `>=8.0,<9.0` → `>=8.3,<9.0`.** `SpaceSeparatedChoice` overrides `Option.add_to_parser`, whose signature in the shipped Click is `(self, parser: _OptionParser, ctx: Context)` — a private type — and reaches `parser._long_opt`, `parsed.process`, `state.rargs` and `state.opts`, all private. The prototype was verified on 8.3.2 and on nothing else. ADR-017 makes the `BadParameter` wording and the exit-2 code a contract; a parser hook that silently stops consuming the greedy tail on an older in-range Click would break that contract **at runtime rather than at install time**, which is the worse failure. The spec gate upheld this and ruled that no implementation mission needs to verify the hook on 8.0–8.2.

`[tool.hatch.build.targets.wheel]`'s `artifacts` still names `src/lore/defaults/AGENTS.md`, a file that no longer exists. It becomes `src/lore/defaults/**/*` so `agents.yaml`, `skills-catalogue.yaml` and `legacy-hashes.json` are guaranteed into the wheel.

The version moves `0.9.0` → `0.10.0` — a minor bump, matching the additive public-API change US-023 records.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: The prompt library is a declared runtime dependency

**Given** `pyproject.toml`
**When** a test parses `[project].dependencies`
**Then** it contains a `questionary` requirement whose specifier is `>=2.0,<3.0`, and `[project.optional-dependencies]` is either absent or does not contain it

#### Scenario 2: The Click floor is not below the version the parser hook is exercised against

**Given** `pyproject.toml` and the installed `click` distribution
**When** a test parses the `click` requirement's lower bound and compares it against the installed version
**Then** the declared floor is at least `8.3`, and the installed version satisfies the declared specifier

#### Scenario 3: The wheel carries every packaged data file

**Given** a wheel built from the repository
**When** a test lists its contents
**Then** `lore/defaults/agents.yaml`, `lore/defaults/skills-catalogue.yaml`, `lore/defaults/legacy-hashes.json`, every `lore/defaults/skills/**/SKILL.md`, `lore/defaults/docs/LORE-AGENT.md`, `lore/defaults/gitignore` and every `lore/schemas/*.yaml` are present, and no entry names `defaults/AGENTS.md`

#### Scenario 4: The declared version matches the changelog

**Given** `pyproject.toml` and `CHANGELOG.md`
**When** a test reads `[project].version` and the top-most released changelog section
**Then** both are `0.10.0`

#### Scenario 5: A fresh install can reach the prompt layer

**Given** the package installed from the built wheel into a clean environment
**When** the caller runs `python -c "import lore.prompts; lore.prompts.ask_access_mode"`
**Then** the import succeeds and no `ModuleNotFoundError` is raised

### Unit Test Scenarios

- [ ] `pyproject.toml`: `[project].dependencies` names `click`, `pyyaml`, `jsonschema` and `questionary`, and nothing else
- [ ] `pyproject.toml`: the `click` specifier's lower bound is `>=8.3` and its upper bound is `<9.0`
- [ ] `pyproject.toml`: the declared `click` floor is not below `importlib.metadata.version("click")` — the assertion Tech Spec §11 requires, so a downgrade of the dev environment fails loudly rather than silently degrading the parser hook
- [ ] `pyproject.toml`: `[tool.hatch.build.targets.wheel].artifacts` names no path that does not exist on disk
- [ ] `pyproject.toml`: `[project].version` is `0.10.0` and `requires-python` is unchanged at `>=3.11`
- [ ] `pyproject.toml`: `[project].classifiers` still names Python 3.11 and 3.12

---

## Out of Scope

- The `CHANGELOG.md` entry itself — US-023.
- Updating `tech-overview`'s Python-floor line and dependency table, and `ops-installation` — owned by the phase-5 codex-apply mission (`lore show q-3c9c/m-d053`).
- Verifying `SpaceSeparatedChoice` against Click 8.0, 8.1 or 8.2 — the spec gate ruled it unnecessary.
- Publishing to PyPI.

---

## References

- PRD: `lore codex show interactive-init-prd`
- Tech Spec: `lore codex show interactive-init-tech-spec` §11, §12, §18 Reconciled #5, §19 Escalation 1
- `lore codex show ops-installation`
- `lore codex show ops-publish-pypi`
- `lore codex show decisions-017-constrained-flags-use-click-choice` — the contract the floor protects

---

## Tech Notes

### Implementation Approach

- **Files to modify:** `pyproject.toml`
  - `version = "0.9.0"` → `"0.10.0"` (line 3).
  - `dependencies` (lines 15–19): `"click>=8.0,<9.0"` → `"click>=8.3,<9.0"`; add `"questionary>=2.0,<3.0"`.
  - `[tool.hatch.build.targets.wheel].artifacts` (line 33): `["src/lore/defaults/AGENTS.md", "src/lore/schemas/*.yaml"]` → `["src/lore/defaults/**/*", "src/lore/schemas/*.yaml"]`.
  - `uv.lock` regenerates as a side effect; commit it.
- **Files to create:** none.
- **Schema changes:** none.
- **Dependencies:** none strictly, but US-018 cannot run until `questionary` resolves, so this story should be batched early despite being a release obligation.

`packages = ["src/lore"]` at line 32 is unchanged — it is `artifacts` that decides which non-Python files ride along.

The floor-versus-installed assertion in the last unit criterion is the one Tech Spec §11 asks for by name: "`test_package_distribution.py` gains an assertion that the declared floor is not below the version the parser hook is exercised against."

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_package_distribution.py` — extended | Every criterion above; the file already parses `pyproject.toml` through its `_read_pyproject` helper |

Scenario 3 needs a built wheel. If the suite has no build step today, the implementer asserts the `artifacts` globs would match the files on disk rather than shelling out to `hatch build` in a unit test — the goal is that a data file cannot be added without the packaging config covering it.

### Test Stubs

```python
# E2E/Unit — Scenario 1: The prompt library is a declared runtime dependency
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_questionary_is_a_hard_runtime_dependency():
    pass


# Unit — Scenario 2: The Click floor is not below the exercised version
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_click_floor_at_least_8_3_and_not_below_installed():
    pass


# Unit — Scenario 3: The wheel carries every packaged data file
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_wheel_artifacts_cover_every_defaults_data_file():
    pass


# Unit — Scenario 4: The declared version matches the changelog
# Exercises: lore codex show conceptual-workflows-python-api — release obligations
def test_pyproject_version_matches_changelog_top_entry():
    pass


# E2E — Scenario 5: A fresh install can reach the prompt layer
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_prompts_module_importable_from_the_installed_package():
    pass


# Unit — dependency list is exactly four
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_runtime_dependency_list_is_exactly_the_four_declared():
    pass


# Unit — no artifacts entry names a missing path
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_no_wheel_artifact_pattern_names_a_missing_file():
    pass


# Unit — version and python floor
# Exercises: lore codex show conceptual-workflows-python-api — release obligations
def test_version_is_0_10_0_and_requires_python_unchanged():
    pass
```

### Complexity Estimate

**S** — four edits to one file plus a lockfile regeneration; the only judgement is the artifacts glob, and every assertion is a parse-and-compare.

### Standards References

- `lore codex show decisions-017-constrained-flags-use-click-choice` — why the floor moves
- `lore codex show ops-publish-pypi`
- `lore codex show technical-test-guidelines`
