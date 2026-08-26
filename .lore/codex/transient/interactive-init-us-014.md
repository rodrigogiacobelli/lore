---
id: interactive-init-us-014
title: US-014 — plan_init computes an initialisation without performing it
summary: A Python caller receives a typed InitPlan describing every create, overwrite,
  section, removal and conflict, with each answer resolved argument then config then
  built-in default, reconfigure skipping the config layer, and prompts_needed naming
  the conditional questions the plan justifies.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-api-facade
- tech-arch-project-root-detection
- decisions-011-api-parity-with-cli
- decisions-021-health-reports-are-ephemeral-by-default
- conceptual-workflows-lore-init
---

# US-014 — `plan_init` computes an initialisation without performing it

## Metadata

- **ID:** US-014
- **Status:** final
- **Epic:** _Plan and Apply Core_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _Realm_, I want _to compute exactly what an initialisation would do without performing it_, so that _I can decide, log or refuse it before a single file changes_.

## Context

FR-32 is the requirement; Tech Spec §1 makes it the feature's central architectural decision. `plan_init(...) -> InitPlan` computes; `apply_init(plan) -> InitResult` writes. Prompting exists only in the CLI layer and only to fill `plan_init` parameters, because ADR-011 forbids logic that lives only in the CLI: every prompt's *effect* is a keyword parameter here, so a Python caller reaches the same behaviour without a terminal.

`prompts_needed` is what lets the CLI know a conditional prompt is warranted without the core function owning a prompt. `plan_init` is called once with whatever is known, the CLI inspects `prompts_needed`, asks, and calls `plan_init` again with the answers filled in. Two plan computations, no prompt inside the core — this is how ADR-011 is satisfied without a callback (Tech Spec §16 records the rejected callback design).

**`plan_init` is the only reader of the four `init-*` config keys.** ADR-021 constraint 2 settled the shape: `health_check` resolves `health-report-retention` and "no caller — `lore health` included — reads the key and decides for itself. A second reader of that key is a duplicate implementation and an ADR-011 violation." The four `init-*` keys get the same treatment, which is why no flag carries a config-derived Click default (§3.3).

`project_root=None` resolves to `Path.cwd()`, preserving `run_init`'s behaviour and honouring `tech-arch-project-root-detection`'s rule that `lore init` is the documented exception to `find_project_root()`.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: A plan is returned and nothing is written

**Given** an empty directory
**When** a caller runs `plan_init(project_root=tmp)` and then snapshots the directory
**Then** an `InitPlan` is returned whose `files` is non-empty, and the directory's recursive path set and mtimes are identical to before the call — no `.lore/` is created

#### Scenario 2: Resolution order is argument, then config, then default

**Given** a project whose `.lore/config.toml` carries `init-access-mode = "cli"`
**When** a caller runs `plan_init(project_root=p)`, then `plan_init(project_root=p, access_mode="native")`, then the same against a project with no config file
**Then** the three plans carry `answers.access_mode` of `cli`, `native` and `native` respectively — config wins over the built-in default, the argument wins over config

#### Scenario 3: `reconfigure` skips the config layer

**Given** the same project with `init-agents = ["claude"]` and `init-access-mode = "cli"` recorded
**When** a caller runs `plan_init(project_root=p, reconfigure=True)`
**Then** `answers.agents` is empty and `answers.access_mode` is `native` — the built-in defaults — while `plan.answers` still reports the recorded values through a separate `recorded` view the CLI preselects from

#### Scenario 4: A headless plan reproduces the pre-feature file set

**Given** an empty directory
**When** a caller runs `plan_init(project_root=tmp)` with no keyword arguments
**Then** `answers.agents` is empty, `answers.access_mode` is `native`, `answers.skill_families` is all three families, every skill path in `files` sits under `.lore/skills/`, and no path outside `.lore/` appears except the root `.gitignore` entry

#### Scenario 5: An unknown token raises with the documented wording

**Given** an empty directory
**When** a caller runs `plan_init(project_root=tmp, agents=["cline"])`
**Then** `ValueError` is raised with the message `Unknown agent: 'cline'. Known agents: agents-md, claude, cursor, gemini, none, qwen.`, and the same shape holds for an invalid `access_mode`, `skill_families` item, `on_conflict` and `skills_gitignore` token

#### Scenario 6: `prompts_needed` names only the warranted conditional prompts

**Given** a project with a pre-existing `CLAUDE.md` carrying no Lore markers, an agent selection of `("claude",)`, and two edited installed skills recorded in the manifest
**When** a caller runs `plan_init(project_root=p, agents=["claude"])`
**Then** `prompts_needed` contains the tokens for the existing-instruction-file question, the installed-skill-tracking question and the conflict question — and on a fresh project with none of those conditions it is empty

### Unit Test Scenarios

- [ ] `lore.init.plan_init`: `project_root=None` resolves to `Path.cwd()`
- [ ] `lore.init.plan_init`: each of the seven answers resolves argument → `.lore/config.toml` → built-in default, one test per keyword
- [ ] `lore.init.plan_init`: `reconfigure=True` skips the config layer for the four persisted answers and leaves the three unpersisted ones on their defaults
- [ ] `lore.init.plan_init`: `skill_families=["all"]` and `skill_families=["none"]` are accepted and resolved through `skills.resolve_families` — identical to the `--skills` behaviour (ADR-011)
- [ ] `lore.init.plan_init`: calls `validators.validate_agent_id`, `validate_agent_selection`, `validate_access_mode` and `validate_skill_family`, and raises `ValueError` on any non-`None` return (the wiring; the rule itself is US-017)
- [ ] `lore.init.plan_init`: `files` is sorted by path and `conflicts` is exactly the `CONFLICT` subset of `files`
- [ ] `lore.init.plan_init`: `targets` holds one `AgentTarget` per selected agent, in registry order
- [ ] `lore.init.plan_init`: `prompts_needed` is empty on a fresh project with no agent selected
- [ ] `lore.init.plan_init`: `prompts_needed` names the existing-instruction-file prompt only when a selected agent's file exists **and** carries no Lore markers
- [ ] `lore.init.plan_init`: `prompts_needed` names the installed-skill-tracking prompt only when a selected agent has a non-null `skills_dir`
- [ ] `lore.init.plan_init`: `prompts_needed` names the conflict prompt only when `conflicts` is non-empty
- [ ] `lore.init.plan_init`: writes nothing — asserted by a recursive path-and-mtime snapshot around the call
- [ ] `lore.init.plan_init`: two calls with identical inputs return plans whose `files` tuples compare equal

---

## Out of Scope

- Performing the plan — US-015.
- The four validators' own behaviour — US-017; this story wires them in and asserts the wiring.
- Prompting on `prompts_needed` — US-019.
- Re-export through `lore.api` — US-023.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-9, FR-10, FR-32
- Tech Spec: `lore codex show interactive-init-tech-spec` §1, §5.2, §5.3, §3.3, §9.2, §16
- `lore codex show decisions-011-api-parity-with-cli`
- `lore codex show decisions-021-health-reports-are-ephemeral-by-default` — constraint 2
- `lore codex show tech-arch-project-root-detection`

---

## Tech Notes

### Implementation Approach

- **Files to modify:** `src/lore/init.py` — add `plan_init(project_root=None, *, agents=None, access_mode=None, skill_families=None, on_existing_agent_file="append", root_gitignore=None, skills_gitignore=None, on_conflict="skip", reconfigure=False) -> InitPlan`, signature exactly as Tech Spec §5.3. It composes: resolve answers → `agents.get_agent` per id → `skills.desired_files` (US-011) → `manifest.load` or `reconcile.legacy_recorded` (US-008, US-010) → `reconcile.reconcile` (US-009) → assemble `InitPlan`.
- **Files to create:** none.
- **Schema changes:** none.
- **Dependencies:** US-001, US-002, US-003, US-008, US-009, US-010, US-011, US-012 (its renderers contribute the instruction-file and gitignore entries to `desired`), US-013 (the config layer).

Non-skill entries the desired set also carries, per Tech Spec §6.7's write order: the `.lore/` seeded trees, `.lore/LORE-AGENT.md` (`owned`), each selected agent's instruction-file block (`section`), the root `.gitignore` block (`section`), and the skills gitignore (`owned`).

Default resolution, per §9.2: the non-interactive default for `skill_families` is **all three families**, so a Realm deployment that depends on `update-doctrine` keeps it across the upgrade. The interactive checkbox preselecting memory and workflow is a CLI-layer concern and belongs in US-019, not here.

`reconfigure=True` skips the config layer for the four persisted answers. The recorded values still have to reach `cli.py` so a human sees them preselected at the prompt (FR-10) — Tech Spec §3.3 says the CLI preselects from `InitPlan.answers` on the first `plan_init` call and never from `load_config()`. The implementer therefore exposes the recorded answers on the plan rather than letting `cli.py` open the config file.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_api_parity_init.py` — extended | Anchor `conceptual-workflows-python-api`; the plan-without-writing and typed-return scenarios |
| E2E | `tests/e2e/test_lore_init.py` — extended | Anchor `conceptual-workflows-lore-init`; resolution order and headless parity |
| Unit | `tests/unit/test_lore_init.py` — extended | Resolution order per keyword, `prompts_needed`, determinism |

### Test Stubs

```python
# E2E — Scenario 1: A plan is returned and nothing is written
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_plan_init_returns_a_plan_and_writes_nothing(tmp_path):
    pass


# E2E — Scenario 2: Resolution order is argument, then config, then default
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_argument_beats_config_beats_default(project_dir):
    pass


# E2E — Scenario 3: `reconfigure` skips the config layer
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_reconfigure_skips_the_config_layer(project_dir):
    pass


# E2E — Scenario 4: A headless plan reproduces the pre-feature file set
# Exercises: lore codex show conceptual-workflows-lore-init — headless initialisation
def test_no_argument_plan_matches_the_pre_feature_file_set(tmp_path):
    pass


# E2E — Scenario 5: An unknown token raises with the documented wording
# Exercises: lore codex show conceptual-workflows-lore-init — error paths
def test_unknown_tokens_raise_valueerror_with_documented_wording(tmp_path):
    pass


# E2E — Scenario 6: `prompts_needed` names only the warranted conditional prompts
# Exercises: lore codex show conceptual-workflows-lore-init — conditional prompts
def test_prompts_needed_reflects_the_project_state(project_dir):
    pass


# Unit — project_root=None resolves to cwd
# Exercises: lore codex show conceptual-workflows-lore-init — project root resolution
def test_plan_init_defaults_project_root_to_cwd(tmp_path, monkeypatch):
    pass


# Unit — resolution order, one test per keyword
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_resolution_order_per_keyword(project_dir):
    pass


# Unit — reconfigure skips config for the four persisted answers
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_reconfigure_only_affects_persisted_answers(project_dir):
    pass


# Unit — aggregates accepted on the Python surface
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_skill_families_all_and_none_accepted_by_plan_init(tmp_path):
    pass


# Unit — validators are wired in
# Exercises: lore codex show conceptual-workflows-validators — validator wiring
def test_plan_init_calls_the_four_validators(tmp_path, monkeypatch):
    pass


# Unit — files sorted, conflicts is the CONFLICT subset
# Exercises: lore codex show conceptual-workflows-lore-init — plan shape
def test_files_sorted_and_conflicts_subset(tmp_path):
    pass


# Unit — targets in registry order
# Exercises: lore codex show conceptual-workflows-lore-init — plan shape
def test_targets_one_per_selected_agent_in_registry_order(tmp_path):
    pass


# Unit — prompts_needed, three conditional cases plus the empty case
# Exercises: lore codex show conceptual-workflows-lore-init — conditional prompts
def test_prompts_needed_empty_on_a_fresh_project(tmp_path):
    pass


def test_prompts_needed_existing_instruction_file_case(project_dir):
    pass


def test_prompts_needed_skills_tracking_case(project_dir):
    pass


def test_prompts_needed_conflict_case(project_dir):
    pass


# Unit — plan_init writes nothing
# Exercises: lore codex show conceptual-workflows-lore-init — plan/apply split
def test_plan_init_touches_no_file(tmp_path):
    pass


# Unit — determinism
# Exercises: lore codex show conceptual-workflows-lore-init — plan shape
def test_two_identical_plan_calls_compare_equal(tmp_path):
    pass
```

### Complexity Estimate

**L** — the composition point for eight upstream modules, with a seven-keyword three-layer resolution order and a conditional-prompt signal that has to be right for the CLI to behave; no single branch is hard but there are many and they all meet here.

### Standards References

- `lore codex show decisions-011-api-parity-with-cli` — no rule may live only in the CLI
- `lore codex show decisions-021-health-reports-are-ephemeral-by-default` — one reader per command-scoped config key
- `lore codex show standards-separation-of-concerns`
- `lore codex show technical-test-guidelines`
