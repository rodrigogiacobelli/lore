---
id: group-param-us-004
title: US-004 Artifact new subcommand with --group
summary: Lore ships a brand new lore artifact new CLI subcommand and lore.artifact.create_artifact Python API, producing a single markdown artifact file under .lore/artifacts/[group/]name.md with frontmatter validation, auto-mkdir, and subtree duplicate detection.
type: user-story
status: final
---

## Metadata

- **ID:** US-004
- **Status:** final
- **Epic:** Entity creation — --group parameter
- **Author:** Business Analyst
- **Date:** 2026-04-15
- **PRD:** `lore codex show group-param-prd`
- **Tech Spec:** `lore codex show group-param-tech-spec`

---

## Story

As a Realm orchestrator agent producing a new artifact template, I want a `lore artifact new` command that writes a single markdown artifact file into `.lore/artifacts/`, optionally into a nested subdirectory via `--group`, so that artifacts can be created through the same CLI + Python API surface as doctrines, knights, and watchers.

## Context

Fulfills PRD workflow "Create a nested artifact — AI orchestrator" and functional requirements FR-7, FR-8, FR-9. Today `lore/artifact.py` is read-only; the only way to create an artifact is to hand-write a markdown file on disk. This story introduces the first write path for artifacts, reaching sibling-module symmetry with `create_doctrine`, `create_knight`, and `create_watcher`.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Nested artifact create — happy path

**Given** no artifact named `fi-review` exists anywhere under `.lore/artifacts/`, and a body file `review.md` containing valid frontmatter (`id`, `title`, `summary`) is present in the working directory
**When** the user runs `lore artifact new fi-review --group codex/templates --from review.md`
**Then** stdout is exactly `Created artifact fi-review (group: codex/templates)`, file `.lore/artifacts/codex/templates/fi-review.md` exists, and exit code is 0.

#### Scenario 2: Nested artifact create — JSON envelope

**Given** the same preconditions as Scenario 1
**When** the user runs `lore artifact new fi-review --group codex/templates --from review.md --json`
**Then** stdout parses as JSON equal to `{"id": "fi-review", "group": "codex/templates", "filename": "fi-review.md", "path": ".lore/artifacts/codex/templates/fi-review.md"}` and exit code is 0.

#### Scenario 3: Root artifact create — --group omitted, JSON group is null

**Given** no artifact named `transient-note` exists and a valid body file is present
**When** the user runs `lore artifact new transient-note --from note.md --json`
**Then** stdout parses as JSON whose `group` key equals `null`, file `.lore/artifacts/transient-note.md` exists directly under the artifacts root, and exit code is 0.

#### Scenario 4: Duplicate name anywhere in subtree rejected

**Given** an artifact `overview` exists at `.lore/artifacts/default/codex/overview.md`
**When** the user runs `lore artifact new overview --group other --from o.md`
**Then** stderr contains `Error: artifact 'overview' already exists`, exit code is 1, and no file is created under `.lore/artifacts/other/`.

#### Scenario 5: Missing required frontmatter fields rejected

**Given** a body file `bad.md` whose frontmatter is missing the `summary` field
**When** the user runs `lore artifact new bad-one --from bad.md`
**Then** stderr contains an error identifying the missing `summary` field, exit code is 1, and no file is written.

### Unit Test Scenarios

- [ ] `lore.artifact.create_artifact`: function exists with signature `(artifacts_dir, name, content, *, group=None) -> dict`
- [ ] `lore.artifact.create_artifact`: `group=None` writes to `artifacts_dir / "<name>.md"`
- [ ] `lore.artifact.create_artifact`: `group="a/b"` writes to `artifacts_dir / "a" / "b" / "<name>.md"` with intermediate dirs auto-created
- [ ] `lore.artifact.create_artifact`: raises `ValueError` when same-stemmed `*.md` file exists anywhere under `artifacts_dir` via rglob
- [ ] `lore.artifact.create_artifact`: raises `ValueError` when body content is missing any of the required frontmatter fields (`id`, `title`, `summary`), matching the strict rule applied by `scan_artifacts`
- [ ] `lore.artifact.create_artifact`: return dict contains `id`, `group`, `filename`, `path` keys
- [ ] `lore.artifact.create_artifact`: raises `ValueError` when `validate_group` rejects the input, before any filesystem write
- [ ] `lore.cli.artifact_new` thin-wrapper smoke: with `create_artifact` monkeypatched, the CLI handler calls it with the parsed `--group` value and performs no validation or mkdir of its own

---

## Out of Scope

- `lore artifact edit`, `lore artifact delete`, `lore artifact mv` — this story adds only `new`
- Group validator implementation (covered by US-005)
- Artifact list display or filter grammar (covered by US-007, US-008)
- Any change to the artifact frontmatter schema itself

---

## References

- PRD: `lore codex show group-param-prd`
- Tech Spec: `lore codex show group-param-tech-spec`
- Workflow: `lore codex show conceptual-workflows-artifact-list`
- Entity: `lore codex show conceptual-entities-artifact`

---

## Tech Notes

### Implementation Approach

- `src/lore/artifact.py` — add new `create_artifact(artifacts_dir: Path, name: str, content: str, *, group: str | None = None) -> dict`. Validation order: `validate_name(name)` → `validate_group(group)` (raise `ValueError`) → non-empty content → subtree duplicate via `artifacts_dir.rglob("*.md")` matching `filepath.stem == name` → strict frontmatter parse of `content` using `frontmatter.parse_frontmatter_doc_full` (or inline parse) requiring `id`, `title`, `summary` (mirrors `scan_artifacts`) — raise `ValueError` if any required field is missing → compute `target_dir = artifacts_dir if group is None else artifacts_dir / Path(group)` → `target_dir.mkdir(parents=True, exist_ok=True)` → write `target_dir / f"{name}.md"`. Return `{"id": name, "group": group, "filename": f"{name}.md", "path": str(target_dir / f"{name}.md")}`.
- `src/lore/cli.py` — add new subcommand `artifact_new` under the existing `@main.group() artifact` group (around line 2376). Mirrors `watcher_new` structure: `--from` file or stdin read, `--group` option, `--json` flag, `try/except ValueError` around `create_artifact(artifacts_dir, name, content, group=group)`. Success text: `Created artifact {name}` or `Created artifact {name} (group: {group})`.

### Test File Locations

- Unit: `tests/unit/test_artifact.py` (existing) — add `TestCreateArtifact` class.
- E2E: `tests/e2e/test_artifact_new.py` (new file).

### Test Stubs

```python
# tests/e2e/test_artifact_new.py — new file
"""anchor: conceptual-workflows-artifact-list (first write path)"""

_VALID_BODY = "---\nid: fi-review\ntitle: Review\nsummary: s\n---\nbody\n"

def test_artifact_new_nested_happy_path(runner, project_dir):
    # Scenario 1 — cites conceptual-workflows-artifact-list
    (project_dir / "review.md").write_text(_VALID_BODY)
    result = runner.invoke(main, [
        "artifact", "new", "fi-review",
        "--group", "codex/templates", "--from", "review.md",
    ])
    assert result.exit_code == 0
    assert result.output.strip() == "Created artifact fi-review (group: codex/templates)"
    assert (project_dir / ".lore/artifacts/codex/templates/fi-review.md").exists()

def test_artifact_new_nested_json_envelope(runner, project_dir):
    # Scenario 2 — cites conceptual-workflows-json-output
    (project_dir / "review.md").write_text(_VALID_BODY)
    result = runner.invoke(main, [
        "artifact", "new", "fi-review",
        "--group", "codex/templates", "--from", "review.md", "--json",
    ])
    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "id": "fi-review", "group": "codex/templates",
        "filename": "fi-review.md",
        "path": ".lore/artifacts/codex/templates/fi-review.md",
    }

def test_artifact_new_root_json_null_group(runner, project_dir):
    # Scenario 3 — cites conceptual-workflows-json-output
    body = "---\nid: transient-note\ntitle: T\nsummary: s\n---\n"
    (project_dir / "note.md").write_text(body)
    result = runner.invoke(main, ["artifact", "new", "transient-note", "--from", "note.md", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["group"] is None
    assert (project_dir / ".lore/artifacts/transient-note.md").exists()

def test_artifact_new_duplicate_subtree_rejected(runner, project_dir):
    # Scenario 4 — cites conceptual-workflows-artifact-list (rglob)
    (project_dir / ".lore/artifacts/default/codex").mkdir(parents=True)
    (project_dir / ".lore/artifacts/default/codex/overview.md").write_text(
        "---\nid: overview\ntitle: T\nsummary: s\n---\n"
    )
    (project_dir / "o.md").write_text("---\nid: overview\ntitle: T\nsummary: s\n---\n")
    result = runner.invoke(main, ["artifact", "new", "overview", "--group", "other", "--from", "o.md"])
    assert result.exit_code == 1
    assert "already exists" in result.stderr
    assert not (project_dir / ".lore/artifacts/other").exists()

def test_artifact_new_missing_frontmatter_rejected(runner, project_dir):
    # Scenario 5 — cites conceptual-workflows-artifact-list (strict frontmatter)
    (project_dir / "bad.md").write_text("---\nid: bad-one\ntitle: T\n---\n")
    result = runner.invoke(main, ["artifact", "new", "bad-one", "--from", "bad.md"])
    assert result.exit_code == 1
    assert "summary" in result.stderr
    assert not any((project_dir / ".lore/artifacts").rglob("bad-one.md"))
```

```python
# tests/unit/test_artifact.py
# anchor: conceptual-workflows-artifact-list

def test_create_artifact_signature_exists():
    # AC unit: kwarg-only group signature
    import inspect
    sig = inspect.signature(create_artifact)
    assert sig.parameters["group"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["group"].default is None

def test_create_artifact_root_write(tmp_path):
    # AC unit: group=None flat write
    create_artifact(tmp_path, "a", _VALID_BODY)
    assert (tmp_path / "a.md").exists()

def test_create_artifact_nested_write_auto_mkdir(tmp_path):
    # AC unit: nested write + auto mkdir
    create_artifact(tmp_path, "a", _VALID_BODY, group="a/b")
    assert (tmp_path / "a/b/a.md").exists()

def test_create_artifact_duplicate_subtree_raises(tmp_path):
    # AC unit: rglob duplicate
    (tmp_path / "x").mkdir()
    (tmp_path / "x/a.md").write_text(_VALID_BODY)
    with pytest.raises(ValueError, match="already exists"):
        create_artifact(tmp_path, "a", _VALID_BODY, group="y")

def test_create_artifact_missing_frontmatter_raises(tmp_path):
    # AC unit: strict frontmatter (matches scan_artifacts)
    bad = "---\nid: a\ntitle: T\n---\n"
    with pytest.raises(ValueError, match="summary"):
        create_artifact(tmp_path, "a", bad)

def test_create_artifact_return_dict_keys(tmp_path):
    # AC unit: id/group/filename/path keys
    result = create_artifact(tmp_path, "a", _VALID_BODY, group="a/b")
    assert set(result.keys()) >= {"id", "group", "filename", "path"}
    assert result["group"] == "a/b"

def test_create_artifact_invalid_group_raises_before_write(tmp_path):
    # AC unit: validate_group failure raises before write
    with pytest.raises(ValueError, match="invalid group"):
        create_artifact(tmp_path, "a", _VALID_BODY, group="../x")
    assert not any(tmp_path.rglob("*.md"))

def test_cli_artifact_new_thin_wrapper_smoke(monkeypatch, runner, project_dir):
    # AC unit: CLI handler passes group kwarg, no local validation
    # anchor: decisions-011-api-parity-with-cli
    captured = {}
    def fake(dir_, name, content, *, group=None):
        captured["group"] = group
        return {"id": name, "group": group, "filename": f"{name}.md", "path": "x"}
    monkeypatch.setattr("lore.artifact.create_artifact", fake)
    (project_dir / "b.md").write_text("body")
    result = runner.invoke(main, ["artifact", "new", "a", "--group", "x/y", "--from", "b.md"])
    assert result.exit_code == 0
    assert captured["group"] == "x/y"
```

### Complexity Estimate

**M** — new `create_artifact` helper (first artifact write path), new CLI subcommand, new E2E test file, strict frontmatter re-parse plumbing, full unit matrix plus thin-wrapper smoke.
