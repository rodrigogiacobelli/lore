---
id: interactive-init-us-009
title: US-009 — Three-way reconciliation, correct for any version hop
summary: One table compares what the installed Lore release would write against what the manifest
  recorded against the bytes on disk, and classifies every path as create, overwrite,
  section, remove, conflict or keep — with a path in neither set never read, written
  or deleted, and empty directories pruned after removals.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-install-manifest
- decisions-003-soft-delete-semantics
- conceptual-workflows-init-reconcile
---

# US-009 — Three-way reconciliation, correct for any version hop

## Metadata

- **ID:** US-009
- **Status:** final
- **Epic:** _Manifest and Reconciliation_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a developer upgrading Lore from any earlier release, including one several versions back_, I want _renamed and merged skills cleaned up and my own edits left alone_, so that _`git status` shows no unexpected untracked files and I lose nothing I wrote_.

## Context

FR-26 through FR-31 are all one algorithm. Tech Spec §1 rejects a per-version migration chain outright: each step becomes permanent code and a 0.8 → 0.14 hop has to replay all of them in order. The three-way reconciliation is one table, correct for any hop, including skipped releases and downgrades (§15).

```
desired  = the set of (path, kind, rendered-bytes) this release would write, given the answers
recorded = manifest.files, or the legacy fallback when no manifest exists
on_disk  = the actual bytes at each path
```

The last row of §6.4's table is FR-28's safety property: **a path in neither `recorded` nor `desired` is never read, never written, never deleted.** §6.5 states the operative reading FR-28 requires — hashing a path that is in `desired` is the *mechanism* that keeps a user's own file from being clobbered, not a violation of it.

`REMOVE` is a hard unlink and §6.4 records why that does not breach ADR-003: the ADR governs entities managed by the `lore` CLI, and a skill has no `lore delete` path, no ID retrieval and no CRUD surface at all. What replaces the soft-delete guarantee here is the hash test — a path is only ever unlinked when the manifest says Lore wrote it **and** its bytes still match what Lore wrote.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Renamed and merged skills are removed with the ledger reason quoted

**Given** a project seeded with the previous catalogue and a matching manifest, upgraded to the current release
**When** the caller runs `lore init --yes`
**Then** every retired skill directory is gone from disk, each removal is reported as `  Removed <path> — <reason>` with the `reason` string taken verbatim from the catalogue's `retired` map, and the new manifest lists exactly the current file set

#### Scenario 2: An unmodified installed file whose content changed is overwritten silently

**Given** a project whose manifest records `.claude/skills/start-quest/SKILL.md` with a hash matching the bytes on disk, and a release that renders different bytes for that path
**When** the caller runs `lore init --yes`
**Then** the file is classified `OVERWRITE`, no conflict prompt fires, and the file's bytes afterwards equal the rendered bytes

#### Scenario 3: A user-authored file at a path Lore wants is never overwritten

**Given** a project with no manifest entry for `.claude/skills/store-memory/SKILL.md` and a user-authored file at that exact path
**When** the caller runs `lore init --yes` (default `--on-conflict skip`)
**Then** the entry is classified `CONFLICT` with detail `not installed by Lore`, the file's bytes are byte-identical afterwards, and the run exits 0 — this is the FR-28 safety property

#### Scenario 4: An edited installed file is a conflict, and refusing leaves it untouched

**Given** a project whose manifest records two skills whose on-disk bytes have since been edited
**When** the caller runs `lore init --yes --on-conflict skip`
**Then** both files are byte-identical afterwards, both are reported as `! Kept <path>` with the successor named, everything else in the plan is applied, and exit is 0

#### Scenario 5: Accepting the conflict performs the write

**Given** the same project
**When** the caller runs `lore init --yes --on-conflict overwrite`
**Then** both files carry the rendered bytes afterwards and are reported as overwrites, not conflicts

#### Scenario 6: Flipping the access mode is an overwrite, not a phantom edit

**Given** a project installed with `--access native` and an unmodified skill set
**When** the caller runs `lore init --access cli --yes`
**Then** every installed skill is classified `OVERWRITE` and none is classified `CONFLICT`; a skill the user edited before the flip is still classified `CONFLICT`

#### Scenario 7: A path in neither set is never touched

**Given** a project with a user-authored `.claude/skills/my-own-skill/SKILL.md` that Lore has never installed and does not ship
**When** the caller runs `lore init --yes`
**Then** the file's bytes and mtime are unchanged, the directory survives, and the path appears nowhere in the plan or the new manifest

#### Scenario 8: Directories left empty by removals are pruned

**Given** a project whose only content under `.claude/skills/new-doctrine/` is the retired `SKILL.md`
**When** the caller runs `lore init --yes`
**Then** `.claude/skills/new-doctrine/` no longer exists, `.claude/skills/` still exists, and a sibling directory holding a user file survives untouched

### Unit Test Scenarios

- [ ] `lore.reconcile.reconcile`: not recorded, in desired, absent on disk → `CREATE`, reported
- [ ] `lore.reconcile.reconcile`: not recorded, in desired, on disk with hash == desired → `CREATE`, **not** reported (already correct)
- [ ] `lore.reconcile.reconcile`: not recorded, in desired, on disk with hash != desired → `CONFLICT` with detail `not installed by Lore`, always reported
- [ ] `lore.reconcile.reconcile`: recorded, in desired, absent on disk → `CREATE` (restore), reported
- [ ] `lore.reconcile.reconcile`: recorded, in desired, hash == recorded and desired == recorded → no-op, not reported
- [ ] `lore.reconcile.reconcile`: recorded, in desired, hash == recorded and desired != recorded → `OVERWRITE`, reported
- [ ] `lore.reconcile.reconcile`: recorded, in desired, hash != recorded → `CONFLICT` with detail `edited since install`, always reported
- [ ] `lore.reconcile.reconcile`: recorded, not in desired, hash == recorded → `REMOVE` carrying the ledger reason
- [ ] `lore.reconcile.reconcile`: recorded, not in desired, hash != recorded → `KEEP` carrying the ledger successor
- [ ] `lore.reconcile.reconcile`: recorded, not in desired, absent on disk → dropped from the result and from the next manifest, not reported
- [ ] `lore.reconcile.reconcile`: a path in neither set is absent from the result entirely, and the function performs no read on it
- [ ] `lore.reconcile.reconcile`: a `section` entry compares the digest of the text between the markers only; `REMOVE` on a `section` entry means "delete the marked block", leaving the rest of the file untouched
- [ ] `lore.reconcile.reconcile`: `on_conflict="skip"` turns a conflicted `REMOVE` candidate into `KEEP`; `on_conflict="overwrite"` performs the write the row would otherwise have carried
- [ ] `lore.reconcile.reconcile`: the returned tuple is sorted by `path`, deterministically, for the same inputs in any argument order
- [ ] `lore.reconcile.prune_empty_dirs`: an empty chain is removed up to the target root; the walk stops at the first non-empty ancestor; the target root itself is never removed; a directory holding a user file survives
- [ ] `lore.reconcile.prune_empty_dirs`: a path outside the target root is never removed

---

## Out of Scope

- Building the `desired` set — US-011.
- The `recorded` set when no manifest exists — US-010.
- Performing the writes and unlinks — US-015.
- Asking the human about a conflict — US-018 and US-019; this story only classifies and honours the `on_conflict` token it is given.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-26, FR-27, FR-28, FR-29, FR-30, FR-31
- Tech Spec: `lore codex show interactive-init-tech-spec` §6.4, §6.5, §15, §16
- `lore codex show tech-arch-install-manifest` — the doc that governs `src/lore/reconcile.py`
- `lore codex show decisions-003-soft-delete-semantics` — the scope boundary a skill sits outside of

---

## Tech Notes

### Implementation Approach

- **Files to create:** `src/lore/reconcile.py` — `reconcile(desired, recorded, project_root, *, on_conflict="skip", retirement_reason=None) -> tuple[PlannedFile, ...]` implementing every row of Tech Spec §6.4, and `prune_empty_dirs(removed_paths, stop_at) -> tuple[Path, ...]`.
- **Files to modify:** none. `reconcile.py` imports `lore.initplan` and `lore.manifest` and nothing else from `lore.*` — it must not import `init.py`, which is the dependency direction `standards-dependency-inversion` requires and the reason `PlannedFile` lives in a leaf module (Tech Spec §5.1).
- **Schema changes:** none.
- **Dependencies:** US-001 (`PlannedFile`, `FileAction`), US-003 (the retirement ledger supplies the `detail` string), US-008 (digests and the `recorded` shape).

`retirement_reason` is injected as a callable rather than imported, so `reconcile.py` does not depend on `skills.py`: the caller passes `skills.retirement_for`. That keeps the module testable on synthetic data with no package fixtures.

Directory pruning walks each removed path's ancestors upward, removing any directory that is now empty, stopping at the first non-empty directory or at the target skills root, whichever comes first. The target root itself is never removed. A directory containing anything Lore did not install is by definition non-empty and survives.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_init_reconcile.py` — extended | Anchor `conceptual-workflows-init-reconcile`; all eight scenarios |
| Unit | `tests/unit/test_reconcile.py` — NEW | Every one of the eleven table rows as its own case, plus pruning |

A fixture `legacy_skills_project` in `tests/e2e/conftest.py` materialises a project seeded with the previous catalogue, with or without a manifest and with optional edits, so the reconciliation scenarios read as data rather than setup (Tech Spec §14.3). No new `conftest.py` is added — `tests/e2e/conftest.py` already exists.

### Test Stubs

```python
# E2E — Scenario 1: Renamed and merged skills are removed with the ledger reason quoted
# Exercises: lore codex show conceptual-workflows-init-reconcile — The Outcomes
def test_retired_skills_removed_with_ledger_reason(legacy_skills_project, runner):
    pass


# E2E — Scenario 2: An unmodified installed file whose content changed is overwritten silently
# Exercises: lore codex show conceptual-workflows-init-reconcile — The Outcomes
def test_unmodified_installed_file_overwritten_without_a_prompt(legacy_skills_project, runner):
    pass


# E2E — Scenario 3: A user-authored file at a path Lore wants is never overwritten
# Exercises: lore codex show conceptual-workflows-init-reconcile — The Outcomes (a path in neither set)
def test_user_authored_file_at_a_desired_path_is_a_conflict_and_survives(legacy_skills_project, runner):
    pass


# E2E — Scenario 4: An edited installed file is a conflict, and refusing leaves it untouched
# Exercises: lore codex show conceptual-workflows-init-reconcile — Conflicts
def test_on_conflict_skip_leaves_edited_files_byte_identical(legacy_skills_project, runner):
    pass


# E2E — Scenario 5: Accepting the conflict performs the write
# Exercises: lore codex show conceptual-workflows-init-reconcile — Conflicts
def test_on_conflict_overwrite_replaces_edited_files(legacy_skills_project, runner):
    pass


# E2E — Scenario 6: Flipping the access mode is an overwrite, not a phantom edit
# Exercises: lore codex show conceptual-workflows-init-reconcile — The Outcomes (Overwrite)
def test_access_mode_flip_classifies_as_overwrite_not_conflict(legacy_skills_project, runner):
    pass


# E2E — Scenario 7: A path in neither set is never touched
# Exercises: lore codex show conceptual-workflows-init-reconcile — The Outcomes (a path in neither set)
def test_unknown_user_skill_untouched_and_absent_from_the_manifest(legacy_skills_project, runner):
    pass


# E2E — Scenario 8: Directories left empty by removals are pruned
# Exercises: lore codex show conceptual-workflows-init-reconcile — Removals
def test_empty_directories_pruned_and_populated_siblings_survive(legacy_skills_project, runner):
    pass


# Unit — one test per row of the §6.4 table (eleven cases)
# Exercises: lore codex show conceptual-workflows-init-reconcile — The Outcomes
def test_row_not_recorded_in_desired_absent_is_create():
    pass


def test_row_not_recorded_in_desired_identical_is_unreported_create():
    pass


def test_row_not_recorded_in_desired_different_is_conflict_not_installed_by_lore():
    pass


def test_row_recorded_in_desired_absent_is_restore_create():
    pass


def test_row_recorded_in_desired_unchanged_and_same_desired_is_noop():
    pass


def test_row_recorded_in_desired_unchanged_and_new_desired_is_overwrite():
    pass


def test_row_recorded_in_desired_edited_is_conflict_edited_since_install():
    pass


def test_row_recorded_not_desired_unchanged_is_remove_with_reason():
    pass


def test_row_recorded_not_desired_edited_is_keep_with_successor():
    pass


def test_row_recorded_not_desired_absent_is_forgotten():
    pass


def test_row_in_neither_set_is_never_read_or_returned():
    pass


# Unit — section entries hash only the marked block
# Exercises: lore codex show conceptual-workflows-init-reconcile — The Outcomes (Section)
def test_section_entry_compares_only_the_marked_block():
    pass


# Unit — on_conflict interacts with a conflicted remove
# Exercises: lore codex show conceptual-workflows-init-reconcile — Conflicts
def test_skip_turns_a_conflicted_remove_into_keep():
    pass


# Unit — deterministic ordering
# Exercises: lore codex show conceptual-workflows-init-reconcile — The Outcomes
def test_result_sorted_by_path_regardless_of_input_order():
    pass


# Unit — prune_empty_dirs
# Exercises: lore codex show conceptual-workflows-init-reconcile — Removals
def test_prune_stops_at_first_non_empty_ancestor_and_never_removes_the_root():
    pass


def test_prune_never_touches_a_path_outside_the_target_root():
    pass
```

### Complexity Estimate

**L** — eleven table rows, a `section`/`owned` split, a conflict policy that rewrites two of the rows, and directory pruning; every branch is a distinct test and the safety property has to hold on all of them.

### Standards References

- `lore codex show decisions-003-soft-delete-semantics` — why a hard unlink is in scope here
- `lore codex show standards-dependency-inversion` — `reconcile.py` never imports `init.py`
- `lore codex show technical-test-guidelines`
