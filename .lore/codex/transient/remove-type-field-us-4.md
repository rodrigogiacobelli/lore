---
id: remove-type-field-us-4
type: user-story
title: "US-4: Remove type from Python models"
summary: As a Realm developer, I want the Artifact and CodexDocument dataclasses to have no type field, so that the public API contract is clean and downstream code is not surprised by a stale attribute.
status: draft
---

## Metadata

- **ID:** US-4
- **Status:** final
- **Epic:** Public API Contract Change
- **Author:** Business Analyst
- **Date:** 2026-03-27
- **PRD:** `lore codex show remove-type-field-prd`
- **Tech Spec:** `lore codex show remove-type-field-tech-spec`

---

## Story

As a Realm developer consuming `from lore.models import Artifact, CodexDocument`, I want neither dataclass to have a `type` field, so that accessing `artifact.type` or `doc.type` raises `AttributeError` immediately — making the contract break visible and actionable rather than silent.

## Context

The PRD (FR-12 through FR-15) requires removing `type: str` from `Artifact` and `CodexDocument` dataclasses in `models.py` and updating their `from_dict` classmethods. `Dependency.type` and `DoctrineStep.type` are unrelated and must not be touched. This is the breaking API change documented in CHANGELOG. This story covers PRD Workflow WF-4: Realm constructs `Artifact` objects from `scan_artifacts()` results and must no longer pass or read a `type` key.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Artifact.from_dict succeeds without type key

**Given** a Python environment with `lore` installed
**When** a caller runs:
```python
from lore.models import Artifact
a = Artifact.from_dict({"id": "x", "title": "X", "summary": "s", "group": "g", "body": ""})
```
**Then** no exception is raised; `a.id == "x"`, `a.title == "X"`, `a.summary == "s"`, `a.group == "g"`

#### Scenario 2: Accessing artifact.type raises AttributeError

**Given** an `Artifact` instance created via `Artifact.from_dict` with a valid dict (no `type` key)
**When** a caller accesses `artifact.type`
**Then** `AttributeError` is raised

#### Scenario 3: CodexDocument.from_dict succeeds without type key

**Given** a Python environment with `lore` installed
**When** a caller runs:
```python
from lore.models import CodexDocument
doc = CodexDocument.from_dict({"id": "y", "title": "Y", "summary": "s"})
```
**Then** no exception is raised; `doc.id == "y"`, `doc.title == "Y"`

#### Scenario 4: Accessing doc.type raises AttributeError

**Given** a `CodexDocument` instance created via `CodexDocument.from_dict`
**When** a caller accesses `doc.type`
**Then** `AttributeError` is raised

#### Scenario 5: scan_artifacts results hydrate into Artifact objects cleanly

**Given** a project with artifact templates
**When** a caller runs:
```python
from lore.artifact import scan_artifacts
from lore.models import Artifact
results = scan_artifacts()
artifacts = [Artifact.from_dict(d) for d in results]
```
**Then** no `AttributeError` or `KeyError` is raised; each `Artifact` object has `id`, `group`, `title`, `summary` attributes and no `type` attribute

### Unit Test Scenarios

- [ ] `models.Artifact`: dataclass has no `type` field — `hasattr(Artifact, "type")` is `False` at class level
- [ ] `models.Artifact.from_dict`: succeeds with dict `{"id": "x", "title": "X", "summary": "s", "group": "g", "body": ""}` (no `type` key)
- [ ] `models.Artifact`: accessing `artifact.type` raises `AttributeError`
- [ ] `models.Artifact`: still frozen (immutable) — assigning any field raises `FrozenInstanceError`
- [ ] `models.CodexDocument`: dataclass has no `type` field — `hasattr(CodexDocument, "type")` is `False` at class level
- [ ] `models.CodexDocument.from_dict`: succeeds with dict `{"id": "y", "title": "Y", "summary": "s"}` (no `type` key)
- [ ] `models.CodexDocument`: accessing `doc.type` raises `AttributeError`
- [ ] `models.Dependency`: `Dependency.type` field is unchanged — still present
- [ ] `models.DoctrineStep`: `DoctrineStep.type` field is unchanged — still present

---

## Out of Scope

- Realm updates to remove access to `artifact.type` — that is Realm's responsibility in a coordinated release
- `Dependency.type` or `DoctrineStep.type` changes — explicitly out of scope per PRD
- CHANGELOG authoring — covered separately (FR-23)

---

## References

- PRD: `lore codex show remove-type-field-prd` (FR-12, FR-13, FR-14, FR-15; WF-4)
- Tech Spec: `lore codex show remove-type-field-tech-spec`
- `lore codex show standards-public-api-stability`

---

## Tech Notes

_(Filled by Tech Lead in tech-notes-draft and tech-notes-final phases — BA must not edit this section)_

### Implementation Approach

- **Files to create:** None
- **Files to modify:**
  - `src/lore/models.py` — Remove `type: str` field from `Artifact` dataclass (line 157); update `Artifact.from_dict` to remove `type=d["type"]` (line 166); remove `type: str` field from `CodexDocument` dataclass (line 181); update `CodexDocument.from_dict` to remove `type=d["type"]` (line 189). Do NOT touch `Dependency.type` (line 110) or `DoctrineStep.type` (line 205).
- **Schema changes:** None — `Dependency.type` is a DB column and is out of scope (see `tech-db-schema`)
- **Dependencies:** US-3 should be complete so `scan_artifacts()` already omits `"type"` from returned dicts before `Artifact.from_dict` is updated

**TDD cycle:** Red mission (write failing tests in `test_models.py` and `test_python_api.py`) → Green mission (update `models.py`) → Commit mission

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_python_api.py` | scan_artifacts + Artifact.from_dict; CodexDocument hydration |
| Unit | `tests/unit/test_models.py` | Artifact and CodexDocument dataclass field assertions |

### Test Stubs

```python
# =============================================================================
# tests/e2e/test_python_api.py — new stubs for US-4
# =============================================================================

# E2E Scenario 1+2: Artifact.from_dict succeeds without type key; .type raises AttributeError
# conceptual-workflows-python-api step: Realm hydrates Artifact from scan_artifacts dict
def test_artifact_from_dict_no_type_key_succeeds(project_dir):
    # Given: Artifact.from_dict({"id":"x","title":"X","summary":"s","group":"g","body":""})
    # When: called without "type" key
    # Then: no exception; a.id=="x"; a.title=="X"; a.summary=="s"; a.group=="g"
    pass


def test_artifact_from_dict_accessing_type_raises_attribute_error(project_dir):
    # Given: Artifact instance from Artifact.from_dict(...) with no type key
    # When: artifact.type
    # Then: AttributeError raised
    pass


# E2E Scenario 3+4: CodexDocument.from_dict succeeds without type key; .type raises AttributeError
# conceptual-workflows-python-api step: Realm hydrates CodexDocument from scan_codex dict
def test_codex_document_from_dict_no_type_key_succeeds(project_dir):
    # Given: CodexDocument.from_dict({"id":"y","title":"Y","summary":"s"})
    # When: called without "type" key
    # Then: no exception; doc.id=="y"; doc.title=="Y"
    pass


def test_codex_document_from_dict_accessing_type_raises_attribute_error(project_dir):
    # Given: CodexDocument instance from CodexDocument.from_dict(...)
    # When: doc.type
    # Then: AttributeError raised
    pass


# E2E Scenario 5: scan_artifacts results hydrate into Artifact objects cleanly
# conceptual-workflows-python-api step: Realm iterates scan_artifacts and constructs Artifact objects
def test_scan_artifacts_hydrate_to_artifact_objects_no_type(project_dir):
    # Given: project with artifact templates (from lore init)
    # When: scan_artifacts() → [Artifact.from_dict(d) for d in results]
    # Then: no AttributeError or KeyError; each Artifact has id/group/title/summary; no type attr
    pass


# =============================================================================
# tests/unit/test_models.py — new/updated stubs for US-4
# =============================================================================

# Unit: Artifact dataclass has no type field
# remove-type-field-us-4 Unit Test Scenarios — Artifact has no type field
def test_artifact_dataclass_has_no_type_field():
    # assert "type" not in Artifact.__dataclass_fields__
    from lore.models import Artifact
    assert "type" not in Artifact.__dataclass_fields__


# Unit: Artifact.from_dict succeeds without type key
# remove-type-field-us-4 Unit Test Scenarios — Artifact.from_dict no type key
def test_artifact_from_dict_no_type_key():
    from lore.models import Artifact
    # Given: {"id":"x","title":"X","summary":"s","group":"g","body":""}
    # When: Artifact.from_dict(d)
    # Then: no exception
    pass


# Unit: accessing artifact.type raises AttributeError
# remove-type-field-us-4 Unit Test Scenarios — artifact.type raises AttributeError
def test_artifact_type_attribute_raises_attribute_error():
    from lore.models import Artifact
    import pytest
    a = Artifact.from_dict({"id": "x", "title": "X", "summary": "s", "group": "g", "body": ""})
    with pytest.raises(AttributeError):
        _ = a.type


# Unit: Artifact is still frozen (immutable)
# remove-type-field-us-4 Unit Test Scenarios — Artifact is still frozen
def test_artifact_is_frozen():
    from lore.models import Artifact
    import dataclasses
    import pytest
    a = Artifact.from_dict({"id": "x", "title": "X", "summary": "s", "group": "g", "body": ""})
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.id = "y"


# Unit: CodexDocument dataclass has no type field
# remove-type-field-us-4 Unit Test Scenarios — CodexDocument has no type field
def test_codex_document_dataclass_has_no_type_field():
    from lore.models import CodexDocument
    assert "type" not in CodexDocument.__dataclass_fields__


# Unit: CodexDocument.from_dict succeeds without type key
# remove-type-field-us-4 Unit Test Scenarios — CodexDocument.from_dict no type key
def test_codex_document_from_dict_no_type_key():
    from lore.models import CodexDocument
    # Given: {"id":"y","title":"Y","summary":"s"}
    # When: CodexDocument.from_dict(d)
    # Then: no exception
    pass


# Unit: accessing doc.type raises AttributeError
# remove-type-field-us-4 Unit Test Scenarios — doc.type raises AttributeError
def test_codex_document_type_attribute_raises_attribute_error():
    from lore.models import CodexDocument
    import pytest
    doc = CodexDocument.from_dict({"id": "y", "title": "Y", "summary": "s"})
    with pytest.raises(AttributeError):
        _ = doc.type


# Unit: Dependency.type field is unchanged
# remove-type-field-us-4 Unit Test Scenarios — Dependency.type unchanged
def test_dependency_type_field_unchanged():
    from lore.models import Dependency
    assert "type" in Dependency.__dataclass_fields__


# Unit: DoctrineStep.type field is unchanged
# remove-type-field-us-4 Unit Test Scenarios — DoctrineStep.type unchanged
def test_doctrine_step_type_field_unchanged():
    from lore.models import DoctrineStep
    assert "type" in DoctrineStep.__dataclass_fields__
```

### Complexity Estimate

S — Two dataclasses (`Artifact`, `CodexDocument`), surgical field removal. The breaking change notice (CHANGELOG) is the hardest part. Nine unit stubs plus five E2E stubs, but each is a one-liner assertion.
