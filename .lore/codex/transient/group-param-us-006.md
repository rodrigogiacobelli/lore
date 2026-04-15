---
id: group-param-us-006
title: US-006 paths.derive_group slash-joined canonical form
summary: Migrates lore.paths.derive_group to return slash-joined group strings as the single canonical in-memory form, replacing the current hyphen-joined output without any other signature change.
type: user-story
status: final
---

## Metadata

- **ID:** US-006
- **Status:** final
- **Epic:** List display + filter migration
- **Author:** Business Analyst
- **Date:** 2026-04-15
- **PRD:** `lore codex show group-param-prd`
- **Tech Spec:** `lore codex show group-param-tech-spec`

---

## Story

As a core-module author, I want `lore.paths.derive_group` to return `"a/b/c"` instead of `"a-b-c"` so that every list renderer, JSON envelope, and filter parser reads and writes the same canonical slash-joined form without any translation layer.

## Context

Fulfills functional requirement FR-11 and the Tech Spec's "Canonical in-memory group form" decision. The PRD resolves the open question from the business context map: migrate the underlying form in lock-step rather than introducing a sibling display helper. This story is the atomic change to `derive_group`; every list renderer immediately benefits because they consume `derive_group`'s output directly.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Derived group reaches list output as slash-joined

**Given** a file already on disk at `.lore/artifacts/default/codex/overview.md` with valid frontmatter
**When** the user runs `lore artifact list`
**Then** the row for `overview` shows `GROUP` column value `default/codex` (not `default-codex`), and exit code is 0.

#### Scenario 2: Root file still renders as root sentinel

**Given** a file at `.lore/artifacts/transient-note.md`
**When** the user runs `lore artifact list`
**Then** the row for `transient-note` renders the empty/root-group sentinel (unchanged behaviour), and exit code is 0.

### Unit Test Scenarios

- [ ] `lore.paths.derive_group`: signature unchanged — `derive_group(filepath, base_dir) -> str`
- [ ] `lore.paths.derive_group`: file directly under `base_dir` returns `""`
- [ ] `lore.paths.derive_group`: file in a single subdirectory `base_dir/a/x.md` returns `"a"`
- [ ] `lore.paths.derive_group`: deeply nested `base_dir/a/b/c/x.md` returns `"a/b/c"`
- [ ] `lore.paths.derive_group`: returned string never contains `-` as a segment separator — asserted by constructing a path whose segments themselves contain hyphens (`base_dir/a-b/c-d/x.md` → `"a-b/c-d"`)
- [ ] `lore.paths.derive_group`: Windows-style separators are not produced (no `\` in output)

---

## Out of Scope

- Filter grammar change (covered by US-008)
- JSON envelope audit for list commands (covered by US-007)
- CLI help text updates (covered by US-010)
- Any change to `derive_group`'s signature or callers

---

## References

- PRD: `lore codex show group-param-prd`
- Tech Spec: `lore codex show group-param-tech-spec`

---

## Tech Notes

### Implementation Approach

- `src/lore/paths.py` `derive_group` (line ~44) — change the body's final line from `return "-".join(parts)` to `return "/".join(parts)`. Signature unchanged. Update the docstring to say "joined with slashes". Every caller (`doctrine.list_doctrines`, `knight.list_knights`, `watcher.list_watchers`, `artifact.scan_artifacts`, `codex.scan_codex`, `cli.codex_list`) consumes this return value unchanged — the in-memory form propagates to both list dicts and JSON envelopes without any other edit. Note: `group_matches_filter` must be migrated in lock-step to avoid breaking list `--filter` — covered by US-008.

### Test File Locations

- Unit: `tests/unit/test_derive_group.py` (existing) — flip every assertion from `-` to `/` and add the hyphen-in-segment preservation test.
- E2E: `tests/e2e/test_artifact_list.py` (existing) — update existing list assertions plus add the scenario covering a file with hyphens inside segment names.

### Test Stubs

```python
# tests/unit/test_derive_group.py
# anchor: conceptual-workflows-filter-list

def test_derive_group_signature_unchanged():
    # AC unit: signature preserved
    import inspect
    sig = inspect.signature(derive_group)
    assert list(sig.parameters) == ["filepath", "base_dir"]

def test_derive_group_root_returns_empty(tmp_path):
    # AC unit: file directly under base_dir → ""
    (tmp_path / "x.md").touch()
    assert derive_group(tmp_path / "x.md", tmp_path) == ""

def test_derive_group_single_subdir(tmp_path):
    # AC unit: one nesting level → "a"
    (tmp_path / "a").mkdir()
    (tmp_path / "a/x.md").touch()
    assert derive_group(tmp_path / "a/x.md", tmp_path) == "a"

def test_derive_group_deeply_nested(tmp_path):
    # AC unit: multi-level → "a/b/c"
    (tmp_path / "a/b/c").mkdir(parents=True)
    (tmp_path / "a/b/c/x.md").touch()
    assert derive_group(tmp_path / "a/b/c/x.md", tmp_path) == "a/b/c"

def test_derive_group_preserves_hyphens_in_segments(tmp_path):
    # AC unit: hyphens within segment names are preserved; separator is /
    (tmp_path / "a-b/c-d").mkdir(parents=True)
    (tmp_path / "a-b/c-d/x.md").touch()
    result = derive_group(tmp_path / "a-b/c-d/x.md", tmp_path)
    assert result == "a-b/c-d"
    # Separator is never "-" between segments
    assert result.split("/") == ["a-b", "c-d"]

def test_derive_group_no_windows_separators(tmp_path):
    # AC unit: output never contains \
    (tmp_path / "a/b").mkdir(parents=True)
    (tmp_path / "a/b/x.md").touch()
    assert "\\" not in derive_group(tmp_path / "a/b/x.md", tmp_path)
```

```python
# tests/e2e/test_artifact_list.py
# anchor: conceptual-workflows-artifact-list

def test_artifact_list_shows_slash_joined_group(runner, project_dir):
    # Scenario 1 — derived group reaches list output as slash-joined
    (project_dir / ".lore/artifacts/default/codex").mkdir(parents=True)
    (project_dir / ".lore/artifacts/default/codex/overview.md").write_text(
        "---\nid: overview\ntitle: Overview\nsummary: s\n---\n"
    )
    result = runner.invoke(main, ["artifact", "list"])
    assert result.exit_code == 0
    assert "default/codex" in result.output
    assert "default-codex" not in result.output

def test_artifact_list_root_sentinel_unchanged(runner, project_dir):
    # Scenario 2 — root file renders empty/root sentinel
    (project_dir / ".lore/artifacts").mkdir(parents=True)
    (project_dir / ".lore/artifacts/transient-note.md").write_text(
        "---\nid: transient-note\ntitle: T\nsummary: s\n---\n"
    )
    result = runner.invoke(main, ["artifact", "list"])
    assert result.exit_code == 0
    # Root row still rendered without a slash-joined group cell
    assert "transient-note" in result.output
```

### Complexity Estimate

**XS** — one-line body change inside `derive_group` plus mechanical test assertion flips. Real risk is all downstream callers; those are covered by US-007 and US-008 unit/E2E tests in the same commit.
