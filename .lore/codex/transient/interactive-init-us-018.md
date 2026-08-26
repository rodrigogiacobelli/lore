---
id: interactive-init-us-018
title: US-018 — A prompt layer that costs nothing when nobody prompts
summary: A new lore.prompts module holds one questionary function per question,
  importing questionary lazily inside each function so prompt_toolkit never loads for
  lore ready, and normalising every answer into the exact shape plan_init accepts.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- decisions-001-dumb-infrastructure
- decisions-011-api-parity-with-cli
- tech-arch-api-facade
- conceptual-workflows-init-interactive
---

# US-018 — A prompt layer that costs nothing when nobody prompts

## Metadata

- **ID:** US-018
- **Status:** final
- **Epic:** _CLI Surface_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _an agent running `lore ready` a hundred times a day_, I want _the prompt library never to load_, so that _adding an interactive command to Lore costs me nothing on every other command_.

## Context

`questionary` becomes a hard runtime dependency with this feature, and `api.py` aliases `_prompts` so `cli.py` can reach it — which means a module-level `import questionary` would pull `prompt_toolkit` into every single `lore` invocation. ADR-001 makes per-invocation cost a design constraint, so Tech Spec §5.4 and §16 require the import to happen lazily, inside each prompt function.

`prompts.py` is a CLI-layer module: it imports no `lore.*` module except `lore.initplan`, which gives it `AccessMode` and nothing else. That keeps it testable without a project and keeps `tests/unit/test_adr011_no_click_in_operational.py`'s rule extendable to it.

Each function's job is narrow: ask one question and return the answer in the exact shape `plan_init` accepts. The orchestration — when to ask, in what order, and what to do with the answers — is US-019.

The eight questions, in the mission's fixed order: agents (checkbox), access mode (select), skill families (checkbox), existing agent instruction file (select, conditional), root `.gitignore` (confirm), installed-skill tracking (select, conditional), edited-skill conflict (select, conditional), summary confirm.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Importing Lore does not import the prompt library

**Given** a fresh interpreter
**When** a caller runs `import lore.api` and inspects `sys.modules`
**Then** neither `questionary` nor `prompt_toolkit` is present

#### Scenario 2: Calling a prompt function imports it

**Given** a fresh interpreter with `questionary` monkeypatched to a recording stub
**When** a caller invokes `prompts.ask_agents(...)`
**Then** the stub's checkbox constructor is called exactly once and its return is normalised before being handed back

#### Scenario 3: Each answer arrives in the shape `plan_init` accepts

**Given** stubbed questionary returns for all eight questions
**When** each prompt function is called
**Then** `ask_agents` returns `list[str]` of registry ids; `ask_access_mode` returns `"cli"` or `"native"`; `ask_skill_families` returns `list[str]` of concrete family names with no aggregate token; `ask_existing_agent_file` returns `"append"` or `"skip"`; `ask_root_gitignore` returns `bool`; `ask_skills_gitignore` returns one of `"lore-only"`, `"none"`, `"all"`; `ask_on_conflict` returns `"skip"` or `"overwrite"`; `ask_confirm_plan` returns `bool`

#### Scenario 4: Ctrl-C at any prompt aborts without writing

**Given** a stubbed questionary whose `ask()` returns `None` — questionary's Ctrl-C signal
**When** any prompt function is called
**Then** it raises `click.Abort` at the CLI boundary rather than returning `None`, and the caller writes nothing

### Unit Test Scenarios

- [ ] `lore.prompts`: the module's AST contains no module-level `import questionary` — every occurrence sits inside a function body
- [ ] `lore.prompts`: the module's AST names no `lore.` module other than `lore.initplan`
- [ ] `lore.prompts.ask_agents`: the choices offered are one per registry row, each showing the row's `label` and its convention (`instruction_file` and `skills_dir`), with `claude` preselected
- [ ] `lore.prompts.ask_agents`: an already-recorded selection is preselected instead of the default — this is what makes FR-10's recorded answers visible at the prompt
- [ ] `lore.prompts.ask_access_mode`: offers exactly two choices with `native` preselected, and its prompt text states that the choice covers codex, rites and the glossary only
- [ ] `lore.prompts.ask_skill_families`: offers one choice per family with `memory` and `workflow` preselected and `machinery` unselected (Tech Spec §9.2's interactive default)
- [ ] `lore.prompts.ask_skill_families`: returns concrete family names only — never `all` or `none`
- [ ] `lore.prompts.ask_existing_agent_file`: offers exactly two options, `append` and `skip`; the collapsed `separate` option is absent
- [ ] `lore.prompts.ask_root_gitignore`: is a confirm defaulting to yes
- [ ] `lore.prompts.ask_skills_gitignore`: offers exactly three options with `lore-only` preselected
- [ ] `lore.prompts.ask_on_conflict`: offers exactly two options with `skip` preselected, and its prompt text carries the count of conflicted files
- [ ] `lore.prompts.ask_confirm_plan`: is a confirm defaulting to yes
- [ ] `lore.prompts`: every function returns `None` handling as an abort signal, uniformly

---

## Out of Scope

- Deciding when to call these functions — US-019.
- The `isatty` gate — US-019.
- Rendering the plan summary these functions confirm — US-019.
- Driving `prompt_toolkit` in a test: the prompt library is a dependency, not a subject (Tech Spec §14.3). Every test stubs the questionary functions.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-1 through FR-7
- Tech Spec: `lore codex show interactive-init-tech-spec` §4.3, §5.4, §7.4, §9.2, §12, §14.2, §16
- `lore codex show decisions-001-dumb-infrastructure` — per-invocation cost is a design constraint
- `lore codex show tech-arch-api-facade` — the `_prompts` underscore alias

---

## Tech Notes

### Implementation Approach

- **Files to create:** `src/lore/prompts.py` — eight functions, one per question. Every one imports `questionary` **inside its body**. Imports `lore.initplan` for `AccessMode` and nothing else from `lore.*`.
- **Files to modify:** `src/lore/api.py` — add `from lore import prompts as _prompts  # noqa: F401` to the underscore-alias block at `src/lore/api.py:163-175`. Because `prompts.py` imports `questionary` lazily, this alias stays cheap.
- **Schema changes:** none.
- **Dependencies:** US-001 (`AccessMode`), US-002 (registry rows for the prompt 1 choice labels), US-003 (families for the prompt 3 choices), US-024 (the `questionary>=2.0,<3.0` dependency must be declared before the import can resolve).

Prompt copy comes from Tech Spec §4.3's worked example. The access-mode question in particular must state its scope inline, because the answer's blast radius is not obvious:

```
? How should agents read and write Lore's local files?
  (codex, rites and the glossary only — quests, missions, artifacts, knights,
   doctrines and watchers always go through the CLI)
```

`questionary` returns `None` when the user presses Ctrl-C. Tech Spec §4.2 fixes the behaviour: `click.Abort()` → Click prints `Aborted!` to stderr → exit 1, nothing written. `prompts.py` itself must stay `click`-free if the ADR-011 import test is extended to it — the cleanest split is for each function to return `None` and for the `cli.py` caller to raise `click.Abort`. The implementer picks one and the test asserts it; the acceptance criterion above assumes the abort surfaces at the CLI boundary.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_init_interactive.py` — extended | Anchor `conceptual-workflows-init-interactive`; the lazy-import and shape scenarios |
| Unit | `tests/unit/test_prompts.py` — NEW | AST inspection, per-function choice sets and normalisation |
| Unit | `tests/unit/test_adr011_no_click_in_operational.py` — extended | `prompts.py` imports no `lore.*` beyond `lore.initplan` |

### Test Stubs

```python
# E2E — Scenario 1: Importing Lore does not import the prompt library
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_importing_lore_api_does_not_load_prompt_toolkit():
    pass


# E2E — Scenario 2: Calling a prompt function imports it
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_calling_a_prompt_imports_questionary_once(monkeypatch):
    pass


# E2E — Scenario 3: Each answer arrives in the shape plan_init accepts
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_every_prompt_returns_the_plan_init_parameter_shape(monkeypatch):
    pass


# E2E — Scenario 4: Ctrl-C at any prompt aborts without writing
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_ctrl_c_aborts_and_writes_nothing(tmp_path, runner, monkeypatch):
    pass


# Unit — no module-level questionary import
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_questionary_imported_only_inside_functions():
    pass


# Unit — no lore.* import beyond initplan
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_prompts_module_imports_only_initplan_from_lore():
    pass


# Unit — prompt 1 choices and preselection
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
def test_ask_agents_offers_one_choice_per_registry_row_with_claude_preselected(monkeypatch):
    pass


# Unit — prompt 1 preselects a recorded selection
# Exercises: lore codex show conceptual-workflows-init-interactive — Answers Are Recorded
def test_ask_agents_preselects_recorded_answers(monkeypatch):
    pass


# Unit — prompt 2 choices, default and scope text
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_ask_access_mode_offers_two_choices_with_native_preselected(monkeypatch):
    pass


# Unit — prompt 3 choices and interactive default
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_ask_skill_families_preselects_memory_and_workflow(monkeypatch):
    pass


# Unit — prompt 3 never returns an aggregate token
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 3 (skill families)
def test_ask_skill_families_returns_concrete_families_only(monkeypatch):
    pass


# Unit — prompt 4 has two options, not three
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 4 (existing instruction file)
def test_ask_existing_agent_file_offers_append_and_skip_only(monkeypatch):
    pass


# Unit — prompt 5a confirm default
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 5a (root .gitignore)
def test_ask_root_gitignore_defaults_to_yes(monkeypatch):
    pass


# Unit — prompt 5b three options
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 5b (installed-skill tracking)
def test_ask_skills_gitignore_offers_three_options(monkeypatch):
    pass


# Unit — prompt 6 two options and the conflict count
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 6 (edited-skill conflict)
def test_ask_on_conflict_offers_two_options_and_names_the_count(monkeypatch):
    pass


# Unit — prompt 7 confirm default
# Exercises: lore codex show conceptual-workflows-init-interactive — The Summary, prompt 7 (apply this plan?)
def test_ask_confirm_plan_defaults_to_yes(monkeypatch):
    pass


# Unit — uniform None handling
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_every_prompt_treats_none_as_an_abort_signal(monkeypatch):
    pass
```

### Complexity Estimate

**M** — eight small functions with no logic beyond normalisation, but the lazy-import constraint, the preselection rules and the abort path each need their own proof.

### Standards References

- `lore codex show decisions-001-dumb-infrastructure` — per-invocation cost
- `lore codex show decisions-011-api-parity-with-cli` — prompts fill parameters, they do not decide anything
- `lore codex show tech-arch-api-facade`
- `lore codex show technical-test-guidelines`
