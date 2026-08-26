---
id: interactive-init-us-002
title: US-002 — The agent registry ships as data, not as code
summary: lore init reads its list of coding-agent targets from a packaged
  src/lore/defaults/agents.yaml validated against a new lore://schemas/agents, loaded
  through importlib.resources at import time, so adding an agent is a one-block data
  edit with no change to init.py or cli.py.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-agents-md
- tech-arch-project-root-detection
- decisions-006-no-seed-content-tests
- decisions-018-overlays-are-path-discovered-config
- conceptual-workflows-init-interactive
---

# US-002 — The agent registry ships as data, not as code

## Metadata

- **ID:** US-002
- **Status:** final
- **Epic:** _Type and Data Foundations_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a Lore maintainer_, I want _the set of coding agents `lore init` can target to live in a shipped YAML file_, so that _adding a newly verified agent convention is one data edit and never a change to initialisation logic_.

## Context

FR-11 requires the human to select agents "from a registry seeded with the release, not from a list compiled into the initialisation logic". FR-12 makes adding an agent a data edit. FR-13 requires every shipped row to have a verified convention — which is why Tech Spec §8.1 ships six rows and no `verified` field: presence in the file *is* the verification, and a field with one legal value on every row is the stored constant `standards-dry` rejects.

The registry is **package** data, not project data. `lore init` runs where no `.lore/` exists — `tech-arch-project-root-detection` documents init as the exception to `find_project_root()` — so a project-local registry could never have worked. It also has to be readable at *import* time, because `click.Choice` evaluates its set when the decorator runs (Tech Spec §8.2).

---

## Acceptance Criteria

### E2E Scenarios

_This story has no CLI surface of its own: every scenario below calls a `lore.*` function directly, so all of them are written in `tests/unit/` (`technical-test-guidelines` §2, §8). See Test File Locations._

#### Scenario 1: The registry is reachable from an installed package

**Given** an installed Lore package and any working directory, initialised or not
**When** a caller runs `from lore.agents import load_registry, agent_ids, get_agent` and calls `agent_ids()`
**Then** the call returns a sorted tuple of exactly six ids — `("agents-md", "claude", "cursor", "gemini", "none", "qwen")` — with no `.lore/` directory required or created

#### Scenario 2: A known agent resolves to its convention

**Given** an installed Lore package
**When** a caller calls `get_agent("claude")`
**Then** the returned `AgentTarget` has `id == "claude"`, a non-empty `label`, `instruction_file == "CLAUDE.md"` and `skills_dir == ".claude/skills"`

#### Scenario 3: An unknown agent id is rejected with the known set named

**Given** an installed Lore package
**When** a caller calls `get_agent("cline")`
**Then** `ValueError` is raised with the message `Unknown agent: 'cline'. Known agents: agents-md, claude, cursor, gemini, none, qwen.`

#### Scenario 4: `none` is a registry row, not a sentinel

**Given** an installed Lore package
**When** a caller calls `get_agent("none")`
**Then** an `AgentTarget` is returned whose `instruction_file` and `skills_dir` are both `None`, and `"none"` is present in `agent_ids()`

### Unit Test Scenarios

- [ ] `lore.agents.load_registry`: returns a tuple of `lore.initplan.AgentTarget`; every entry has a non-empty `id` and `label`
- [ ] `lore.agents.load_registry`: decorated with `functools.lru_cache(maxsize=1)`, asserted via `load_registry.cache_info()` showing one miss then hits on repeat calls
- [ ] `lore.agents.agent_ids`: returns the ids in sorted order and is `lru_cache`d
- [ ] `lore.agents.get_agent`: known id returns the matching row; unknown id raises `ValueError` naming the known ids in sorted order
- [ ] `lore.agents`: the module's AST contains no `import`/`from` naming a `lore.` module other than `lore.initplan`
- [ ] `lore.agents`: a registry payload that fails `lore://schemas/agents` raises `RuntimeError` naming the packaged file path — injected by monkeypatching the loader's read step, never by editing the shipped file
- [ ] `src/lore/defaults/agents.yaml`: exists, parses as YAML, has a top-level `version` integer and an `agents` list; every entry has the keys `id`, `label`, `instruction_file`, `skills_dir`; ids are unique (structural assertions only — ADR-006 forbids asserting values from `src/lore/defaults/`)
- [ ] `src/lore/schemas/agents.yaml`: loads through `lore.schemas.load_schema("agents")` and carries `$id: lore://schemas/agents`
- [ ] `lore.agents`: validation goes through `schemas.load_schema("agents")` and never through `schemas.resolve_merged_schema` — asserted by AST inspection of the module

---

## Out of Scope

- The `--agent` CLI flag and its `click.Choice` set — US-016.
- The `none`-cannot-be-combined rule — US-017 (it is a business rule in `lore.validators`, not a registry property).
- The seven unverified conventions (Cline, Roo Code, Windsurf, Crush, Aider, Goose, Grok) — PRD Post-MVP.
- A `verified` field on registry rows — Tech Spec §16, rejected.
- Where skills land for a given target — US-011.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-11, FR-12, FR-13
- Tech Spec: `lore codex show interactive-init-tech-spec` §8.1, §8.2
- `lore codex show tech-arch-agents-md` — the rewritten home of the registry's documentation
- `lore codex show decisions-006-no-seed-content-tests`
- `lore codex show decisions-018-overlays-are-path-discovered-config` — why `agents` is not an overlayable kind

---

## Tech Notes

### Implementation Approach

- **Files to create:**
  - `src/lore/agents.py` — `load_registry() -> tuple[AgentTarget, ...]`, `agent_ids() -> tuple[str, ...]`, `get_agent(agent_id: str) -> AgentTarget`. Imports `dataclasses`, `functools`, `importlib.resources`, `yaml` and `lore.initplan` only. Both cached functions carry `functools.lru_cache(maxsize=1)`.
  - `src/lore/defaults/agents.yaml` — the six rows in Tech Spec §8.1 verbatim.
  - `src/lore/schemas/agents.yaml` — `$id: lore://schemas/agents`; requires `version` (integer) and `agents` (array); each item requires `id`, `label`, `instruction_file`, `skills_dir`, with the last two `["string", "null"]`; `additionalProperties: false`, matching the style of `src/lore/schemas/knight-frontmatter.yaml`.
- **Files to modify:** none. `src/lore/schemas/__init__.py` already discovers `*.yaml` siblings — the implementer must confirm `load_schema("agents")` resolves without a registry edit and, if `schemas.py` carries an explicit kind list, add `agents` to it.
- **Schema changes:** one new packaged schema kind. It is deliberately **not** overlayable: validation calls `schemas.load_schema(kind)` directly, never `schemas.resolve_merged_schema(kind, project_root)` (Tech Spec §8.2, ADR-018).
- **Dependencies:** US-001 (`AgentTarget` lives in `lore.initplan`).

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_agents.py` — NEW | **Every scenario above is a unit test.** All four call `lore.agents` directly and invoke no CLI, so `technical-test-guidelines` §2 and §8 put them in `tests/unit/`; no E2E file and no codex anchor is involved. The user-visible half of the registry — the prompt 1 checkbox — is covered by US-018 and US-019 |
| Unit | `tests/unit/test_agents.py` — NEW | Loader behaviour, caching, import purity, structural shape of the shipped file |
| Unit | `tests/unit/test_schemas.py` — extended | `lore://schemas/agents` loads |
| Unit | `tests/unit/test_package_distribution.py` — extended | `src/lore/defaults/agents.yaml` is present in the built wheel (see US-024 for the packaging change that makes it so) |

### Test Stubs

```python
# E2E — Scenario 1: The registry is reachable from an installed package
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_agent_ids_available_without_a_project(tmp_path, monkeypatch):
    # Given: cwd is an empty directory with no .lore/
    # When: call lore.agents.agent_ids()
    # Then: six sorted ids returned; no .lore/ created
    pass


# E2E — Scenario 2: A known agent resolves to its convention
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_claude_row_carries_instruction_file_and_skills_dir():
    # get_agent("claude") -> CLAUDE.md + .claude/skills
    pass


# E2E — Scenario 3: An unknown agent id is rejected with the known set named
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_unknown_agent_id_raises_valueerror_naming_known_ids():
    # get_agent("cline") -> ValueError with the exact §4.2 wording
    pass


# E2E — Scenario 4: `none` is a registry row, not a sentinel
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_none_row_has_null_instruction_file_and_skills_dir():
    # get_agent("none") -> both fields None; "none" in agent_ids()
    pass


# Unit — load_registry returns AgentTarget rows
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_load_registry_returns_agent_targets():
    pass


# Unit — load_registry and agent_ids are cached
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_registry_loaders_are_lru_cached():
    # cache_info() shows misses=1 after repeated calls
    pass


# Unit — agent_ids is sorted
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_agent_ids_sorted():
    pass


# Unit — module import purity
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_agents_module_imports_only_initplan_from_lore():
    # AST walk over src/lore/agents.py
    pass


# Unit — a schema-invalid registry is a build defect
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_invalid_registry_payload_raises_runtimeerror_naming_the_file(monkeypatch):
    # Monkeypatch the read step to return a payload missing `agents`; expect RuntimeError
    pass


# Unit — the shipped file is structurally complete (ADR-006: no value assertions)
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_shipped_agents_yaml_is_structurally_complete():
    # parses; has version + agents; every row has the four keys; ids unique
    pass


# Unit — the schema kind is registered and not overlayable
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_agents_schema_loads_and_is_not_overlay_resolved():
    # load_schema("agents") returns a dict with $id lore://schemas/agents
    # AST of agents.py contains no reference to resolve_merged_schema
    pass
```

### Complexity Estimate

**M** — one small loader module plus two new data/schema files, with caching, import-purity and structural-only test constraints; no interaction with the plan/apply core.

### Standards References

- `lore codex show decisions-006-no-seed-content-tests` — the shipped YAML may only be asserted structurally
- `lore codex show decisions-018-overlays-are-path-discovered-config` — packaged schema kinds are not overlayable
- `lore codex show tech-arch-project-root-detection` — why the registry cannot be project data
- `lore codex show technical-test-guidelines`
