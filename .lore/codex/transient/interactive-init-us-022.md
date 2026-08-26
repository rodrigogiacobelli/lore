---
id: interactive-init-us-022
title: US-022 — The init status message reports the real schema version
summary: init._format_db_status stops printing a hardcoded "schema version 1" and
  reads lore.db.SCHEMA_VERSION, so the line a human sees after lore init matches the
  database that was actually created.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- conceptual-workflows-lore-init
- conceptual-workflows-schema-migrations
---

# US-022 — The init status message reports the real schema version

## Metadata

- **ID:** US-022
- **Status:** final
- **Epic:** _Adjacent Corrections_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a developer running `lore init`_, I want _the status line to name the schema version the database actually carries_, so that _the first thing Lore tells me about my project is true_.

## Context

FR-38 is a one-line correction with a stale-by-construction cause. `_format_db_status` at `src/lore/init.py:233` returns `"  Created lore.db (schema version 1)"` as a literal; `lore.db.SCHEMA_VERSION` at `src/lore/db.py:13` is `6`. Five migrations have shipped since the literal was written and none of them touched the message, because nothing connected the two.

The fix removes the class of bug rather than this one instance: the message interpolates the constant, so the next migration updates it for free. The test asserts against `lore.db.SCHEMA_VERSION` rather than against a literal, for the same reason (Tech Spec §14.1).

`init.py` already imports from `lore.db` — `from lore.db import init_database` at `src/lore/init.py:7` — so the import is a one-name extension, not a new dependency.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: The created-database line names the current schema version

**Given** an empty project directory
**When** the caller runs `lore init --yes`
**Then** stdout carries the line `  Created lore.db (schema version 6)` — asserted against `lore.db.SCHEMA_VERSION`, not against the literal `6`, so a future migration does not break the test

#### Scenario 2: The other two status branches are unchanged

**Given** a project that already has a `lore.db`, and separately one whose `lore.db` is corrupt
**When** the caller runs `lore init --yes` in each
**Then** the first prints `  Skipped lore.db (already exists)` and the second prints `  Warning: Existing database appears corrupted. Reinitialized lore.db`, both byte-identical to their pre-feature text

### Unit Test Scenarios

- [ ] `lore.init._format_db_status`: `"created"` returns a single message ending `(schema version {db.SCHEMA_VERSION})`
- [ ] `lore.init._format_db_status`: the returned string contains no hardcoded digit — asserted by building the expected string from the constant and comparing
- [ ] `lore.init._format_db_status`: `"existing"` and `"reinitialized"` return their pre-feature messages unchanged
- [ ] `lore.init._format_db_status`: an unknown status still returns an empty list (the silent-fallthrough behaviour the docstring documents)
- [ ] `lore.init`: `SCHEMA_VERSION` is imported from `lore.db` at module level, not read through a second constant

---

## Out of Scope

- Any change to `SCHEMA_VERSION` itself or to the migration machinery.
- The `conceptual-workflows-schema-migrations` doc, which is correct as written.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-38
- Tech Spec: `lore codex show interactive-init-tech-spec` §11, §14.1
- `lore codex show conceptual-workflows-lore-init`
- `lore codex show conceptual-workflows-schema-migrations`

---

## Tech Notes

### Implementation Approach

- **Files to modify:** `src/lore/init.py`
  - Line 7: `from lore.db import init_database` becomes `from lore.db import SCHEMA_VERSION, init_database`.
  - Line 241 (inside `_format_db_status`, which begins at `src/lore/init.py:233`): `return ["  Created lore.db (schema version 1)"]` becomes `return [f"  Created lore.db (schema version {SCHEMA_VERSION})"]`.
- **Files to create:** none.
- **Schema changes:** none — `SCHEMA_VERSION` stays 6; this feature adds no table, no column and no migration.
- **Dependencies:** none. This story is independent of every other story in the feature and can be batched anywhere.

Existing tests that assert the literal string will fail and must be updated to build the expectation from the constant. The implementer should grep for `schema version 1` across `tests/` before starting.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_lore_init.py` — extended | Anchor `conceptual-workflows-lore-init` |
| Unit | `tests/unit/test_lore_init.py` — extended | `_format_db_status`'s three branches |

### Test Stubs

```python
# E2E — Scenario 1: The created-database line names the current schema version
# Exercises: lore codex show conceptual-workflows-lore-init — database creation
def test_init_reports_the_current_schema_version(tmp_path, runner):
    # Given: an empty directory
    # When: lore init --yes
    # Then: stdout contains f"  Created lore.db (schema version {db.SCHEMA_VERSION})"
    pass


# E2E — Scenario 2: The other two status branches are unchanged
# Exercises: lore codex show conceptual-workflows-lore-init — database creation
def test_existing_and_corrupt_database_messages_unchanged(project_dir, runner):
    pass


# Unit — created branch interpolates the constant
# Exercises: lore codex show conceptual-workflows-lore-init — database creation
def test_format_db_status_created_uses_schema_version_constant():
    pass


# Unit — no hardcoded digit
# Exercises: lore codex show conceptual-workflows-lore-init — database creation
def test_format_db_status_has_no_hardcoded_version():
    pass


# Unit — the other branches
# Exercises: lore codex show conceptual-workflows-lore-init — database creation
def test_format_db_status_existing_and_reinitialized_unchanged():
    pass


# Unit — unknown status falls through silently
# Exercises: lore codex show conceptual-workflows-lore-init — database creation
def test_format_db_status_unknown_returns_empty_list():
    pass
```

### Complexity Estimate

**S** — a two-line change plus a grep for existing literal assertions; fully independent of the rest of the feature.

### Standards References

- `lore codex show standards-dry` — the constant is the one record of the schema version
- `lore codex show technical-test-guidelines`
