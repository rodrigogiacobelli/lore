---
id: group-param-us-002
title: US-002 Knight new --group nested create and create_knight extraction
summary: Lore user creates a knight directly into a nested subdirectory via lore knight new --group, backed by a new lore.knight.create_knight function that receives the group kwarg and replaces the currently-inline create logic in cli.py.
type: user-story
status: final
---

## Metadata

- **ID:** US-002
- **Status:** final
- **Epic:** Entity creation — --group parameter
- **Author:** Business Analyst
- **Date:** 2026-04-15
- **PRD:** `lore codex show group-param-prd`
- **Tech Spec:** `lore codex show group-param-tech-spec`

---

## Story

As a Realm orchestrator agent or human developer, I want to create a knight persona directly at the entity root or inside a nested subdirectory of `.lore/knights/` via a single `lore knight new` command, so that knight creation matches the `--group` behaviour of sibling entities and the Python API exposes `create_knight` at parity with `create_doctrine`.

## Context

Fulfills PRD workflows "Create a knight at the entity root — human developer" and the knight leg of "Create a nested doctrine — AI orchestrator", and functional requirements FR-1, FR-2, FR-3, FR-6, FR-8, FR-9. Today the knight create logic is inlined in `cli.knight_new` and there is no `create_knight` in `lore/knight.py`, violating ADR-011 (API parity) and preventing Realm from creating knights through `lore.models`. This story extracts the logic into a core helper and adds `--group` in the same change.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Root knight create — unchanged behaviour

**Given** a project with no knight named `reviewer`, and a persona file `reviewer.md` in the working directory
**When** the user runs `lore knight new reviewer --from reviewer.md`
**Then** stdout is exactly `Created knight reviewer`, file `.lore/knights/reviewer.md` exists directly under the knights root, and exit code is 0.

#### Scenario 2: Root knight create — JSON envelope, root group is null

**Given** the same preconditions as Scenario 1
**When** the user runs `lore knight new reviewer --from reviewer.md --json`
**Then** stdout parses as JSON equal to `{"name": "reviewer", "group": null, "filename": "reviewer.md"}` and exit code is 0.

#### Scenario 3: Nested knight create — happy path

**Given** no knight named `on-prd-ready` exists anywhere under `.lore/knights/`, and persona file `persona.md` is present
**When** the user runs `lore knight new on-prd-ready --group feature-implementation --from persona.md`
**Then** stdout is exactly `Created knight on-prd-ready (group: feature-implementation)`, file `.lore/knights/feature-implementation/on-prd-ready.md` exists, and exit code is 0.

#### Scenario 4: Nested knight — deep path auto-mkdir

**Given** neither `.lore/knights/team-a/` nor `.lore/knights/team-a/reviewers/` exists
**When** the user runs `lore knight new lead --group team-a/reviewers --from p.md`
**Then** both intermediate directories are created, `.lore/knights/team-a/reviewers/lead.md` exists, and exit code is 0.

#### Scenario 5: Duplicate name anywhere in subtree rejected

**Given** a knight `reviewer` exists at `.lore/knights/team-a/reviewer.md`
**When** the user runs `lore knight new reviewer --group team-b --from p.md`
**Then** stderr contains `Error: knight 'reviewer' already exists`, exit code is 1, and no file is created under `.lore/knights/team-b/`.

### Unit Test Scenarios

- [ ] `lore.knight.create_knight`: function exists with signature `(knights_dir, name, content, *, group=None) -> dict`
- [ ] `lore.knight.create_knight`: `group=None` writes to `knights_dir / "<name>.md"`
- [ ] `lore.knight.create_knight`: `group="a/b"` writes to `knights_dir / "a" / "b" / "<name>.md"` with intermediate directories auto-created
- [ ] `lore.knight.create_knight`: idempotent mkdir — pre-existing target dir does not raise
- [ ] `lore.knight.create_knight`: raises `ValueError` when same name exists anywhere under `knights_dir` via rglob, regardless of `group`
- [ ] `lore.knight.create_knight`: returns dict containing `name`, `group`, `filename`, `path` keys
- [ ] `lore.knight.create_knight`: raises `ValueError` when `validate_group` rejects the input, before any filesystem write
- [ ] `lore.cli.knight_new` thin-wrapper smoke: with `create_knight` monkeypatched, assert the handler calls it with the `group` kwarg equal to the parsed `--group` value and performs no validation or mkdir of its own

---

## Out of Scope

- Group validator implementation (covered by US-005)
- List display or filter grammar for knights (covered by US-007, US-008)
- Editing or moving an existing knight between groups
- Changes to the knight markdown format

---

## References

- PRD: `lore codex show group-param-prd`
- Tech Spec: `lore codex show group-param-tech-spec`
- Workflow: `lore codex show conceptual-workflows-knight-crud`
- ADR: `lore codex show decisions-011-api-parity-with-cli`

---

## Tech Notes

### Implementation Approach

- `src/lore/knight.py` — add new `create_knight(knights_dir: Path, name: str, content: str, *, group: str | None = None) -> dict`. Validation order: `validate_name(name)` → `validate_group(group)` (raise `ValueError` on failure) → non-empty content check → subtree-wide duplicate via `knights_dir.rglob(f"{name}.md")` (raise `ValueError('Knight "..." already exists.')`) → compute `target_dir = knights_dir if group is None else knights_dir / Path(group)` → `target_dir.mkdir(parents=True, exist_ok=True)` → write `target_dir / f"{name}.md"`. Return `{"name": name, "group": group, "filename": f"{name}.md", "path": str(target_dir / f"{name}.md")}`. Preserve existing `find_knight` path-traversal guard — names stay separate from groups.
- `src/lore/cli.py` `knight_new` (line ~1015) — collapse body into a thin wrapper: read content from `--from` or stdin, call `create_knight(knights_dir, name, content, group=group)` inside `try/except ValueError`, format output. Remove the inline duplicate check and inline `knights_dir.mkdir` from `cli.py`. Add Click option `--group`. Success text: `Created knight {name}` for root, `Created knight {name} (group: {group})` for nested. JSON envelope returns the full result dict; `group` is `None` when omitted.

### Test File Locations

- Unit: `tests/unit/test_knight.py` (existing) — add `TestCreateKnight` class.
- E2E: `tests/e2e/test_knight_crud.py` (new file — no current e2e for knight create). Follows `test_watcher_crud.py` conventions.

### Test Stubs

```python
# tests/e2e/test_knight_crud.py — new file
"""anchor: conceptual-workflows-knight-crud"""

def test_knight_new_root_unchanged(runner, project_dir):
    # Scenario 1 — cites conceptual-workflows-knight-crud
    (project_dir / "reviewer.md").write_text("---\nid: reviewer\n---\n# R\n")
    result = runner.invoke(main, ["knight", "new", "reviewer", "--from", "reviewer.md"])
    assert result.exit_code == 0
    assert result.output.strip() == "Created knight reviewer"
    assert (project_dir / ".lore/knights/reviewer.md").exists()

def test_knight_new_root_json_null_group(runner, project_dir):
    # Scenario 2 — cites conceptual-workflows-json-output
    (project_dir / "reviewer.md").write_text("---\nid: reviewer\n---\n")
    result = runner.invoke(main, ["knight", "new", "reviewer", "--from", "reviewer.md", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"name": "reviewer", "group": None, "filename": "reviewer.md"}

def test_knight_new_nested_happy_path(runner, project_dir):
    # Scenario 3 — cites conceptual-workflows-knight-crud
    (project_dir / "persona.md").write_text("---\nid: on-prd-ready\n---\n")
    result = runner.invoke(main, [
        "knight", "new", "on-prd-ready",
        "--group", "feature-implementation",
        "--from", "persona.md",
    ])
    assert result.exit_code == 0
    assert result.output.strip() == "Created knight on-prd-ready (group: feature-implementation)"
    assert (project_dir / ".lore/knights/feature-implementation/on-prd-ready.md").exists()

def test_knight_new_deep_path_auto_mkdir(runner, project_dir):
    # Scenario 4 — cites conceptual-workflows-knight-crud (mkdir parents=True)
    (project_dir / "p.md").write_text("---\nid: lead\n---\n")
    result = runner.invoke(main, [
        "knight", "new", "lead", "--group", "team-a/reviewers", "--from", "p.md",
    ])
    assert result.exit_code == 0
    assert (project_dir / ".lore/knights/team-a/reviewers/lead.md").exists()

def test_knight_new_duplicate_subtree_rejected(runner, project_dir):
    # Scenario 5 — cites conceptual-workflows-knight-crud (rglob duplicate)
    (project_dir / ".lore/knights/team-a").mkdir(parents=True)
    (project_dir / ".lore/knights/team-a/reviewer.md").write_text("---\nid: reviewer\n---\n")
    (project_dir / "p.md").write_text("---\nid: reviewer\n---\n")
    result = runner.invoke(main, ["knight", "new", "reviewer", "--group", "team-b", "--from", "p.md"])
    assert result.exit_code == 1
    assert "already exists" in result.stderr
    assert not (project_dir / ".lore/knights/team-b").exists()
```

```python
# tests/unit/test_knight.py
# anchor: conceptual-workflows-knight-crud

def test_create_knight_signature_exists():
    # AC unit: function with kwarg-only group signature
    import inspect
    sig = inspect.signature(create_knight)
    assert "group" in sig.parameters
    assert sig.parameters["group"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["group"].default is None

def test_create_knight_root_write(tmp_path):
    # AC unit: group=None writes flat
    create_knight(tmp_path, "reviewer", "---\nid: reviewer\n---\n")
    assert (tmp_path / "reviewer.md").exists()

def test_create_knight_nested_write_auto_mkdir(tmp_path):
    # AC unit: nested write + auto mkdir
    create_knight(tmp_path, "lead", "---\nid: lead\n---\n", group="a/b")
    assert (tmp_path / "a/b/lead.md").exists()

def test_create_knight_mkdir_idempotent(tmp_path):
    # AC unit: pre-existing dir ok
    (tmp_path / "a").mkdir()
    create_knight(tmp_path, "k", "c", group="a")
    assert (tmp_path / "a/k.md").exists()

def test_create_knight_duplicate_subtree_raises(tmp_path):
    # AC unit: rglob duplicate regardless of group
    (tmp_path / "x").mkdir()
    (tmp_path / "x/k.md").write_text("---\nid: k\n---\n")
    with pytest.raises(ValueError, match="already exists"):
        create_knight(tmp_path, "k", "c", group="y")

def test_create_knight_return_dict_keys(tmp_path):
    # AC unit: return dict contract
    result = create_knight(tmp_path, "k", "---\nid: k\n---\n", group="a")
    assert set(result.keys()) >= {"name", "group", "filename", "path"}
    assert result["group"] == "a"

def test_create_knight_invalid_group_raises_before_write(tmp_path):
    # AC unit: validate_group failure raises before write
    with pytest.raises(ValueError, match="invalid group"):
        create_knight(tmp_path, "k", "c", group="..")
    assert not any(tmp_path.rglob("*.md"))

def test_cli_knight_new_thin_wrapper_smoke(monkeypatch, runner, project_dir):
    # AC unit: CLI handler calls create_knight with group kwarg, no local validation
    # anchor: decisions-011-api-parity-with-cli
    captured = {}
    def fake_create_knight(knights_dir, name, content, *, group=None):
        captured["group"] = group
        return {"name": name, "group": group, "filename": f"{name}.md", "path": "x"}
    monkeypatch.setattr("lore.knight.create_knight", fake_create_knight)
    (project_dir / "p.md").write_text("---\nid: k\n---\n")
    result = runner.invoke(main, ["knight", "new", "k", "--group", "a/b", "--from", "p.md"])
    assert result.exit_code == 0
    assert captured["group"] == "a/b"
```

### Complexity Estimate

**M** — new `create_knight` helper, non-trivial extraction from `cli.knight_new` body, new E2E test file, full unit matrix plus thin-wrapper smoke test.
