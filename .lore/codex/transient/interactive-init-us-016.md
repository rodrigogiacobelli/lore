---
id: interactive-init-us-016
title: US-016 — Every prompt has a flag, and multi-value flags are space-separated
summary: lore init gains ten flags covering every prompt, with two multi-value flags
  parsed space-separated through a SpaceSeparatedChoice option subclass that leaves
  click.Choice as the validator, and a --help that names every flag and states that
  JSON output is unsupported.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- decisions-008-help-as-teaching-interface
- decisions-012-multi-value-cli-param-convention
- decisions-017-constrained-flags-use-click-choice
- conceptual-workflows-help
- conceptual-workflows-error-handling
- conceptual-workflows-init-interactive
- conceptual-workflows-json-output
---

# US-016 — Every prompt has a flag, and multi-value flags are space-separated

## Metadata

- **ID:** US-016
- **Status:** final
- **Epic:** _CLI Surface_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a CI pipeline with no terminal_, I want _a command-line flag for every question `lore init` would ask a human_, so that _I can reach the whole flow without interaction and without guessing at defaults_.

## Context

FR-8 requires every prompt to have a flag equivalent and all prompting to be suppressible. Tech Spec §3.3 is the flag table:

| Flag | Type | Click default | Prompt it replaces |
|---|---|---|---|
| `--agent ID [ID ...]` | `SpaceSeparatedChoice` over registry ids | `None` | agents |
| `--access {cli,native}` | `click.Choice` | `None` | access mode |
| `--skills FAMILY [FAMILY ...]` | `SpaceSeparatedChoice` over `memory` `machinery` `workflow` `all` `none` | `None` | skill families |
| `--on-existing-agent-file {append,skip}` | `click.Choice` | `"append"` | existing instruction file |
| `--gitignore / --no-gitignore` | flag pair | `None` | root `.gitignore` |
| `--skills-gitignore {lore-only,none,all}` | `click.Choice` | `None` | installed-skill tracking |
| `--on-conflict {skip,overwrite}` | `click.Choice` | `"skip"` | edited-file conflict |
| `-y, --yes` | flag | off | the summary confirm, and every other prompt |
| `--reconfigure` | flag | off | forces re-prompting despite recorded answers |
| `--dry-run` | flag | off | — |

**No flag carries a config-derived Click default, and `cli.py` never reads a config key.** A Click default is evaluated at decorator time, where no project root exists, and ADR-021 constraint 2 already settled that the business function is a command-scoped key's only reader. A flag left unset arrives as `None`, and `plan_init` resolves it (US-014).

ADR-012 requires `--agent claude codex`, not `--agent claude --agent codex`. Neither existing mechanism works here: `nargs=-1` on an option raises `TypeError: nargs=-1 is not supported for options` on Click 8.3.2, and `lore health --scope`'s trailing-variadic-positional trick cannot serve two multi-value flags on one command. Tech Spec §3.4 adds one `click.Option` subclass, ~25 lines, that greedily consumes following non-flag tokens — **argv parsing, not business logic**, so it belongs in `cli.py` under `standards-separation-of-concerns`. `type=click.Choice(...)` still owns the closed set, so ADR-017's three constraints hold untouched: the mechanism is `click.Choice`, an out-of-set token is a `BadParameter`/`UsageError` on stderr, and the exit code is 2.

§3.1 rules that `lore init` gains no JSON envelope and `lore --json init` keeps its current behaviour — accepted, no effect, text output, exit 0. ADR-008 makes help the teaching surface, so `--help` states the fact rather than leaving a silently-ignored flag to be discovered.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Space-separated multi-value parses both flags

**Given** an empty project directory
**When** the caller runs `lore init --agent claude agents-md --skills memory workflow --yes`
**Then** exit is 0, both selections are applied — skills land under `.claude/skills/` and `.lore/skills/`, only the memory and workflow families are installed — and `.lore/config.toml` records `init-agents = ["agents-md", "claude"]`

#### Scenario 2: A following flag stops greedy consumption

**Given** an empty project directory
**When** the caller runs `lore init --agent claude --skills memory --yes`
**Then** `--agent` receives `["claude"]` only, `--skills` receives `["memory"]`, and neither flag swallows the other's token

#### Scenario 3: A bare `-` is consumed as a value, not read as a flag

**Given** an empty project directory
**When** the caller runs `lore init --agent claude - --yes`
**Then** `-` is consumed as an `--agent` value and rejected by `click.Choice` with exit 2 and the message `Error: Invalid value for '--agent': '-' is not one of 'agents-md', 'claude', 'cursor', 'gemini', 'none', 'qwen'.`

#### Scenario 4: An out-of-set token in the greedy tail still exits 2

**Given** an empty project directory
**When** the caller runs `lore init --agent claude bogus`
**Then** exit is 2 and stderr carries `Error: Invalid value for '--agent': 'bogus' is not one of 'agents-md', 'claude', 'cursor', 'gemini', 'none', 'qwen'.` — Click's standard wording, unchanged (ADR-017)

#### Scenario 5: A repeated flag accumulates rather than raising

**Given** an empty project directory
**When** the caller runs `lore init --agent claude agents-md --agent gemini --yes`
**Then** exit is 0 and all three agents are selected — the form is undocumented but does not crash

#### Scenario 6: Every constrained flag exits 2 on a bad value

**Given** an empty project directory
**When** the caller runs `lore init --access agentic`, then `lore init --skills memory typo`, then `lore init --on-existing-agent-file merge`, then `lore init --skills-gitignore some`, then `lore init --on-conflict keep-new`
**Then** each exits 2 with Click's `Invalid value for '<flag>'` wording on stderr and writes nothing — no `.lore/` is created

#### Scenario 7: `lore init --help` teaches the flag surface and the JSON exception

**Given** any working directory
**When** the caller runs `lore init --help`
**Then** exit is 0, the output names every one of the ten flags, shows `--agent` and `--skills` in their space-separated form only, and contains the sentence `JSON output is not supported for this command. Use the Python API — lore.api.plan_init() returns a typed InitPlan describing every create, overwrite, removal and conflict without performing any of them.`

#### Scenario 8: `lore --json init` is accepted, ignored and exits 0

**Given** an empty project directory
**When** the caller runs `lore --json init --yes`
**Then** exit is 0, stdout is the same text output the flagless run produces, and no JSON object is emitted — the permanent exception recorded in `ref-lore_cli-commands`, pinned

### Unit Test Scenarios

- [ ] `lore.cli`: `init` carries all ten options with the types and Click defaults in the §3.3 table, asserted through `main.commands["init"].params`
- [ ] `lore.cli`: no `init` option has a default sourced from `lore.config` — asserted by AST inspection showing no `load_config` reference in the `init` handler or its decorators
- [ ] `lore.cli.SpaceSeparatedChoice`: subclasses `click.Option` and overrides only `add_to_parser`
- [ ] `lore.cli`: `--agent`'s `click.Choice` set equals `agents.agent_ids()`, evaluated at import time
- [ ] `lore.cli`: `--skills`'s `click.Choice` set equals `skills.family_ids()` plus `all` and `none`
- [ ] `tests/unit/test_cli_imports_only_api.py`: still passes — `cli.py` reaches `prompts`, `agents` and `skills` through the `lore.api` underscore aliases, never by direct import

Note: the five `SpaceSeparatedChoice` parser cases are E2E, not unit. `technical-test-guidelines` §2 forbids a unit test importing `lore.cli`, §6 lists `from lore.cli import main` as a prohibited unit pattern, and §8 says a test that needs to invoke the CLI belongs in `tests/e2e/`. The unit assertions above inspect the command object's declared parameters, which does require the import — so they live in `tests/e2e/test_init_interactive.py` alongside the parser scenarios rather than in a unit file.

---

## Out of Scope

- The `--agent none` exclusivity rule — US-017, which owns it on both surfaces.
- Prompting when a flag is absent — US-018 and US-019.
- What `plan_init` does with the resolved values — US-014.
- Adding a `--force` flag — Tech Spec §3.3 rejects it: `--yes --on-conflict overwrite` says the same thing explicitly and composes.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-8, FR-9
- Tech Spec: `lore codex show interactive-init-tech-spec` §3.1, §3.3, §3.4, §4.2, §4.3, §14.1
- `lore codex show decisions-012-multi-value-cli-param-convention` — amended in place by the phase-5 codex-apply mission to name `SpaceSeparatedChoice` as the mechanism
- `lore codex show decisions-017-constrained-flags-use-click-choice`
- `lore codex show decisions-008-help-as-teaching-interface`
- `lore codex show conceptual-workflows-json-output` — the `lore init` sentence, restated as unchanged

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/cli.py` — add the `SpaceSeparatedChoice(click.Option)` class exactly as Tech Spec §3.4 prints it, and the ten options on the `init` command at `src/lore/cli.py:366-374`. The handler body currently reads `from lore.api import run_init; messages = run_init()`; it becomes a `plan_init`/`apply_init` call. The prompt orchestration inside it is US-019 — this story wires the flags straight through with no prompting and no summary.
  - `src/lore/api.py` — add the underscore aliases `_agents` and `_skills` beside the existing block at `src/lore/api.py:163-175`. Both are needed at `cli.py` **import** time, because `click.Choice` evaluates its set when the decorator runs. `_prompts` lands in US-018.
- **Files to create:** none.
- **Schema changes:** none.
- **Dependencies:** US-002 (`agent_ids()`), US-003 (`family_ids()`), US-014 (`plan_init`), US-015 (`apply_init`).

`SpaceSeparatedChoice` reaches Click private API — `parser._long_opt`, `parsed.process`, `state.rargs`, `state.opts` — and was verified on 8.3.2 alone. US-024 raises the declared `click` floor to `>=8.3,<9.0` for exactly that reason; the spec gate upheld it and ruled that **no implementation mission needs to verify the parser hook on 8.0–8.2**.

The `--help` text is a `\b`-guarded paragraph in the `init` docstring, matching how the existing enriched help is written elsewhere in `cli.py`. `tests/e2e/test_help_group_param.py` is the extension point.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_init_interactive.py` — extended | Anchor `conceptual-workflows-init-interactive`; space-separated parsing and the five `SpaceSeparatedChoice` cases (Tech Spec §14.2 folds them here) |
| E2E | `tests/e2e/test_error_handling.py` — extended | Anchor `conceptual-workflows-error-handling`; the constrained-flag exit-2 cases |
| E2E | `tests/e2e/test_help_group_param.py` — extended | Anchor `conceptual-workflows-help`; the `--help` contract |
| E2E | `tests/e2e/test_lore_init.py` — extended | Anchor `conceptual-workflows-lore-init`; `lore --json init` |
| Unit | `tests/unit/test_cli_imports_only_api.py` — unchanged rule, must stay green | |

### Test Stubs

```python
# E2E — Scenario 1: Space-separated multi-value parses both flags
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_space_separated_agent_and_skills_flags_both_apply(tmp_path, runner):
    pass


# E2E — Scenario 2: A following flag stops greedy consumption
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_following_flag_stops_greedy_consumption(tmp_path, runner):
    pass


# E2E — Scenario 3: A bare `-` is consumed as a value
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_bare_dash_is_consumed_as_a_value_and_rejected(tmp_path, runner):
    pass


# E2E — Scenario 4: An out-of-set token in the greedy tail still exits 2
# Exercises: lore codex show conceptual-workflows-error-handling — usage errors exit 2
def test_out_of_set_token_in_the_tail_exits_two_with_click_wording(tmp_path, runner):
    pass


# E2E — Scenario 5: A repeated flag accumulates rather than raising
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_repeated_agent_flag_accumulates(tmp_path, runner):
    pass


# E2E — Scenario 6: Every constrained flag exits 2 on a bad value
# Exercises: lore codex show conceptual-workflows-error-handling — usage errors exit 2
def test_every_constrained_flag_exits_two_and_writes_nothing(tmp_path, runner):
    pass


# E2E — Scenario 7: `lore init --help` teaches the flag surface and the JSON exception
# Exercises: lore codex show conceptual-workflows-help — the teaching contract
def test_init_help_names_every_flag_and_the_json_exception(runner):
    pass


# E2E — Scenario 8: `lore --json init` is accepted, ignored and exits 0
# Exercises: lore codex show conceptual-workflows-lore-init — the permanent --json exception
def test_json_flag_on_init_is_accepted_and_ignored(tmp_path, runner):
    pass


# E2E — the ten declared options match the spec table
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_init_declares_the_ten_documented_options():
    pass


# E2E — no config-derived Click default
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_no_init_option_default_comes_from_config():
    pass


# E2E — SpaceSeparatedChoice shape
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_space_separated_choice_overrides_only_add_to_parser():
    pass


# E2E — choice sets come from the registry and the catalogue
# Exercises: lore codex show conceptual-workflows-init-interactive — The Flags
def test_choice_sets_are_registry_and_catalogue_derived():
    pass
```

### Complexity Estimate

**L** — ten flags, a Click parser subclass riding on private API, five parser edge cases, an enriched help contract, and a pinned `--json` behaviour that must not shift; each piece is small but the surface is wide and ADR-012 and ADR-017 both bear on it.

### Standards References

- `lore codex show decisions-012-multi-value-cli-param-convention`
- `lore codex show decisions-017-constrained-flags-use-click-choice`
- `lore codex show decisions-008-help-as-teaching-interface`
- `lore codex show standards-separation-of-concerns` — argv parsing belongs in `cli.py`
- `lore codex show technical-test-guidelines` — why the parser cases are E2E
