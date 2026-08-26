---
id: interactive-init-us-015
title: US-015 — apply_init performs a computed plan, and run_init still takes no arguments
summary: apply_init writes the plan in a fixed order with the manifest last, reports
  every create, overwrite, removal and kept conflict, and run_init becomes a two-line
  wrapper whose zero-argument signature and list-of-strings return are unchanged.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-api-facade
- standards-public-api-stability
- decisions-010-public-api-stability
- conceptual-workflows-lore-init
- conceptual-workflows-python-api
---

# US-015 — `apply_init` performs a computed plan, and `run_init` still takes no arguments

## Metadata

- **ID:** US-015
- **Status:** final
- **Epic:** _Plan and Apply Core_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _an existing Realm deployment_, I want _`run_init()` to keep working with no arguments and produce the same files it always has_, so that _upgrading Lore changes nothing in my initialisation path_.

## Context

FR-33 and FR-34 are one story because they are one function. `run_init()` is `apply_init(plan_init())` plus message rendering, and its signature is unchanged: zero arguments, returns `list[str]`. That contract is pinned by `tests/e2e/test_api_parity_init.py` (Review-Ledger CHANGED #9), and a positional-arg change would be a major bump under `standards-public-api-stability`.

Tech Spec §6.7 fixes the write order and puts the manifest **last**. An interrupted run therefore leaves the previous manifest on disk; the next `lore init` sees the old `recorded` set, finds the already-written files' hashes differ from it, and classifies them as conflicts rather than silently overwriting. Slightly noisy, strictly safe — and it satisfies the PRD reliability requirement that an interrupted `lore init` leaves a project a subsequent `lore init` reconciles to a correct state.

Two error paths in §4.2 belong here: an unlink that fails skips that path and reports `! Kept <path> — could not remove: <reason>` while the run continues; a write that fails propagates, and the manifest-last ordering makes the partial state recoverable.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: `run_init()` still takes no arguments and produces the pre-feature file set

**Given** an empty directory as the working directory
**When** a caller runs `run_init()` with no arguments
**Then** it returns a `list[str]`, `.lore/lore.db` exists, every seeded skill sits under `.lore/skills/`, no instruction file is written outside `.lore/`, and the created path set equals the pre-feature set plus `.lore/.install-manifest.json`

#### Scenario 2: `apply_init` writes exactly the paths the plan named

**Given** a plan produced by `plan_init(project_root=tmp, agents=["claude"], skill_families=["memory"])`
**When** a caller runs `apply_init(plan)`
**Then** every `CREATE`, `OVERWRITE` and `SECTION` path in the plan exists afterwards with the planned bytes, every `REMOVE` path is gone, every `CONFLICT` path under `skip` is byte-identical to before, and `InitResult.applied` plus `InitResult.skipped` together partition `plan.files`

#### Scenario 3: The manifest is written last

**Given** a plan whose apply is interrupted after the skills are written but before the manifest is
**When** the caller runs `lore init --yes` again
**Then** the already-written skills are classified `CONFLICT` against the stale manifest rather than silently overwritten, the run exits 0, and a third run after resolving them reports zero changes

#### Scenario 4: Two consecutive runs with the same answers are idempotent

**Given** a project initialised once with a given answer set
**When** the caller runs `lore init --yes` a second time with the same answers
**Then** the second run reports zero creates, zero overwrites and zero removals, and the new manifest is byte-identical to the previous one apart from `generated_at`

#### Scenario 5: A failed unlink is reported and the run continues

**Given** a plan carrying two `REMOVE` entries, one of whose paths cannot be unlinked
**When** the caller runs `apply_init(plan)`
**Then** the other removal still happens, the failure is reported as `! Kept <path> — could not remove: <reason>`, the run returns normally, and the failed path stays in the next manifest

#### Scenario 6: A `section` removal deletes only the block

**Given** a project whose `CLAUDE.md` carries a Lore block and user prose, and a plan retiring that agent
**When** the caller runs `apply_init(plan)`
**Then** `CLAUDE.md` still exists, the Lore block and its two markers are gone, and every other byte is unchanged

#### Scenario 7: The report names the successor for each kept conflict

**Given** a plan carrying two `KEEP` entries for skills the user edited
**When** the caller runs `apply_init(plan)`
**Then** `InitResult.messages` carries a `! Kept <path>` line for each, followed by the retirement `detail` naming the successor skill

### Unit Test Scenarios

- [ ] `lore.init.apply_init`: writes in the §6.7 order — `.lore/` scaffolding, rendered skills in path order, `.lore/LORE-AGENT.md`, agent instruction blocks, root `.gitignore` block, skills gitignore, removals then pruning, manifest — asserted by recording write calls
- [ ] `lore.init.apply_init`: the manifest write is the final I/O call
- [ ] `lore.init.apply_init`: `InitResult.applied` and `InitResult.skipped` are disjoint and their union equals `plan.files`
- [ ] `lore.init.apply_init`: a `section` removal calls `remove_marked_section`, never `unlink`
- [ ] `lore.init.apply_init`: an `OSError` on unlink is caught, reported and does not abort the run; any other exception during a write propagates
- [ ] `lore.init.apply_init`: `InitResult.manifest_path` equals `paths.install_manifest_path(plan.project_root)`
- [ ] `lore.init.apply_init`: the four persisted answers are written into `.lore/config.toml` before the manifest
- [ ] `lore.init.run_init`: signature takes zero parameters, asserted with `inspect.signature`
- [ ] `lore.init.run_init`: returns `list[str]`, not a tuple — the pinned return type
- [ ] `lore.init.run_init`: equivalent to `list(apply_init(plan_init()).messages)`, asserted by comparing both against the same temp directory
- [ ] `lore.init._format_db_status`: still returns the three status branches unchanged (the message text itself is US-022)

---

## Out of Scope

- Computing the plan — US-014.
- Rendering the human-readable plan summary before the write — US-019.
- The `--yes` and `--dry-run` flags — US-016 and US-019.
- Re-export through `lore.api` — US-023.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-9, FR-29, FR-33, FR-34
- Tech Spec: `lore codex show interactive-init-tech-spec` §6.7, §4.2, §4.3, §5.3, §15
- `lore codex show standards-public-api-stability` — why `run_init`'s signature cannot move
- `lore codex show conceptual-workflows-python-api`

---

## Tech Notes

### Implementation Approach

- **Files to modify:** `src/lore/init.py`
  - Add `apply_init(plan: InitPlan) -> InitResult`.
  - Rewrite `run_init` at `src/lore/init.py:136` as a two-line wrapper: `return list(apply_init(plan_init()).messages)`. The body it replaces — the seeded-tree copies at `src/lore/init.py:159-193`, the rites skeleton at `src/lore/init.py:195-197`, and the `_write_skills_gitignore` call at `src/lore/init.py:202` — moves into `apply_init`'s step 1, minus the skills-gitignore call, which US-012 removes.
  - `_copy_defaults_tree("skills", ...)` at `src/lore/init.py:192` is replaced by the plan's rendered skill entries (US-011).
- **Files to create:** none.
- **Schema changes:** none.
- **Dependencies:** US-007, US-008, US-009, US-011, US-012, US-013, US-014.

The existing `tests/e2e/test_api_parity_init.py` is the contract to keep green. Its `test_run_init_zero_args_creates_lore_dir` and `test_run_init_idempotent` cases must not be edited to accommodate a new signature — if either needs a change, the implementation is wrong.

The parity anchor for FR-9 is precise: with `stdout` not a TTY and no flags, the created path set equals the pre-feature set **plus** `.lore/.install-manifest.json`. The implementer should capture the pre-feature set from `git stash`-clean `main` once and assert against a stored list, not against a regenerated one.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_api_parity_init.py` — extended | Anchor `conceptual-workflows-python-api`; `run_init` zero-arg, `apply_init` produces exactly the planned paths |
| E2E | `tests/e2e/test_lore_init.py` — extended | Anchor `conceptual-workflows-lore-init`; headless parity, idempotency, interrupted-run recovery |
| Unit | `tests/unit/test_lore_init.py` — extended | Write ordering, partitioning, unlink failure, section removal |

### Test Stubs

```python
# E2E — Scenario 1: run_init() still takes no arguments and produces the pre-feature file set
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_run_init_zero_arg_headless_parity(tmp_path, monkeypatch):
    pass


# E2E — Scenario 2: apply_init writes exactly the paths the plan named
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_apply_init_writes_exactly_the_planned_paths(tmp_path):
    pass


# E2E — Scenario 3: The manifest is written last
# Exercises: lore codex show conceptual-workflows-lore-init — interrupted run recovery
def test_interrupted_apply_recovers_as_conflicts_on_the_next_run(project_dir, runner):
    pass


# E2E — Scenario 4: Two consecutive runs with the same answers are idempotent
# Exercises: lore codex show conceptual-workflows-lore-init — idempotency
def test_second_run_reports_zero_changes_and_a_matching_manifest(project_dir, runner):
    pass


# E2E — Scenario 5: A failed unlink is reported and the run continues
# Exercises: lore codex show conceptual-workflows-lore-init — error paths
def test_failed_unlink_is_reported_and_the_run_continues(project_dir, monkeypatch):
    pass


# E2E — Scenario 6: A section removal deletes only the block
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_section_removal_deletes_only_the_block(project_dir):
    pass


# E2E — Scenario 7: The report names the successor for each kept conflict
# Exercises: lore codex show conceptual-workflows-lore-init — apply report
def test_kept_conflicts_report_their_successor(project_dir):
    pass


# Unit — write ordering
# Exercises: lore codex show conceptual-workflows-lore-init — apply ordering
def test_apply_writes_in_the_documented_order(tmp_path, monkeypatch):
    pass


# Unit — manifest last
# Exercises: lore codex show conceptual-workflows-lore-init — apply ordering
def test_manifest_is_the_final_write(tmp_path, monkeypatch):
    pass


# Unit — applied plus skipped partitions plan.files
# Exercises: lore codex show conceptual-workflows-lore-init — apply report
def test_applied_and_skipped_partition_the_plan(tmp_path):
    pass


# Unit — section removal never unlinks
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_section_removal_calls_remove_marked_section_not_unlink(tmp_path, monkeypatch):
    pass


# Unit — unlink failure handling
# Exercises: lore codex show conceptual-workflows-lore-init — error paths
def test_oserror_on_unlink_is_caught_and_other_errors_propagate(tmp_path, monkeypatch):
    pass


# Unit — manifest_path on the result
# Exercises: lore codex show conceptual-workflows-lore-init — apply report
def test_init_result_manifest_path(tmp_path):
    pass


# Unit — config written before the manifest
# Exercises: lore codex show conceptual-workflows-lore-init — recorded answers
def test_persisted_answers_written_before_the_manifest(tmp_path, monkeypatch):
    pass


# Unit — run_init signature and return type
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_run_init_takes_zero_parameters_and_returns_a_list():
    pass


# Unit — run_init equals apply_init(plan_init())
# Exercises: lore codex show conceptual-workflows-python-api — return-type contracts
def test_run_init_is_the_two_line_wrapper(tmp_path, monkeypatch):
    pass
```

### Complexity Estimate

**L** — the write side of the whole feature: an eight-step ordering, two distinct removal mechanisms, a partial-failure path, and a pinned public signature that must not move while everything underneath it does.

### Standards References

- `lore codex show standards-public-api-stability` — `run_init` keeps its signature
- `lore codex show decisions-010-public-api-stability`
- `lore codex show conceptual-workflows-error-handling`
- `lore codex show technical-test-guidelines`
