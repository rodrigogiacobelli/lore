---
id: group-param-us-001
title: US-001 Doctrine new --group nested create
summary: Lore user creates a doctrine directly into a nested subdirectory under .lore/doctrines via a single lore doctrine new --group command, with auto-mkdir, subtree duplicate detection, and slash-joined group in both text and JSON output.
type: user-story
status: final
---

## Metadata

- **ID:** US-001
- **Status:** final
- **Epic:** Entity creation — --group parameter
- **Author:** Business Analyst
- **Date:** 2026-04-15
- **PRD:** `lore codex show group-param-prd`
- **Tech Spec:** `lore codex show group-param-tech-spec`

---

## Story

As a Realm orchestrator agent organising a growing `seo-analysis` feature area, I want to create a doctrine directly into an arbitrarily nested subdirectory under `.lore/doctrines/` with one command, so that I never have to hand-edit files or bypass validation and duplicate detection.

## Context

Fulfills PRD workflow "Create a nested doctrine — AI orchestrator" and functional requirements FR-1, FR-2, FR-3, FR-6. Today `lore doctrine new` writes flat under `.lore/doctrines/`; the only way to place a doctrine in a nested subdirectory is to hand-edit files, which skips name validation, duplicate detection, and the Python API. This story restores symmetry between `lore init`'s seeded layout and create-time placement.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Nested doctrine create — happy path

**Given** a project with no existing doctrine named `keyword-ranker` anywhere under `.lore/doctrines/`, and source files `ranker.yaml` and `ranker.design.md` in the working directory
**When** the user runs `lore doctrine new keyword-ranker --group seo-analysis/keyword-analysers -f ranker.yaml -d ranker.design.md`
**Then** stdout contains exactly `Created doctrine keyword-ranker (group: seo-analysis/keyword-analysers)`, exit code is 0, files `.lore/doctrines/seo-analysis/keyword-analysers/keyword-ranker.yaml` and `.lore/doctrines/seo-analysis/keyword-analysers/keyword-ranker.design.md` exist on disk, and intermediate directories `seo-analysis/` and `seo-analysis/keyword-analysers/` were auto-created.

#### Scenario 2: Nested doctrine create — JSON envelope

**Given** the same preconditions as Scenario 1
**When** the user runs `lore doctrine new keyword-ranker --group seo-analysis/keyword-analysers -f ranker.yaml -d ranker.design.md --json`
**Then** stdout parses as JSON equal to `{"name": "keyword-ranker", "group": "seo-analysis/keyword-analysers", "yaml_filename": "keyword-ranker.yaml", "design_filename": "keyword-ranker.design.md", "path": ".lore/doctrines/seo-analysis/keyword-analysers/keyword-ranker.yaml"}` and exit code is 0.

#### Scenario 3: Root doctrine create — --group omitted (unchanged behaviour)

**Given** no doctrine named `flat-doctrine` exists, and source files are present
**When** the user runs `lore doctrine new flat-doctrine -f flat.yaml -d flat.design.md`
**Then** stdout is exactly `Created doctrine flat-doctrine`, file `.lore/doctrines/flat-doctrine.yaml` exists directly under the doctrines root, and exit code is 0.

#### Scenario 4: Duplicate name anywhere in subtree rejected

**Given** a doctrine `ranker` already exists at `.lore/doctrines/seo-analysis/ranker.yaml`
**When** the user runs `lore doctrine new ranker --group other-feature -f ranker.yaml -d ranker.design.md`
**Then** stderr contains `Error: doctrine 'ranker' already exists at .lore/doctrines/seo-analysis/ranker.yaml`, exit code is 1, and no file is created under `.lore/doctrines/other-feature/`.

#### Scenario 5: mkdir idempotent when target dir already exists

**Given** directory `.lore/doctrines/existing-group/` already exists on disk
**When** the user runs `lore doctrine new new-doc --group existing-group -f d.yaml -d d.design.md`
**Then** exit code is 0 and files are created inside the existing directory without error.

### Unit Test Scenarios

- [ ] `lore.doctrine.create_doctrine`: accepts `group=None` and writes to `doctrines_dir / "<name>.yaml"` (flat path unchanged)
- [ ] `lore.doctrine.create_doctrine`: accepts `group="a/b/c"` and writes to `doctrines_dir / "a" / "b" / "c" / "<name>.yaml"`
- [ ] `lore.doctrine.create_doctrine`: calls `mkdir(parents=True, exist_ok=True)` before writing — asserted via a pre-existing nested directory passing without error
- [ ] `lore.doctrine.create_doctrine`: raises `DoctrineError` with message mentioning existing path when a same-named doctrine exists anywhere under `doctrines_dir` (rglob scope), regardless of supplied `group`
- [ ] `lore.doctrine.create_doctrine`: return dict contains `"group"` key equal to the supplied value and `"path"` key equal to the written yaml path as a string
- [ ] `lore.doctrine.create_doctrine`: raises `DoctrineError` when `validate_group` rejects the input, before any filesystem write occurs

---

## Out of Scope

- Validating the group parameter's character set and forbidden patterns (covered by US-005)
- Moving or renaming an existing doctrine between groups (`edit --group`, `mv`)
- Any change to the `.yaml` / `.design.md` file format
- Updating the list display or filter grammar (covered by US-007, US-008)
- Extracting knight/artifact create logic (covered by US-002, US-004)

---

## References

- PRD: `lore codex show group-param-prd`
- Tech Spec: `lore codex show group-param-tech-spec`
- Workflow: `lore codex show conceptual-workflows-doctrine-new`

---

## Tech Notes

### Implementation Approach

- `src/lore/doctrine.py` — extend `create_doctrine(name, yaml_source_path, design_source_path, doctrines_dir)` signature with `*, group: str | None = None`. Validation order becomes: `validate_name` → `validate_group` (raise `DoctrineError`) → subtree rglob duplicate check (unchanged, already `doctrines_dir.rglob(f"{name}.yaml")`) → source file existence → YAML/design content validation → compute `target_dir = doctrines_dir if group is None else doctrines_dir / Path(group)` → `target_dir.mkdir(parents=True, exist_ok=True)` → `shutil.copy2` both files into `target_dir`. Return dict gains `"group": group` and `"path": str(target_dir / f"{name}.yaml")`.
- `src/lore/cli.py` `doctrine_new` (line ~1248) — add Click option `@click.option("--group", default=None, help="Nested subdirectory under .lore/doctrines/ (slash-delimited, e.g. seo-analysis/keyword-analysers).")` and pass `group=group` through to `create_doctrine`. No mkdir or validation moves into the handler. On success, render text `Created doctrine {name}` when group is None, `Created doctrine {name} (group: {group})` otherwise. JSON envelope emits the full result dict (includes `group` and `path`; `group` is `None` for root).

### Test File Locations

- Unit: `tests/unit/test_doctrine.py` (existing) — add `TestCreateDoctrineGroup` class.
- E2E: `tests/e2e/test_doctrine_new.py` (existing) — add nested-create scenarios.

### Test Stubs

```python
# tests/e2e/test_doctrine_new.py
# anchor: conceptual-workflows-doctrine-new (step 5 write subtree + step 2 duplicate rglob)

def test_doctrine_new_nested_happy_path(runner, project_dir):
    # Scenario 1 — cites conceptual-workflows-doctrine-new
    _write_sources(project_dir, "ranker.yaml", "ranker.design.md", name="keyword-ranker")
    result = runner.invoke(main, [
        "doctrine", "new", "keyword-ranker",
        "--group", "seo-analysis/keyword-analysers",
        "-f", "ranker.yaml", "-d", "ranker.design.md",
    ])
    assert result.exit_code == 0
    assert result.output.strip() == "Created doctrine keyword-ranker (group: seo-analysis/keyword-analysers)"
    assert (project_dir / ".lore/doctrines/seo-analysis/keyword-analysers/keyword-ranker.yaml").exists()
    assert (project_dir / ".lore/doctrines/seo-analysis/keyword-analysers/keyword-ranker.design.md").exists()

def test_doctrine_new_nested_json_envelope(runner, project_dir):
    # Scenario 2 — cites conceptual-workflows-json-output
    _write_sources(project_dir, "ranker.yaml", "ranker.design.md", name="keyword-ranker")
    result = runner.invoke(main, [
        "doctrine", "new", "keyword-ranker",
        "--group", "seo-analysis/keyword-analysers",
        "-f", "ranker.yaml", "-d", "ranker.design.md", "--json",
    ])
    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "name": "keyword-ranker",
        "group": "seo-analysis/keyword-analysers",
        "yaml_filename": "keyword-ranker.yaml",
        "design_filename": "keyword-ranker.design.md",
        "path": ".lore/doctrines/seo-analysis/keyword-analysers/keyword-ranker.yaml",
    }

def test_doctrine_new_root_unchanged(runner, project_dir):
    # Scenario 3 — cites conceptual-workflows-doctrine-new
    _write_sources(project_dir, "flat.yaml", "flat.design.md", name="flat-doctrine")
    result = runner.invoke(main, ["doctrine", "new", "flat-doctrine", "-f", "flat.yaml", "-d", "flat.design.md"])
    assert result.exit_code == 0
    assert result.output.strip() == "Created doctrine flat-doctrine"
    assert (project_dir / ".lore/doctrines/flat-doctrine.yaml").exists()

def test_doctrine_new_duplicate_subtree_rejected(runner, project_dir):
    # Scenario 4 — cites conceptual-workflows-doctrine-new (duplicate rglob)
    (project_dir / ".lore/doctrines/seo-analysis").mkdir(parents=True)
    (project_dir / ".lore/doctrines/seo-analysis/ranker.yaml").write_text("id: ranker\nsteps: [{id: s, title: t}]\n")
    (project_dir / ".lore/doctrines/seo-analysis/ranker.design.md").write_text("---\nid: ranker\n---\n")
    _write_sources(project_dir, "ranker.yaml", "ranker.design.md", name="ranker")
    result = runner.invoke(main, [
        "doctrine", "new", "ranker", "--group", "other-feature",
        "-f", "ranker.yaml", "-d", "ranker.design.md",
    ])
    assert result.exit_code == 1
    assert "already exists" in result.stderr
    assert not (project_dir / ".lore/doctrines/other-feature").exists()

def test_doctrine_new_mkdir_idempotent(runner, project_dir):
    # Scenario 5 — cites conceptual-workflows-doctrine-new (mkdir parents=True exist_ok=True)
    (project_dir / ".lore/doctrines/existing-group").mkdir(parents=True)
    _write_sources(project_dir, "d.yaml", "d.design.md", name="new-doc")
    result = runner.invoke(main, [
        "doctrine", "new", "new-doc", "--group", "existing-group",
        "-f", "d.yaml", "-d", "d.design.md",
    ])
    assert result.exit_code == 0
    assert (project_dir / ".lore/doctrines/existing-group/new-doc.yaml").exists()
```

```python
# tests/unit/test_doctrine.py
# anchor: conceptual-workflows-doctrine-new

def test_create_doctrine_group_none_writes_flat(tmp_path):
    # AC unit: group=None flat write (unchanged)
    create_doctrine("d", yaml_src, design_src, tmp_path)
    assert (tmp_path / "d.yaml").exists()

def test_create_doctrine_group_nested_writes_nested(tmp_path):
    # AC unit: group="a/b/c" nested write
    result = create_doctrine("d", yaml_src, design_src, tmp_path, group="a/b/c")
    assert (tmp_path / "a/b/c/d.yaml").exists()
    assert result["group"] == "a/b/c"
    assert result["path"] == str(tmp_path / "a/b/c/d.yaml")

def test_create_doctrine_mkdir_idempotent(tmp_path):
    # AC unit: pre-existing nested dir does not error
    (tmp_path / "a/b").mkdir(parents=True)
    create_doctrine("d", yaml_src, design_src, tmp_path, group="a/b")
    assert (tmp_path / "a/b/d.yaml").exists()

def test_create_doctrine_duplicate_subtree_raises(tmp_path):
    # AC unit: subtree rglob duplicate fires regardless of group
    (tmp_path / "x").mkdir()
    (tmp_path / "x/d.yaml").write_text("id: d\nsteps: [{id: s, title: t}]\n")
    with pytest.raises(DoctrineError, match="already exists"):
        create_doctrine("d", yaml_src, design_src, tmp_path, group="y")

def test_create_doctrine_invalid_group_raises_before_write(tmp_path):
    # AC unit: validate_group failure raises DoctrineError before any filesystem write
    with pytest.raises(DoctrineError, match="invalid group"):
        create_doctrine("d", yaml_src, design_src, tmp_path, group="../etc")
    assert not (tmp_path / "d.yaml").exists()

def test_create_doctrine_return_dict_keys(tmp_path):
    # AC unit: return dict carries group and path
    result = create_doctrine("d", yaml_src, design_src, tmp_path, group="a/b")
    assert result["group"] == "a/b"
    assert result["path"].endswith("a/b/d.yaml")
```

### Complexity Estimate

**M** — signature extension on one existing helper, new kwarg wiring in one CLI handler, five new E2E scenarios, six new unit cases; no architectural change beyond target_dir resolution.
