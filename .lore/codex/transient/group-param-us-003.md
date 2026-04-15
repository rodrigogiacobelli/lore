---
id: group-param-us-003
title: US-003 Watcher new --group nested create
summary: Lore user creates a watcher directly into a nested subdirectory via lore watcher new --group, with auto-mkdir, subtree duplicate detection, Python API parity via create_watcher group kwarg, and slash-joined group in both text and JSON output.
type: user-story
status: final
---

## Metadata

- **ID:** US-003
- **Status:** final
- **Epic:** Entity creation — --group parameter
- **Author:** Business Analyst
- **Date:** 2026-04-15
- **PRD:** `lore codex show group-param-prd`
- **Tech Spec:** `lore codex show group-param-tech-spec`

---

## Story

As a Realm orchestrator agent wiring a watcher under an existing feature area, I want to create a watcher directly inside `.lore/watchers/feature-implementation/` via a single `lore watcher new --group feature-implementation` command, so that watcher placement no longer requires hand-editing YAML on disk.

## Context

Fulfills PRD workflow "Create a nested watcher — AI orchestrator" and functional requirements FR-1, FR-2, FR-3, FR-6, FR-8. `watcher.create_watcher` already exists; this story adds the `group=None` kwarg to it and the `--group` option to the CLI. The target directory commonly pre-exists, so `mkdir(parents=True, exist_ok=True)` must be a no-op in that path.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Nested watcher create — target dir already exists

**Given** directory `.lore/watchers/feature-implementation/` already exists, no watcher named `on-prd-ready` exists anywhere under `.lore/watchers/`, and a source file `watcher.yaml` is present
**When** the user runs `lore watcher new on-prd-ready --group feature-implementation -f watcher.yaml`
**Then** stdout is exactly `Created watcher on-prd-ready (group: feature-implementation)`, file `.lore/watchers/feature-implementation/on-prd-ready.yaml` exists, and exit code is 0.

#### Scenario 2: Nested watcher create — JSON envelope

**Given** the same preconditions as Scenario 1
**When** the user runs `lore watcher new on-prd-ready --group feature-implementation -f watcher.yaml --json`
**Then** stdout parses as JSON whose `group` key equals `"feature-implementation"` and `path` key equals `".lore/watchers/feature-implementation/on-prd-ready.yaml"`, and exit code is 0.

#### Scenario 3: Nested watcher create — intermediate dirs auto-created

**Given** neither `.lore/watchers/team-a/` nor `.lore/watchers/team-a/triggers/` exists
**When** the user runs `lore watcher new nightly --group team-a/triggers -f w.yaml`
**Then** both intermediate directories are created, `.lore/watchers/team-a/triggers/nightly.yaml` exists, and exit code is 0.

#### Scenario 4: Root watcher create — --group omitted (unchanged)

**Given** no watcher named `root-watcher` exists
**When** the user runs `lore watcher new root-watcher -f w.yaml`
**Then** `.lore/watchers/root-watcher.yaml` exists directly under the watchers root and exit code is 0.

#### Scenario 5: Duplicate anywhere in subtree rejected

**Given** a watcher `nightly` exists at `.lore/watchers/team-b/nightly.yaml`
**When** the user runs `lore watcher new nightly --group team-a -f w.yaml`
**Then** stderr contains `Error: watcher 'nightly' already exists`, exit code is 1, and no file is created under `.lore/watchers/team-a/`.

### Unit Test Scenarios

- [ ] `lore.watcher.create_watcher`: accepts `group=None` keyword argument and writes flat (unchanged behaviour)
- [ ] `lore.watcher.create_watcher`: accepts `group="a/b"` and writes to `watchers_dir / "a" / "b" / "<name>.yaml"`
- [ ] `lore.watcher.create_watcher`: calls `mkdir(parents=True, exist_ok=True)` — pre-existing target dir does not raise
- [ ] `lore.watcher.create_watcher`: raises `ValueError` when same-named watcher exists anywhere under `watchers_dir`
- [ ] `lore.watcher.create_watcher`: return dict contains `"group"` and `"path"` keys
- [ ] `lore.watcher.create_watcher`: existing YAML-parse validation still runs (malformed watcher YAML still rejected after adding group support)
- [ ] `lore.watcher.update_watcher`: unchanged — edit does not move a watcher between groups

---

## Out of Scope

- Group validator implementation (covered by US-005)
- List display or filter grammar for watchers (covered by US-007, US-008)
- `edit --group` / rename vector for moving watchers
- Changes to the watcher YAML schema

---

## References

- PRD: `lore codex show group-param-prd`
- Tech Spec: `lore codex show group-param-tech-spec`
- Workflow: `lore codex show conceptual-workflows-watcher-crud`

---

## Tech Notes

### Implementation Approach

- `src/lore/watcher.py` `create_watcher` — extend signature to `create_watcher(watchers_dir: Path, name: str, content: str, *, group: str | None = None) -> dict`. Validation order: existing name regex check → `validate_group(group)` (raise `ValueError`) → empty content → YAML parse → subtree rglob duplicate (already present) → compute `target_dir = watchers_dir if group is None else watchers_dir / Path(group)` → `target_dir.mkdir(parents=True, exist_ok=True)` → write `target_dir / f"{name}.yaml"`. Return dict gains `"group": group` and `"path": str(target_dir / f"{name}.yaml")`. `update_watcher` is unchanged — edit never moves a watcher.
- `src/lore/cli.py` `watcher_new` (line ~2611) — add `@click.option("--group", default=None, ...)` and pass `group=group` into `create_watcher`. Success text: `Created watcher {name}` for root, `Created watcher {name} (group: {group})` for nested. JSON envelope returns the full result dict.

### Test File Locations

- Unit: `tests/unit/test_watcher.py` (existing) — add `TestCreateWatcherGroup` class.
- E2E: `tests/e2e/test_watcher_crud.py` (existing) — add nested-create scenarios.

### Test Stubs

```python
# tests/e2e/test_watcher_crud.py
# anchor: conceptual-workflows-watcher-crud

def test_watcher_new_nested_target_exists(runner, project_dir):
    # Scenario 1 — cites conceptual-workflows-watcher-crud (mkdir idempotent)
    (project_dir / ".lore/watchers/feature-implementation").mkdir(parents=True)
    (project_dir / "watcher.yaml").write_text("id: on-prd-ready\ntitle: T\n")
    result = runner.invoke(main, [
        "watcher", "new", "on-prd-ready",
        "--group", "feature-implementation", "-f", "watcher.yaml",
    ])
    assert result.exit_code == 0
    assert result.output.strip() == "Created watcher on-prd-ready (group: feature-implementation)"
    assert (project_dir / ".lore/watchers/feature-implementation/on-prd-ready.yaml").exists()

def test_watcher_new_nested_json_envelope(runner, project_dir):
    # Scenario 2 — cites conceptual-workflows-json-output
    (project_dir / "watcher.yaml").write_text("id: on-prd-ready\n")
    result = runner.invoke(main, [
        "watcher", "new", "on-prd-ready",
        "--group", "feature-implementation", "-f", "watcher.yaml", "--json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["group"] == "feature-implementation"
    assert data["path"] == ".lore/watchers/feature-implementation/on-prd-ready.yaml"

def test_watcher_new_deep_path_auto_mkdir(runner, project_dir):
    # Scenario 3 — cites conceptual-workflows-watcher-crud
    (project_dir / "w.yaml").write_text("id: nightly\n")
    result = runner.invoke(main, [
        "watcher", "new", "nightly", "--group", "team-a/triggers", "-f", "w.yaml",
    ])
    assert result.exit_code == 0
    assert (project_dir / ".lore/watchers/team-a/triggers/nightly.yaml").exists()

def test_watcher_new_root_unchanged(runner, project_dir):
    # Scenario 4 — cites conceptual-workflows-watcher-crud
    (project_dir / "w.yaml").write_text("id: root-watcher\n")
    result = runner.invoke(main, ["watcher", "new", "root-watcher", "-f", "w.yaml"])
    assert result.exit_code == 0
    assert (project_dir / ".lore/watchers/root-watcher.yaml").exists()

def test_watcher_new_duplicate_subtree_rejected(runner, project_dir):
    # Scenario 5 — cites conceptual-workflows-watcher-crud (rglob duplicate)
    (project_dir / ".lore/watchers/team-b").mkdir(parents=True)
    (project_dir / ".lore/watchers/team-b/nightly.yaml").write_text("id: nightly\n")
    (project_dir / "w.yaml").write_text("id: nightly\n")
    result = runner.invoke(main, ["watcher", "new", "nightly", "--group", "team-a", "-f", "w.yaml"])
    assert result.exit_code == 1
    assert "already exists" in result.stderr
    assert not (project_dir / ".lore/watchers/team-a").exists()
```

```python
# tests/unit/test_watcher.py
# anchor: conceptual-workflows-watcher-crud

def test_create_watcher_group_none_flat(tmp_path):
    # AC unit: group=None flat write (unchanged)
    create_watcher(tmp_path, "w", "id: w\n")
    assert (tmp_path / "w.yaml").exists()

def test_create_watcher_group_nested(tmp_path):
    # AC unit: nested write to a/b
    create_watcher(tmp_path, "w", "id: w\n", group="a/b")
    assert (tmp_path / "a/b/w.yaml").exists()

def test_create_watcher_mkdir_idempotent(tmp_path):
    # AC unit: pre-existing dir does not error
    (tmp_path / "a/b").mkdir(parents=True)
    create_watcher(tmp_path, "w", "id: w\n", group="a/b")
    assert (tmp_path / "a/b/w.yaml").exists()

def test_create_watcher_duplicate_subtree_raises(tmp_path):
    # AC unit: rglob duplicate regardless of group
    (tmp_path / "x").mkdir()
    (tmp_path / "x/w.yaml").write_text("id: w\n")
    with pytest.raises(ValueError, match="already exists"):
        create_watcher(tmp_path, "w", "id: w\n", group="y")

def test_create_watcher_return_dict_keys(tmp_path):
    # AC unit: return dict carries group and path
    result = create_watcher(tmp_path, "w", "id: w\n", group="a")
    assert result["group"] == "a"
    assert result["path"].endswith("a/w.yaml")

def test_create_watcher_yaml_validation_still_runs(tmp_path):
    # AC unit: malformed YAML still rejected when group provided
    with pytest.raises(ValueError, match="Invalid YAML"):
        create_watcher(tmp_path, "w", "::not yaml::", group="a")

def test_update_watcher_unchanged(tmp_path):
    # AC unit: update does not move between groups
    (tmp_path / "a").mkdir()
    (tmp_path / "a/w.yaml").write_text("id: w\n")
    update_watcher(tmp_path, "w", "id: w\nupdated: true\n")
    assert (tmp_path / "a/w.yaml").read_text().endswith("updated: true\n")
    assert not (tmp_path / "w.yaml").exists()
```

### Complexity Estimate

**S** — signature extension on an existing helper, one new CLI option, five E2E scenarios that reuse existing fixtures, seven unit cases. Lower complexity than US-002 because no extraction or new file is needed.
