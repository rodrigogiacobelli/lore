---
id: interactive-init-us-004
title: US-004 — One authored skill source, two access modes
summary: A skills.render function selects HTML-comment-marked access-mode blocks out
  of a single authored SKILL.md at install time, so one source per skill produces
  either the Lore-CLI command layer or the agent-native one, while text outside any
  block survives in both.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-skill-catalogue
- decisions-001-dumb-infrastructure
- decisions-006-id-references
- decisions-006-no-seed-content-tests
- standards-dry
- conceptual-workflows-init-interactive
---

# US-004 — One authored skill source, two access modes

## Metadata

- **ID:** US-004
- **Status:** final
- **Epic:** _Rendering the Skills_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a Lore maintainer_, I want _each skill authored once with its two command layers marked inline_, so that _a project's chosen access mode is injected at install time and the two variants can never drift apart_.

## Context

FR-19 requires one authored source per skill with the access mode injected at install. FR-16 and FR-17 are the two outputs. FR-18 pins the exception: `lore codex map`, `lore codex chaos` and `lore impacts` stay in both modes, because no agent file tool reproduces a precomputed graph traversal.

Tech Spec §7.2 makes all three fall out of one convention. Text inside `<!-- lore:access cli -->` … `<!-- lore:access end -->` survives only under `cli`; text inside `<!-- lore:access native -->` … `<!-- lore:access end -->` only under `native`; text outside any block is unconditional — which is where FR-18's three commands are authored, so no third `both` token is needed (§16).

ADR-001 rejected a template engine on the grounds that Lore would have to understand and evaluate templates. Block selection is line-range arithmetic: no variables, no expression language.

This story delivers the renderer as a pure string function. `decisions-006-no-seed-content-tests` decides how it is proved: fixtures are authored **inside the test file**, never read from `src/lore/defaults/`.

---

## Acceptance Criteria

### E2E Scenarios

_This story has no CLI surface of its own: every scenario below calls a `lore.*` function directly, so all of them are written in `tests/unit/` (`technical-test-guidelines` §2, §8). See Test File Locations._

#### Scenario 1: The CLI layer survives and the native layer is dropped

**Given** a document containing a `cli` block, a `native` block, and a trailing unblocked paragraph
**When** a caller runs `skills.render(text, AccessMode.CLI)`
**Then** the returned string contains the `cli` block's body with its two marker lines removed, contains none of the `native` block's body, contains no `<!-- lore:access` marker at all, and contains the trailing unblocked paragraph verbatim

#### Scenario 2: The native layer survives and the CLI layer is dropped

**Given** the same document
**When** a caller runs `skills.render(text, AccessMode.NATIVE)`
**Then** the mirror of Scenario 1 holds

#### Scenario 3: Every shipped file is well-formed under both modes

**Given** the shipped tree at `src/lore/defaults/skills/` and `src/lore/defaults/docs/LORE-AGENT.md`
**When** every file is passed through `skills.render` once per mode
**Then** no call raises, and every `<!-- lore:access ... -->` region in every shipped file is terminated and names `cli` or `native` — asserted as structural well-formedness, never against any rendered word

#### Scenario 4: A malformed block is a loud failure

**Given** a document with an opener and no `<!-- lore:access end -->`
**When** a caller runs `skills.render(text, AccessMode.CLI)`
**Then** `ValueError` is raised naming the offending line number, and the same holds for an unknown mode token, an `end` with no opener, and a nested opener

### Unit Test Scenarios

- [ ] `lore.skills.render`: `cli` kept and `native` dropped; then the reverse — on a fixture authored in the test file
- [ ] `lore.skills.render`: text outside any block is byte-identical in both modes
- [ ] `lore.skills.render`: two adjacent blocks with no blank line between them each resolve independently
- [ ] `lore.skills.render`: a block that ends at end-of-file with no trailing newline renders without raising and without adding a newline
- [ ] `lore.skills.render`: a dropped block removes its two marker lines, its body, and a single trailing newline — the surrounding text keeps its own blank-line structure
- [ ] `lore.skills.render`: an unterminated block raises `ValueError` naming the opener's line number
- [ ] `lore.skills.render`: `<!-- lore:access agentic -->` raises `ValueError` naming the unknown token and the line
- [ ] `lore.skills.render`: `<!-- lore:access end -->` with no opener raises `ValueError` naming the line
- [ ] `lore.skills.render`: an opener inside an open block raises `ValueError` (blocks never nest)
- [ ] `lore.skills.render`: a document with no markers at all is returned unchanged
- [ ] `lore.skills.render`: accepts `AccessMode` members and is the single place block selection happens (no second copy in `init.py`)

---

## Out of Scope

- Authoring the access blocks into any shipped skill — US-005 and US-006.
- Rendering `LORE-AGENT.md`'s generated skills table — US-007.
- Hashing the rendered output — US-008.
- Choosing which mode a project gets — US-013 (config) and US-016 (flag).

---

## References

- PRD: `lore codex show interactive-init-prd` FR-16, FR-17, FR-18, FR-19
- Tech Spec: `lore codex show interactive-init-tech-spec` §7.2, §7.3, §14.2, §16
- `lore codex show decisions-001-dumb-infrastructure` — why no template engine
- `lore codex show decisions-006-id-references` — the entity types agent-native mode does **not** cover
- `lore codex show decisions-006-no-seed-content-tests` — fixtures are authored in the test

---

## Tech Notes

### Implementation Approach

- **Files to modify:** `src/lore/skills.py` (created in US-003) gains `render(text: str, mode: AccessMode) -> str`. Algorithm per Tech Spec §7.2: scan line by line for `<!-- lore:access MODE -->` … `<!-- lore:access end -->`; keep a matching region's body with its two marker lines stripped; drop a non-matching region entirely, markers and one trailing newline included; blocks never nest; an unterminated block, an unknown `MODE`, or an `end` with no opener raises `ValueError` naming the file and line.
- **Files to create:** none.
- **Schema changes:** none.
- **Dependencies:** US-001 (`AccessMode`), US-003 (`skills.py` exists).

The implementer should keep `render` free of any file I/O — it takes text and returns text. The caller that reads a `SKILL.md` off the package and passes its contents in is US-011's desired-file enumeration. A `ValueError` message needs the file name, so `render` takes an optional `source: str | None = None` used only in error text; the enumerator passes the packaged path.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| Unit | `tests/unit/test_skills.py` — extended | **Every scenario above is a unit test.** `skills.render` is a pure string function and the shipped-tree sweep reads package data; neither invokes a CLI (`technical-test-guidelines` §2, §8). The user-visible half — a skill installed in the chosen mode — is covered by US-011 and US-019 |
| Unit | `tests/unit/test_skills.py` — extended | The renderer against test-authored fixtures — the whole error matrix |

### Test Stubs

```python
# E2E — Scenario 1: The CLI layer survives and the native layer is dropped
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_render_cli_mode_keeps_cli_block_and_drops_native():
    # Given: fixture text with a cli block, a native block and unblocked trailing text
    # When: render(text, AccessMode.CLI)
    # Then: cli body present, native body absent, no marker survives, trailing text verbatim
    pass


# E2E — Scenario 2: The native layer survives and the CLI layer is dropped
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_render_native_mode_is_the_mirror():
    pass


# E2E — Scenario 3: Every shipped file is well-formed under both modes
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_every_shipped_access_block_is_terminated_and_named():
    # Structural only: no assertion on any rendered word (ADR-006)
    pass


# E2E — Scenario 4: A malformed block is a loud failure
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_malformed_blocks_raise_valueerror_with_a_line_number():
    pass


# Unit — mode selection both directions
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_block_selection_both_directions_on_authored_fixture():
    pass


# Unit — unblocked text is unconditional
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_text_outside_any_block_is_identical_in_both_modes():
    pass


# Unit — adjacent blocks
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_adjacent_blocks_resolve_independently():
    pass


# Unit — block at EOF without trailing newline
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_block_at_end_of_file_without_trailing_newline():
    pass


# Unit — a dropped block takes one trailing newline with it
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_dropped_block_removes_markers_body_and_one_newline():
    pass


# Unit — unterminated block
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_unterminated_block_raises_naming_the_opener_line():
    pass


# Unit — unknown mode token
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_unknown_mode_token_raises():
    pass


# Unit — end with no opener
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_end_without_opener_raises():
    pass


# Unit — nesting is rejected
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_nested_opener_raises():
    pass


# Unit — a document with no markers is returned unchanged
# Exercises: lore codex show conceptual-workflows-init-interactive — The Prompts, prompt 2 (access mode)
def test_document_without_markers_is_unchanged():
    pass
```

### Complexity Estimate

**M** — a single pure string function, but the error matrix is wide (four raise cases) and the newline/adjacency behaviour has to be exact because every installed file's hash depends on it.

### Standards References

- `lore codex show standards-dry` — one authored source, not two copies
- `lore codex show decisions-001-dumb-infrastructure` — no template engine
- `lore codex show decisions-006-no-seed-content-tests` — fixtures authored in the test file
- `lore codex show technical-test-guidelines`
