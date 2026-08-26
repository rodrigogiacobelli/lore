---
id: interactive-init-us-012
title: US-012 — Lore owns a marked block inside files the user owns
summary: Lore writes its section of an agent instruction file, the project's root
  .gitignore and the installed-skills gitignore between markers and replaces only that
  section on later runs, so an existing CLAUDE.md is never overwritten wholesale and
  every byte outside the markers survives.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-agents-md
- tech-arch-initialized-project-structure
- conceptual-workflows-lore-init
---

# US-012 — Lore owns a marked block inside files the user owns

## Metadata

- **ID:** US-012
- **Status:** final
- **Epic:** _Plan and Apply Core_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a developer with a `CLAUDE.md` I have been maintaining for months_, I want _Lore to add its section without touching anything else in the file_, so that _adopting Lore costs me nothing I have already written_.

## Context

The PRD's first workflow names the critical decision point: "An existing `CLAUDE.md` must never be overwritten wholesale." FR-15 states the mechanism — Lore writes its section between markers and replaces only that section on later runs. FR-5 and FR-6 apply the same mechanism to the root `.gitignore` and to the installed-skills gitignore.

Tech Spec §7.6 fixes the content. The root block, inside `#`-comment markers, names Lore-generated artefacts that are never committed: `.lore/lore.db`, `.lore/lore.db-wal`, `.lore/lore.db-shm`, `.lore/reports/`, `.lore/.install-manifest.json`. `.lore/codex/transient/` is deliberately absent — `!codex/**` un-ignores the transient layer on purpose, and many projects track in-flight PRDs and specs there. When `--skills-gitignore all` is chosen and a native skills directory exists, one further line joins the block.

The skills gitignore is written at the target skills directory only under `lore-only`; `none` writes no file, and `all` writes no file and adds the directory to the root block instead. All three are manifest-tracked as `owned`, so switching answers removes the previous file cleanly.

Tech Spec §2.1 fixes what a `section` entry hashes: **the rendered section text between the markers, markers excluded**. A user editing prose outside the markers never registers as a conflict.

FR-4's answer set is two, not three (§7.4): `append` adds the marked block and preserves everything else; `skip` leaves the file alone — and `.lore/LORE-AGENT.md` is written either way, so the collapsed `separate` option would have produced identical bytes.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: An existing instruction file keeps every original byte

**Given** a project with a `CLAUDE.md` containing user prose and no Lore markers
**When** the caller runs `lore init --agent claude --on-existing-agent-file append --yes`
**Then** every original byte of `CLAUDE.md` is still present in the same order, a `<!-- lore:begin -->` … `<!-- lore:end -->` block has been appended, and `.lore/LORE-AGENT.md` also exists

#### Scenario 2: `skip` leaves the file byte-identical

**Given** the same project
**When** the caller runs `lore init --agent claude --on-existing-agent-file skip --yes`
**Then** `CLAUDE.md` is byte-identical to before the run, `.lore/LORE-AGENT.md` is still written, and the plan carries no `SECTION` entry for `CLAUDE.md`

#### Scenario 3: A second run replaces only the block

**Given** a project whose `CLAUDE.md` carries a Lore block and user prose both above and below it
**When** the caller runs `lore init --yes` after a change that alters the rendered block
**Then** the block's content is replaced, both stretches of user prose are byte-identical, and the file has exactly one `<!-- lore:begin -->` and one `<!-- lore:end -->`

#### Scenario 4: The root gitignore block is appended and then replaced in place

**Given** a project with an existing root `.gitignore` carrying user entries
**When** the caller runs `lore init --gitignore --yes` twice
**Then** after the first run the file carries the user entries unchanged plus one `# lore:begin` … `# lore:end` block naming the five Lore artefacts, and after the second run the file is byte-identical to after the first

#### Scenario 5: `--no-gitignore` writes nothing

**Given** a project with no root `.gitignore`
**When** the caller runs `lore init --no-gitignore --yes`
**Then** no root `.gitignore` is created, and the plan carries no entry for it

#### Scenario 6: The skills gitignore follows its token

**Given** a project selecting Claude Code
**When** the caller runs `lore init` with `--skills-gitignore lore-only`, then `none`, then `all`
**Then** `lore-only` writes `.claude/skills/.gitignore` listing exactly the installed skill directories one per line; `none` writes no such file and removes a previously written one; `all` writes no such file, removes a previously written one, and adds `.claude/skills/` to the root `.gitignore` block

#### Scenario 7: Editing outside the markers is not a conflict

**Given** a project whose `CLAUDE.md` carries a Lore block, where the user has since edited prose **outside** the markers
**When** the caller runs `lore init --yes`
**Then** the `CLAUDE.md` entry is not classified `CONFLICT`, the user's edit survives, and the block is refreshed

### Unit Test Scenarios

- [ ] `lore.init.write_marked_section`: file absent → created containing only the block, with the marker pair
- [ ] `lore.init.write_marked_section`: file present without markers → block appended; every prior byte precedes it unchanged
- [ ] `lore.init.write_marked_section`: file present with markers → text between them replaced; bytes before the opener and after the closer are byte-identical
- [ ] `lore.init.write_marked_section`: a file with two marker pairs raises `ValueError` naming the file rather than guessing which to replace
- [ ] `lore.init.write_marked_section`: an opener with no closer raises `ValueError` naming the file
- [ ] `lore.init.remove_marked_section`: deletes the block and its two marker lines, leaving the rest of the file byte-identical; a file with no markers is left untouched
- [ ] `lore.init._marker_pair`: returns HTML markers for a `.md`/`.mdc` target and `#`-comment markers for `.gitignore`
- [ ] `lore.init.render_root_gitignore_block`: names exactly the five Lore artefacts; adds `.claude/skills/` only when `skills_gitignore == "all"` and a native skills directory is among the targets; never names `.lore/codex/transient/`
- [ ] `lore.init.render_skills_gitignore`: lists the installed skill directory names sorted, one per line with a trailing `/`, under a two-line explanatory comment header
- [ ] `lore.init.render_skills_gitignore`: called with `none` or `all` returns `None`, signalling no file
- [ ] `lore.manifest.section_digest` integration: the digest of a `section` entry changes when the block changes and not when surrounding prose changes

---

## Out of Scope

- Prompting for any of these answers — US-018 and US-019.
- The `--gitignore` / `--skills-gitignore` / `--on-existing-agent-file` flags — US-016.
- Rendering the instruction text itself — US-007.
- The write ordering these functions are called in — US-015.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-4, FR-5, FR-6, FR-15
- Tech Spec: `lore codex show interactive-init-tech-spec` §7.4, §7.6, §2.1, §6.2
- `lore codex show tech-arch-agents-md` — the rewritten marker contract
- `lore codex show conceptual-workflows-lore-init`

---

## Tech Notes

### Implementation Approach

- **Files to modify:** `src/lore/init.py` — add `write_marked_section(target, block_text, *, markers)`, `remove_marked_section(target, *, markers)`, `_marker_pair(target)`, `render_root_gitignore_block(...)` and `render_skills_gitignore(skill_ids)`. Remove `_write_skills_gitignore` at `src/lore/init.py:216` and its call at `src/lore/init.py:202`: the existing `skills/` line in `.lore/.gitignore` already ignores the whole `.lore/skills/` tree, so the unconditional write has no job left (Tech Spec §7.6). A `.lore/skills/.gitignore` left behind by an earlier release is not in `recorded` and is therefore never touched.
- **Files to create:** none.
- **Schema changes:** none.
- **Dependencies:** US-007 (the block text), US-008 (`section_digest`), US-011 (the installed skill ids for the gitignore listing).

Marker forms, per Tech Spec §7.6 and §7.4:

- Markdown targets (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `QWEN.md`, `.cursor/rules/lore.mdc`): `<!-- lore:begin -->` … `<!-- lore:end -->`
- `.gitignore`: `# lore:begin — managed by \`lore init\`; edits between these markers are replaced` … `# lore:end`

`.cursor/rules/lore.mdc` is a file Lore creates whole rather than a pre-existing user file in most projects, but it takes the same marker treatment so a hand-edited one is still safe.

The FR-4 prompt fires only in the case where the file exists and carries no Lore markers. A file that does not exist is created with markers; a file that already has markers has its block replaced. Neither asks.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_lore_init.py` — extended | Anchor `conceptual-workflows-lore-init`; marker behaviour is init behaviour |
| Unit | `tests/unit/test_lore_init.py` — extended | The marker writers and the two gitignore renderers |

### Test Stubs

```python
# E2E — Scenario 1: An existing instruction file keeps every original byte
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_append_preserves_every_original_byte_of_claude_md(project_dir, runner):
    pass


# E2E — Scenario 2: `skip` leaves the file byte-identical
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_skip_leaves_claude_md_byte_identical_and_still_writes_lore_agent(project_dir, runner):
    pass


# E2E — Scenario 3: A second run replaces only the block
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_second_run_replaces_only_the_marked_block(project_dir, runner):
    pass


# E2E — Scenario 4: The root gitignore block is appended and then replaced in place
# Exercises: lore codex show conceptual-workflows-lore-init — root gitignore block
def test_root_gitignore_block_appended_then_idempotent(project_dir, runner):
    pass


# E2E — Scenario 5: `--no-gitignore` writes nothing
# Exercises: lore codex show conceptual-workflows-lore-init — root gitignore block
def test_no_gitignore_flag_creates_no_root_gitignore(project_dir, runner):
    pass


# E2E — Scenario 6: The skills gitignore follows its token
# Exercises: lore codex show conceptual-workflows-lore-init — installed-skill tracking
def test_skills_gitignore_lore_only_none_and_all(project_dir, runner):
    pass


# E2E — Scenario 7: Editing outside the markers is not a conflict
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_editing_outside_the_markers_is_not_a_conflict(project_dir, runner):
    pass


# Unit — create when absent
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_write_marked_section_creates_file_when_absent(tmp_path):
    pass


# Unit — append when present without markers
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_write_marked_section_appends_when_no_markers(tmp_path):
    pass


# Unit — replace between markers
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_write_marked_section_replaces_between_markers(tmp_path):
    pass


# Unit — two marker pairs raise
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_duplicate_marker_pairs_raise(tmp_path):
    pass


# Unit — unterminated marker raises
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_opener_without_closer_raises(tmp_path):
    pass


# Unit — remove_marked_section
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_remove_marked_section_deletes_block_and_keeps_the_rest(tmp_path):
    pass


# Unit — marker pair selection by target type
# Exercises: lore codex show conceptual-workflows-lore-init — root gitignore block
def test_marker_pair_html_for_markdown_and_hash_for_gitignore():
    pass


# Unit — root gitignore block content
# Exercises: lore codex show conceptual-workflows-lore-init — root gitignore block
def test_root_block_names_five_artefacts_and_never_the_transient_layer():
    pass


# Unit — the `all` token adds the skills directory line
# Exercises: lore codex show conceptual-workflows-lore-init — installed-skill tracking
def test_all_token_adds_native_skills_directory_to_the_root_block():
    pass


# Unit — skills gitignore listing
# Exercises: lore codex show conceptual-workflows-lore-init — installed-skill tracking
def test_skills_gitignore_lists_installed_directories_sorted():
    pass


# Unit — none and all write no skills gitignore
# Exercises: lore codex show conceptual-workflows-lore-init — installed-skill tracking
def test_none_and_all_return_no_skills_gitignore():
    pass


# Unit — section digest tracks only the block
# Exercises: lore codex show conceptual-workflows-lore-init — instruction-file marker block
def test_section_digest_changes_only_with_the_block():
    pass
```

### Complexity Estimate

**M** — three marker-managed targets sharing one writer, plus two small renderers; the logic is short but every branch is a user-file-safety branch and each needs its own test.

### Standards References

- `lore codex show tech-arch-agents-md`
- `lore codex show standards-single-responsibility` — one writer, marker pair injected
- `lore codex show technical-test-guidelines`
