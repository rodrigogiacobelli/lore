---
id: interactive-init-us-010
title: US-010 — Projects that predate the manifest still reconcile
summary: A packaged legacy-hashes.json lets Lore recognise its own previously shipped
  skill files by hash when no install manifest exists, across `.lore/skills/` and every
  agent skills directory in the packaged registry, so a long-idle project cleans
  up cleanly on its first upgrade while every tree Lore cannot prove it wrote into is
  left alone, with a release pre-flight script keeping the hash set current.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-install-manifest
- ops-publish-pypi
- decisions-006-no-seed-content-tests
- conceptual-workflows-init-reconcile
---

# US-010 — Projects that predate the manifest still reconcile

## Metadata

- **ID:** US-010
- **Status:** final
- **Epic:** _Manifest and Reconciliation_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a developer who initialised the project on a release that predates the install manifest_, I want _my first upgrade to recognise the skills Lore itself installed and clean them up_, so that _I get the same tidy result as a project that has a manifest, without risking a file I wrote_.

## Context

FR-30 requires Lore to reconcile a project that predates the install manifest by matching files against hashes it has shipped previously, and to keep any file it cannot match. Without it, the very projects most in need of the consolidation — the ones that have not re-initialised in a while — are the ones it cannot help.

Tech Spec §6.3 scoped the fallback to `.lore/skills/**` only, on the premise that this was the only place a pre-feature skill could live. **That premise was wrong and the scope has been corrected.** Lore's own pre-feature `GETTING-STARTED.md` told users, verbatim, to run `cp -r .lore/skills/. .claude/skills/` — so the documented workflow put a copy of every skill in the agent's own directory, and a fallback that walked only `.lore/skills/` was unreachable for everyone who followed the instructions. Their upgrade left `.claude/skills/` holding `new-doctrine` *and* `update-doctrine`, which is the doubling this feature exists to prevent.

The fallback therefore walks `.lore/skills/` plus the `skills_dir` of every agent in the packaged registry that exists on disk — every registry row, not only the agents selected this run, so a project that copied into `.claude/skills/` and now initialises for Gemini still gets the stale copies removed. The historical table stays keyed `.lore/skills/<rel>`, because that is the path Lore installed to; a candidate at `<root>/<rel>` is looked up under that key and the `RecordedEntry` is written at the candidate's actual path, so the removal targets the real file.

Widening the walk cannot widen what is touched: the path lookup comes before the hash, so a path Lore never shipped is never read. Everything else Lore seeds lives under a `default/` subtree that re-init already overwrites in place.

**Corrected by the ownership ruling.** This story originally said a file Lore shipped but the user edited is *kept*. It is not, and has not been since Lore was ruled to own the files it installs (`conceptual-workflows-init-reconcile`, "Lore Owns the Files It Installs"): a **current** skill at a path the table names is rewritten, and a **retired** one is removed with its successor quoted. What the fallback still refuses to do is guess — and that refusal is now stated about a *tree* rather than a path, because it authorises an unlink instead of a report. A hit whose on-disk hash is in the historical set becomes an `installed` entry. A known path whose hash matches nothing shipped is named too, so the run can act on it — but only when something else under the same root *did* match, which is what proves Lore ever wrote there. A root with no match at all is claimed in no part: a project that authored its own `inquest/SKILL.md` in a directory holding nothing of Lore's keeps it (FR-28). After one `lore init` a real manifest exists and the fallback never runs again for that project.

`.lore/skills/.gitignore` is deliberately absent from the file: it is generated per release, so its historical hashes vary with the shipped skill list, and an unmatched file is kept. A stale gitignore listing retired directories inside a tree that `.lore/.gitignore` already ignores wholesale is harmless.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Pristine previous-release skills are recognised and removed

**Given** a project with `.lore/skills/` populated with byte-identical copies of a previous release's skill files, one user-authored skill directory, and **no** `.lore/.install-manifest.json`
**When** the caller runs `lore init --yes`
**Then** every previous-release skill directory whose files match a shipped historical hash is removed, the user-authored directory is untouched and reported as kept, and a real manifest exists afterwards

#### Scenario 2: A file Lore shipped but the user edited is taken back

**Given** the same project with one previous-release `SKILL.md` modified by the user
**When** the caller runs `lore init --yes`
**Then** a **current** skill is overwritten with this release's version and recorded, and a **retired** one is removed with its ledger reason and successor quoted; either way the report says the edit was discarded

#### Scenario 2b: A tree Lore cannot prove it wrote into is left alone

**Given** a skills root in which no file's hash matches anything Lore has shipped, holding a `SKILL.md` at an id Lore also ships
**When** the caller runs `lore init --yes`
**Then** that file's bytes are unchanged afterwards and it is absent from the new manifest

#### Scenario 3: The fallback runs once and never again

**Given** the project from Scenario 1 after one successful `lore init`
**When** the caller runs `lore init --yes` a second time
**Then** the run reports zero removals, and `reconcile.legacy_recorded` is not consulted — asserted by monkeypatching it to raise

#### Scenario 4: The stale skills gitignore is left where it is

**Given** a project with a `.lore/skills/.gitignore` written by an earlier release
**When** the caller runs `lore init --yes`
**Then** the file still exists with unchanged bytes, and it appears in neither the plan nor the new manifest

#### Scenario 5: Skills copied into the agent directory are reconciled too

**Given** a project with no manifest whose previous-release skills sit under `.claude/skills/` — where the pre-feature `GETTING-STARTED.md` told the user to copy them — alongside one skill the user wrote
**When** the caller runs `lore init --yes`
**Then** every retired directory under `.claude/skills/` is removed with its ledger reason quoted, the replacements are installed there, and the user-authored skill is neither read, removed nor listed in the plan

#### Scenario 6: Both trees are cleaned in one run

**Given** a project holding the same previous-release skills in both `.lore/skills/` and `.claude/skills/`, with no manifest
**When** the caller runs `lore init --yes`
**Then** both trees lose their retired directories in that single run, and a second run reports nothing to change

### Unit Test Scenarios

- [ ] `lore.reconcile.legacy_recorded`: a file whose repo-relative path is a key in `legacy-hashes.json` and whose on-disk hash is in that key's list becomes a `recorded` entry with `kind == "owned"` and that hash
- [ ] `lore.reconcile.legacy_recorded`: a known path whose hash is not in the list is **absent** from the `installed` result
- [ ] `lore.reconcile.legacy_records`: a known path whose hash is not in the list is named in `shipped_paths` when some other file under the same root does match, and in nothing at all when none does
- [ ] `lore.reconcile.legacy_recorded`: an unknown path is absent from the result
- [ ] `lore.reconcile.legacy_recorded`: a project with no skills tree returns an empty mapping without raising
- [ ] `lore.reconcile.legacy_recorded`: a matching path planted under `.claude/skills/` **is** recorded, at that path, with the `.lore/skills/<rel>` table row supplying its hash set
- [ ] `lore.reconcile.legacy_recorded`: a project holding the same skill in both `.lore/skills/` and `.claude/skills/` records both
- [ ] `lore.reconcile.legacy_recorded`: a path Lore never shipped is never hashed, whichever root it sits in
- [ ] `lore.reconcile.legacy_skills_roots`: `.lore/skills` plus every non-null `skills_dir` in the packaged registry, deduplicated and sorted
- [ ] `lore.reconcile.legacy_recorded`: a missing or unparseable packaged `legacy-hashes.json` raises `RuntimeError` naming the packaged file (a build defect, per Tech Spec §4.2)
- [ ] `src/lore/defaults/legacy-hashes.json`: exists, parses, has `legacy_hashes_version` and a `files` object whose every value is a non-empty list of `sha256:`-prefixed strings (structural assertions only — ADR-006)
- [ ] `scripts/update_legacy_hashes.py`: hashes every file under `src/lore/defaults/skills/`, prefixes each relative path with `.lore/skills/`, and unions into the existing file
- [ ] `scripts/update_legacy_hashes.py`: never removes an existing row — a key present before the run is present after it, with its prior hashes retained
- [ ] `scripts/update_legacy_hashes.py`: idempotent — running twice on an unchanged tree produces a byte-identical file
- [ ] `scripts/update_legacy_hashes.py`: does not add a row for `.lore/skills/.gitignore`

---

## Out of Scope

- The reconciliation table itself — US-009 consumes the `recorded` set this story produces.
- Widening the fallback to entity trees — doctrines, knights, artifacts and watchers live under a `default/` subtree that re-init overwrites in place. That overwrite is intended behaviour, not an accident, and the ownership ruling generalises it to every file Lore installs. (Tech Spec §16 also rejected widening to the agent skills directories; that half of the rejection was wrong and has been reversed — see Context.)
- Running the pre-flight script as part of CI — it is a release step documented in `ops-publish-pypi`, and that doc update belongs to the phase-5 codex-apply mission.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-30, FR-31
- Tech Spec: `lore codex show interactive-init-tech-spec` §6.3, §6.6, §16
- `lore codex show tech-arch-install-manifest`
- `lore codex show ops-publish-pypi` — where the pre-flight step is recorded
- `lore codex show decisions-006-no-seed-content-tests`

---

## Tech Notes

### Implementation Approach

- **Files to create:**
  - `src/lore/defaults/legacy-hashes.json` — format per Tech Spec §6.3: `legacy_hashes_version: 1` and a `files` object mapping `.lore/skills/<path>` to a list of historical `sha256:` digests. Seeded by running the script below against the pre-consolidation tree **before** US-005 and US-006 delete it, then again after — so the file carries both the retired names and the current ones.
  - `scripts/update_legacy_hashes.py` — new top-level `scripts/` directory (none exists today). Hashes every file under `src/lore/defaults/skills/`, prefixes each relative path with `.lore/skills/`, unions into the existing file, never removes a row, and is idempotent.
- **Files to modify:** `src/lore/reconcile.py` — add `legacy_recorded(project_root) -> dict[str, RecordedEntry]` implementing the four steps of Tech Spec §6.6, plus `legacy_skills_roots()` naming the trees it walks, plus a packaged-file loader following the `agents.py` pattern (`importlib.resources`, `lru_cache`, `RuntimeError` on a build defect). `reconcile` imports `lore.agents` for the registry: a sibling data module whose only `lore` dependency is `initplan`, so the arrow still points inward.
- **Schema changes:** none — the legacy file is packaged data with a fixed shape, not a validated entity kind.
- **Dependencies:** US-008 (`file_digest`), US-009 (`reconcile` consumes the result), US-005 and US-006 (the tree whose pre-consolidation hashes must be captured **before** deletion).

**Sequencing note for the implementer and the story grouper:** the pre-consolidation hashes have to be captured before US-005 and US-006 delete the thirteen directories. Either run the script and commit its output ahead of those two stories, or recover the hashes from git history. This is the one ordering constraint in the feature that a `git checkout` cannot undo cheaply.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_init_reconcile.py` — extended | Anchor `conceptual-workflows-init-reconcile`; the no-manifest scenarios |
| Unit | `tests/unit/test_reconcile.py` — extended | `legacy_recorded` on synthetic hash tables |
| Unit | `tests/unit/test_package_distribution.py` — extended | `legacy-hashes.json` ships in the wheel; the script's idempotency and union behaviour |

### Test Stubs

```python
# E2E — Scenario 1: Pristine previous-release skills are recognised and removed
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_no_manifest_project_removes_matched_shipped_files(legacy_skills_project, runner):
    pass


# E2E — Scenario 2: A file Lore shipped but the user edited is kept
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_edited_previous_release_file_is_kept_and_absent_from_the_manifest(legacy_skills_project, runner):
    pass


# E2E — Scenario 3: The fallback runs once and never again
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_legacy_recorded_not_consulted_once_a_manifest_exists(legacy_skills_project, runner, monkeypatch):
    pass


# E2E — Scenario 4: The stale skills gitignore is left where it is
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_stale_skills_gitignore_untouched(legacy_skills_project, runner):
    pass


# Unit — hash hit becomes a recorded entry
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_hash_hit_becomes_owned_recorded_entry(tmp_path, monkeypatch):
    pass


# Unit — hash miss is absent
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_hash_miss_is_not_recorded(tmp_path, monkeypatch):
    pass


# Unit — unknown path is absent
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_unknown_path_is_not_recorded(tmp_path, monkeypatch):
    pass


# Unit — no .lore/skills/ at all
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_missing_skills_tree_returns_empty(tmp_path):
    pass


# Unit — the agent skills directory is walked too
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_legacy_scan_reaches_agent_skills_directories(tmp_path, monkeypatch):
    pass


# Unit — a path Lore never shipped is never read, whichever root it sits in
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_a_path_lore_never_shipped_is_never_read(tmp_path, monkeypatch):
    pass


# Unit — missing packaged file is a build defect
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_missing_legacy_hashes_file_raises_runtimeerror(monkeypatch):
    pass


# Unit — shipped legacy-hashes.json is structurally valid (ADR-006)
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_shipped_legacy_hashes_structure():
    pass


# Unit — the pre-flight script unions rather than replaces
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_update_script_never_removes_an_existing_row(tmp_path):
    pass


# Unit — the pre-flight script is idempotent
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_update_script_is_idempotent(tmp_path):
    pass


# Unit — the script skips the generated gitignore
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_update_script_skips_skills_gitignore(tmp_path):
    pass
```

### Complexity Estimate

**M** — one loader, one walk with a hash lookup, and a small release script; the logic is short but the keep-on-doubt bias and the capture-before-delete sequencing both need care.

### Standards References

- `lore codex show decisions-006-no-seed-content-tests` — the packaged hash file is asserted structurally
- `lore codex show ops-publish-pypi` — the release pre-flight step
- `lore codex show technical-test-guidelines`
