---
id: custom-codex-schemas-us-5
title: US-5 — lore codex create/edit accept declared custom keys
summary: >
  codex.create_document and update_document pass project_root into
  validate_entity so frontmatter is validated against the merged schema at write
  time (FR-9). A declared custom key is accepted; an undeclared key still errors;
  a malformed overlay raises OverlayError which, being a ValueError subclass,
  propagates unchanged out of create/edit's documented ValueError-on-schema-failure
  contract — no traceback escapes lore codex.
type: user-story
related:
  - custom-codex-schemas-tech-spec
  - custom-codex-schemas-us-3
---

## Metadata

- **ID:** US-5
- **Status:** final
- **Epic:** Validation integration
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-06-18
- **PRD:** `lore codex show custom-codex-schemas-prd`
- **Tech Spec:** `lore codex show custom-codex-schemas-tech-spec`

---

## Story

As a **codex maintainer running `lore codex create` / `lore codex edit`**, I want **a declared custom frontmatter key to pass validation at write time**, so that **writing a doc with `owner: alice` succeeds consistently with what `lore health` accepts, while a typo is still rejected**.

## Context

FR-9: create/edit must accept custom keys at write time consistently with the health audit. Both `create_document` (`codex.py:121`) and `update_document` (`codex.py:193`) call `validate_entity(_DOC_TYPE_SCHEMAS[kind], meta)` (`codex.py:151`, `codex.py:222`) on in-memory parsed frontmatter; `project_root` is already a parameter of both. The Tech Spec wires them to pass `project_root=project_root` into the keyword US-3 added. Both functions document "Raises `ValueError` on any … schema failure" (`codex.py:132`, `codex.py:201`); ordinary validation issues are already joined into a `ValueError`, and a malformed-overlay `OverlayError` (subclass of `ValueError`) propagates unchanged through the same contract — no separate handling, no traceback (Tech Spec Error-response-format, reconciliation R-2).

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: create accepts a declared custom key (happy path)

**Given** an initialised project with `.lore/custom-schemas/codex-frontmatter.yaml` adding optional `owner: {type: string, minLength: 1}`
**When** the user runs `lore codex create` for a new doc whose frontmatter includes `owner: alice` (with required `id`/`title`/`summary`)
**Then** exit code is `0`, the doc file is written, and `lore codex show <id>` returns it including `owner: alice` (FR-9).

#### Scenario 2: create rejects an undeclared key

**Given** the same overlay (declares `owner`)
**When** the user runs `lore codex create` for a doc whose frontmatter has `onwer: alice` (typo)
**Then** exit code is non-zero and stderr carries `Unknown property 'onwer' — allowed keys are id, title, summary, type, related, binds, rites, owner.` — `owner` appears among the allowed keys (FR-6).

#### Scenario 3: create with a collision overlay surfaces a clean ValueError

**Given** `.lore/custom-schemas/codex-frontmatter.yaml` declaring `title` (collision)
**When** the user runs `lore codex create` for any doc
**Then** exit code is non-zero and stderr carries the `OverlayError` text `... property 'title' collides with a packaged field and cannot be overridden`, with no Python traceback (FR-10).

### Unit Test Scenarios

- [ ] `codex.create_document(project_root=root, ...)`: with an overlay declaring `owner`, creating a doc with `owner` writes the file and returns normally (FR-9).
- [ ] `codex.create_document`: an undeclared key raises `ValueError` whose message contains `Unknown property 'onwer'` and lists `owner` among allowed.
- [ ] `codex.create_document`: a collision overlay raises `ValueError` carrying the `OverlayError` text (FR-10).
- [ ] `codex.update_document(project_root=root, ...)`: edits re-validate the merged frontmatter against the merged schema; a declared custom key persists (FR-9).
- [ ] `codex.create_document`: with no overlay present, create behaviour is unchanged (FR-2).

---

## Out of Scope

- The `validate_entity` keyword itself (US-3) and resolver internals (US-1, US-2).
- `lore health` wiring (US-4).
- The scaffolding skill (US-7).
- Any change to `delete_document` or non-write codex commands.

---

## References

- PRD: `lore codex show custom-codex-schemas-prd`
- Tech Spec: `lore codex show custom-codex-schemas-tech-spec`
- `lore codex show decisions-011-api-parity-with-cli` — create/edit via CLI ≡ `lore.api`
- `lore codex show tech-cli-entity-crud-matrix` — codex has only create/edit write paths

---

## Tech Notes

### Implementation Approach

- **Files to modify:**
  - `src/lore/codex.py` — at `create_document`'s call (`codex.py:151`) change `validate_entity(_DOC_TYPE_SCHEMAS[resolved_type], meta)` → `validate_entity(_DOC_TYPE_SCHEMAS[resolved_type], meta, project_root=project_root)`. At `update_document`'s call (`codex.py:222`) change `validate_entity(_DOC_TYPE_SCHEMAS[doc_type], merged)` → `validate_entity(_DOC_TYPE_SCHEMAS[doc_type], merged, project_root=project_root)`. `project_root` is already the first parameter of both (`codex.py:122`, `codex.py:194`). No change to the existing `ValueError("\n".join(...))` join — `OverlayError` is a `ValueError` and propagates ahead of that join. No CLI change (`codex` CLI already passes `project_root`).
- **Schema changes:** none.
- **Dependencies:** US-3 (`validate_entity` keyword).

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_custom_schema_overlay.py` | extend US-4 E2E file with create/edit scenarios |
| Unit | `tests/unit/test_codex_create_overlay.py` | NEW — create/update overlay validation |

### Test Stubs

```python
# E2E — create accepts declared custom key (Scenario 1, FR-9)
# Exercises: lore codex show conceptual-workflows-health (merged validator at write time)
def test_codex_create_accepts_custom_key(tmp_path):
    # Given: overlay adds owner; init project
    # When: CliRunner invoke ["codex", "create", ...] with owner: alice frontmatter
    # Then: exit 0; doc written; codex show returns owner alice (result.stdout)
    pass


# E2E — create rejects typo, owner listed allowed (Scenario 2, FR-6)
# Exercises: lore codex show conceptual-workflows-health
def test_codex_create_rejects_typo(tmp_path):
    # Given: overlay adds owner; frontmatter has onwer
    # When: invoke ["codex", "create", ...]
    # Then: exit non-zero; result.stderr has "Unknown property 'onwer'" and owner among allowed
    pass


# E2E — collision overlay -> clean ValueError text, no traceback (Scenario 3, FR-10)
# Exercises: lore codex show conceptual-workflows-health
def test_codex_create_collision_overlay_clean_error(tmp_path):
    # Given: overlay declares title (collision)
    # When: invoke ["codex", "create", ...]
    # Then: exit non-zero; stderr has collision message; no "Traceback" in output
    pass


# Unit — create_document accepts declared key (FR-9)
# Exercises: lore codex show conceptual-workflows-health
def test_create_document_accepts_custom_key(tmp_path):
    # Given: overlay adds owner
    # When: create_document(project_root, ... meta with owner)
    # Then: file written; no raise
    pass


# Unit — create_document rejects undeclared key
# Exercises: lore codex show conceptual-workflows-health
def test_create_document_rejects_undeclared(tmp_path):
    # Given: overlay adds owner; meta has onwer
    # When: create_document
    # Then: raises ValueError, message has "Unknown property 'onwer'", owner among allowed
    pass


# Unit — create_document collision overlay -> ValueError with OverlayError text (FR-10)
# Exercises: lore codex show conceptual-workflows-health
def test_create_document_collision_overlay_value_error(tmp_path):
    # Given: collision overlay
    # When: create_document
    # Then: raises ValueError carrying the OverlayError collision text
    pass


# Unit — update_document re-validates merged schema (FR-9)
# Exercises: lore codex show conceptual-workflows-health
def test_update_document_revalidates_custom_key(tmp_path):
    # Given: existing doc, overlay adds owner
    # When: update_document setting owner
    # Then: persists owner; declared key accepted
    pass


# Unit — no-overlay create unchanged (FR-2)
# Exercises: lore codex show conceptual-workflows-health
def test_create_document_no_overlay_unchanged(tmp_path):
    # Given: no .lore/custom-schemas/
    # When: create_document with a custom key
    # Then: raises Unknown property (pre-feature behaviour)
    pass
```

### Complexity Estimate

**S** — Two call-site keyword additions; `project_root` already in scope and the `ValueError` contract already absorbs `OverlayError`. Weight is in the E2E/unit coverage, not the change.

### Standards References

**Tester (Red):**
- `lore codex show decisions-006-no-seed-content-tests` — assert create/edit outcomes, not packaged byte content.
- Note for the Tester: Click CLI tested via `CliRunner` reading `result.stdout`/`result.stderr` separately (no `mix_stderr`).

**Implementer (Green):**
- `lore codex show decisions-011-api-parity-with-cli` — create/edit must accept what health accepts.
- `lore codex show tech-cli-entity-crud-matrix` — no new codex write path; only create/edit change.
