---
id: interactive-init-us-019
title: US-019 — lore init asks, shows a summary, and writes nothing until confirmed
summary: When standard output is a terminal, lore init prompts in a fixed order,
  prints every create, overwrite, removal and conflict before writing anything, and
  applies only on confirmation — while a caller with no terminal sees no prompt at
  all, and --dry-run prints the plan and writes nothing either way.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- decisions-001-dumb-infrastructure
- decisions-011-api-parity-with-cli
- conceptual-workflows-init-interactive
- conceptual-workflows-error-handling
---

# US-019 — `lore init` asks, shows a summary, and writes nothing until confirmed

## Metadata

- **ID:** US-019
- **Status:** final
- **Epic:** _CLI Surface_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a developer adopting Lore on an existing repository_, I want _`lore init` to ask me how I work and show me exactly what it will do before it does it_, so that _I get a setup that matches my project and never discover a change I did not agree to_.

## Context

This is the PRD's first workflow end to end, and its two critical decision points are both about restraint: an existing `CLAUDE.md` must never be overwritten wholesale, and **the summary must be shown before any file is written, not after**.

FR-7 is the summary and its confirmation. FR-9 is the other side: a caller without a terminal receives no prompt and Lore proceeds on defaults and flags alone. Tech Spec §1 puts the gate at `sys.stdout.isatty()`, evaluated in `cli.py` only — a false result selects defaults silently and never fails.

§3.2 adds `--dry-run` because the `isatty` gate creates a hazard without it: `lore init | tee upgrade.log` is not a terminal, so no prompt fires and the full plan — removals included — applies unseen. `--dry-run` is the only way to read the plan before an upgrade in that situation. It composes with `--yes`, and `--dry-run` wins.

The prompt sequence follows `prompts_needed` (US-014): `plan_init` is called once with what is known, the CLI inspects the plan, asks only the warranted questions, and calls `plan_init` again with the answers filled in. Recorded answers suppress the questions they answer unless `--reconfigure` is passed (FR-10).

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: A first interactive run asks in the fixed order and applies on confirmation

**Given** an empty project directory, `sys.stdout.isatty` forced to `True`, and the `lore.prompts` functions monkeypatched to canned answers
**When** the caller runs `lore init`
**Then** the prompt functions are called in the order agents → access mode → skill families → existing instruction file → root `.gitignore` → installed-skill tracking → summary confirm, a summary block is printed before any file is written, and on confirmation `.claude/skills/` holds the selected families, `CLAUDE.md` carries a `<!-- lore:begin -->` block, the root `.gitignore` carries a `# lore:begin` block, `.lore/config.toml` carries the four `init-*` keys, and `.lore/.install-manifest.json` exists

#### Scenario 2: Declining the summary writes nothing

**Given** the same setup with the summary confirm answering no
**When** the caller runs `lore init`
**Then** stdout carries `No changes applied.`, exit is 0, and no file exists outside the directory's pre-run state — asserted by a recursive path-and-mtime snapshot taken before and after

#### Scenario 3: The summary names every action with its counts

**Given** a plan carrying creates, a section, an overwrite, removals and conflicts
**When** the summary is rendered
**Then** it opens with `Plan for <root> (agents: <ids> · access: <mode> · families: <families>)`, lists one line per file prefixed `Create`, `Section`, `Overwrite`, `Remove` or `Conflict`, quotes the retirement reason on each `Remove` line and the successor on each `Conflict` line, and closes with a counts line of the form `13 create · 2 section · 0 overwrite · 0 remove · 0 conflict`

#### Scenario 4: No terminal means no prompt

**Given** an empty project directory with `sys.stdout.isatty` returning `False` and no flags
**When** the caller runs `lore init`
**Then** no prompt function is called, no summary confirm fires, the run applies the default plan, skills land in `.lore/skills/`, and no instruction file is written outside `.lore/`

#### Scenario 5: `--yes` suppresses every prompt including the confirm

**Given** a terminal and a project with conflicts
**When** the caller runs `lore init --yes`
**Then** no prompt function is called, the plan is applied with the default `--on-conflict skip`, and the summary is still printed

#### Scenario 6: `--dry-run` prints the plan and writes nothing

**Given** a project needing changes
**When** the caller runs `lore init --dry-run`
**Then** the summary is printed, the final line is `Dry run — no files written.`, exit is 0, and a recursive path-and-mtime snapshot is identical before and after — and the same holds for `lore init --dry-run --yes`

#### Scenario 7: Recorded answers suppress their questions until `--reconfigure`

**Given** a project whose `.lore/config.toml` records all four persisted answers
**When** the caller runs `lore init` with a terminal, then `lore init --reconfigure`
**Then** the first run asks neither the agents, access-mode, skill-families nor installed-skill-tracking question, and the second asks all four with the recorded values preselected

#### Scenario 8: The conditional prompts fire only in their own case

**Given** three projects — one with a pre-existing `CLAUDE.md` carrying no Lore markers, one selecting an agent with no native skills directory, and one with edited installed skills
**When** each is initialised with a terminal
**Then** the first asks the existing-instruction-file question and the other two do not; the second does **not** ask the installed-skill-tracking question; the third asks the conflict question and the other two do not

#### Scenario 9: Ctrl-C aborts and writes nothing

**Given** a terminal and a prompt function stubbed to signal an abort
**When** the caller runs `lore init`
**Then** stderr carries `Aborted!`, exit is 1, and nothing is written

### Unit Test Scenarios

- [ ] `lore.cli`: the `isatty` check is the only prompt gate and appears exactly once in the `init` handler
- [ ] `lore.cli._render_plan`: the header, the per-file lines and the counts line match the §4.3 format for a synthetic plan
- [ ] `lore.cli._render_plan`: a `Remove` line carries the `PlannedFile.detail` string verbatim; a `Conflict` line carries its detail
- [ ] `lore.cli._render_plan`: an entry whose action is a no-op is not rendered
- [ ] `lore.cli`: the prompt sequence calls `plan_init` twice — once before prompting and once after — and never more than twice on a run with no conditional prompts
- [ ] `lore.cli`: `--dry-run` short-circuits before `apply_init` is reached, asserted by monkeypatching `apply_init` to raise
- [ ] `lore.cli`: `--yes` skips every prompt function, asserted by monkeypatching each to raise
- [ ] `lore.cli`: a declined confirm returns exit 0 and never calls `apply_init`

---

## Out of Scope

- The prompt functions themselves — US-018.
- The flags — US-016.
- The plan and the apply — US-014 and US-015.
- Driving `prompt_toolkit`: every test monkeypatches `lore.prompts` and forces `sys.stdout.isatty` (Tech Spec §14.3).

---

## References

- PRD: `lore codex show interactive-init-prd` FR-1 through FR-10, and the first, third and fourth user workflows
- Tech Spec: `lore codex show interactive-init-tech-spec` §1, §3.2, §4.2, §4.3, §14.1
- `lore codex show decisions-001-dumb-infrastructure` — amended in place to admit a human-first interactive command class
- `lore codex show conceptual-workflows-error-handling` — the declined-confirm and Ctrl-C exits

---

## Tech Notes

### Implementation Approach

- **Files to modify:** `src/lore/cli.py` — the `init` handler at `src/lore/cli.py:366-374`.
  1. Build the keyword arguments from the flags (US-016).
  2. Call `plan_init` once.
  3. If `sys.stdout.isatty()` and not `--yes`: ask prompts 1–3 and 5a unless recorded (or `--reconfigure`), then ask each prompt named in `plan.prompts_needed`.
  4. Call `plan_init` again with every answer filled in.
  5. Render the summary through a new `_render_plan(plan) -> str`.
  6. If `--dry-run`: print `Dry run — no files written.` and exit 0.
  7. If interactive and not `--yes`: ask the confirm; on no, print `No changes applied.` and exit 0.
  8. Call `apply_init(plan)` and print `Initialized Lore project:` followed by `InitResult.messages`.
- **Files to create:** none.
- **Schema changes:** none.
- **Dependencies:** US-014, US-015, US-016, US-018.

Two prompt-order details from Tech Spec §4.3 and §7.4 that the tests pin:

- The installed-skill-tracking question fires **only** when a selected agent has a native skills directory (FR-6). Selecting `agents-md` alone does not ask it.
- The existing-instruction-file question fires **only** when the file exists and carries no Lore markers. A file that does not exist is created with markers; a file that already has them has its block replaced. Neither asks.

`sys.stdout.isatty()` is evaluated in `cli.py` and nowhere else (Tech Spec §1). No business module may consult it — that would be exactly the CLI-only rule ADR-011 forbids, in reverse.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_init_interactive.py` — extended | Anchor `conceptual-workflows-init-interactive`; every scenario above except Scenario 4 |
| E2E | `tests/e2e/test_lore_init.py` — extended | Anchor `conceptual-workflows-lore-init`; Scenario 4, the headless no-prompt guarantee |
| Unit | `tests/unit/test_lore_init.py` — extended | `_render_plan` against synthetic plans (it takes a plan and returns a string, so it needs no CLI import) |

`_render_plan` must be reachable without importing `lore.cli` for the unit half to be legal under `technical-test-guidelines` §2 and §6. The implementer puts it in `src/lore/init.py` and has `cli.py` call it through `lore.api`; only the orchestration stays in `cli.py`.

### Test Stubs

```python
# E2E — Scenario 1: A first interactive run asks in the fixed order and applies on confirmation
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_first_interactive_run_prompts_in_order_and_applies(tmp_path, runner, monkeypatch):
    pass


# E2E — Scenario 2: Declining the summary writes nothing
# Exercises: lore codex show conceptual-workflows-init-interactive — The Summary, prompt 7 (apply this plan?)
def test_declining_the_summary_writes_nothing_and_exits_zero(tmp_path, runner, monkeypatch):
    pass


# E2E — Scenario 3: The summary names every action with its counts
# Exercises: lore codex show conceptual-workflows-init-interactive — The Summary
def test_summary_lists_every_action_and_closes_with_counts(tmp_path, runner, monkeypatch):
    pass


# E2E — Scenario 4: No terminal means no prompt
# Exercises: lore codex show conceptual-workflows-lore-init — headless initialisation
def test_no_tty_means_no_prompt_and_pre_feature_placement(tmp_path, runner, monkeypatch):
    pass


# E2E — Scenario 5: `--yes` suppresses every prompt including the confirm
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_yes_flag_suppresses_every_prompt(tmp_path, runner, monkeypatch):
    pass


# E2E — Scenario 6: `--dry-run` prints the plan and writes nothing
# Exercises: lore codex show conceptual-workflows-init-interactive — The TTY Gate (--dry-run)
def test_dry_run_prints_the_plan_and_writes_nothing(tmp_path, runner, monkeypatch):
    pass


# E2E — Scenario 7: Recorded answers suppress their questions until `--reconfigure`
# Exercises: lore codex show conceptual-workflows-init-interactive — Answers Are Recorded
def test_recorded_answers_suppress_prompts_until_reconfigure(project_dir, runner, monkeypatch):
    pass


# E2E — Scenario 8: The conditional prompts fire only in their own case
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts (conditional)
def test_conditional_prompts_fire_only_in_their_own_case(tmp_path, runner, monkeypatch):
    pass


# E2E — Scenario 9: Ctrl-C aborts and writes nothing
# Exercises: lore codex show conceptual-workflows-error-handling — abort path
def test_ctrl_c_aborts_with_exit_one_and_no_writes(tmp_path, runner, monkeypatch):
    pass


# Unit — the isatty gate appears once
# Exercises: lore codex show conceptual-workflows-init-interactive — The TTY Gate
def test_isatty_is_the_only_prompt_gate():
    pass


# Unit — _render_plan format
# Exercises: lore codex show conceptual-workflows-init-interactive — The Summary
def test_render_plan_header_lines_and_counts():
    pass


# Unit — remove and conflict lines carry their detail
# Exercises: lore codex show conceptual-workflows-init-interactive — The Summary
def test_remove_and_conflict_lines_quote_their_detail():
    pass


# Unit — no-op entries are not rendered
# Exercises: lore codex show conceptual-workflows-init-interactive — The Summary
def test_noop_entries_are_not_rendered():
    pass


# Unit — plan_init called exactly twice
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_plan_init_called_once_before_and_once_after_prompting(monkeypatch):
    pass


# Unit — dry-run short-circuits before apply
# Exercises: lore codex show conceptual-workflows-init-interactive — The TTY Gate (--dry-run)
def test_dry_run_never_reaches_apply_init(monkeypatch):
    pass


# Unit — yes skips every prompt
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts
def test_yes_skips_every_prompt_function(monkeypatch):
    pass


# Unit — declined confirm never applies
# Exercises: lore codex show conceptual-workflows-init-interactive — The Summary, prompt 7 (apply this plan?)
def test_declined_confirm_never_calls_apply_init(monkeypatch):
    pass
```

### Complexity Estimate

**L** — an eight-step orchestration with a TTY gate, three conditional prompts, a two-pass plan computation, a rendered summary with an exact format, and three separate exit paths (declined, dry-run, abort).

### Standards References

- `lore codex show decisions-001-dumb-infrastructure` — the human-first interactive command class this amendment admits
- `lore codex show decisions-011-api-parity-with-cli` — the CLI orchestrates, it never decides
- `lore codex show conceptual-workflows-error-handling`
- `lore codex show technical-test-guidelines`
