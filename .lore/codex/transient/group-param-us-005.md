---
id: group-param-us-005
title: US-005 validate_group validator with zero lore imports
summary: Adds a new validate_group function to lore.validators that rejects path traversal, backslashes, absolute paths, leading/trailing slashes, empty segments, and per-segment tokens failing the existing name character rule, with zero lore.* imports.
type: user-story
status: final
---

## Metadata

- **ID:** US-005
- **Status:** final
- **Epic:** Python API parity — core helpers
- **Author:** Business Analyst
- **Date:** 2026-04-15
- **PRD:** `lore codex show group-param-prd`
- **Tech Spec:** `lore codex show group-param-tech-spec`

---

## Story

As a core-module author wiring `--group` into the four entity create helpers, I want a single `validate_group(group: str | None) -> str | None` function in `lore/validators.py` that rejects every unsafe group string and returns `None` on success, so that every create path shares one chokepoint against path traversal and every entity helper reuses the same rules.

## Context

Fulfills functional requirements FR-4, FR-5, FR-10 and the Non-Functional Security clause of the PRD ("`validate_group` is the single chokepoint against path traversal"). `lore/validators.py` is the dependency-inversion boundary — it must not import from `lore.*`. This story adds the validator and its test matrix; it does NOT wire the validator into entity helpers (that happens inside US-001..US-004).

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Invalid group rejected end-to-end via doctrine new

**Given** source files are present and no doctrine name collision
**When** the user runs `lore doctrine new d1 --group ../etc -f d.yaml -d d.design.md`
**Then** stderr contains `Error: invalid group '../etc': path traversal ('..') not allowed`, exit code is 1, and no file or directory is created outside `.lore/doctrines/`.

#### Scenario 2: Leading slash rejected

**When** the user runs `lore knight new k1 --group /abs --from p.md`
**Then** stderr contains `Error: invalid group '/abs': absolute paths not allowed` (or equivalent message mentioning leading `/`), exit code is 1, and no file is written.

#### Scenario 3: Empty segment rejected

**When** the user runs `lore watcher new w1 --group a//b -f w.yaml`
**Then** stderr contains `Error: invalid group 'a//b': empty segment not allowed`, exit code is 1, and no file is written.

#### Scenario 4: Backslash rejected

**When** the user runs `lore artifact new a1 --group a\\b --from a.md`
**Then** stderr contains `Error: invalid group 'a\\b': backslash not allowed`, exit code is 1, and no file is written.

### Unit Test Scenarios

- [ ] `lore.validators.validate_group`: `None` input returns `None`
- [ ] `lore.validators.validate_group`: valid single segment `"a"` returns `None`
- [ ] `lore.validators.validate_group`: valid nested `"a/b/c"` returns `None`
- [ ] `lore.validators.validate_group`: valid with hyphens/underscores `"a-b/c_d"` returns `None`
- [ ] `lore.validators.validate_group`: empty string `""` returns a non-None error message mentioning empty
- [ ] `lore.validators.validate_group`: `".."` and `"../x"` and `"x/.."` each return an error mentioning path traversal
- [ ] `lore.validators.validate_group`: `"\\x"` and `"a\\b"` each return an error mentioning backslash
- [ ] `lore.validators.validate_group`: `"/x"` returns an error mentioning absolute path or leading slash
- [ ] `lore.validators.validate_group`: `"x/"` returns an error mentioning trailing slash
- [ ] `lore.validators.validate_group`: `"a//b"` returns an error mentioning empty segment
- [ ] `lore.validators.validate_group`: `"a/!/b"` returns an error mentioning the bad segment characters
- [ ] `lore.validators.validate_group`: `"-a"` returns an error (leading hyphen violates `_NAME_RE`)
- [ ] `lore.validators`: module does not import from any `lore.*` submodule — asserted by parsing the source file's imports

---

## Out of Scope

- Wiring `validate_group` into `create_doctrine`, `create_knight`, `create_watcher`, `create_artifact` — covered by US-001..US-004
- Any change to `validate_name`
- Any change to duplicate-detection logic

---

## References

- PRD: `lore codex show group-param-prd`
- Tech Spec: `lore codex show group-param-tech-spec`
- ADR: `lore codex show standards-dependency-inversion`

---

## Tech Notes

### Implementation Approach

- `src/lore/validators.py` — add `validate_group(group: str | None) -> str | None` returning `None` on success or an error string on failure (mirrors `validate_name`'s contract). Rules in order: `None` → `None`; empty string → error mentioning empty; presence of `\\` → error mentioning backslash; `startswith("/")` → error mentioning absolute/leading; `endswith("/")` → error mentioning trailing; then `segments = group.split("/")`, and for each segment: empty → error mentioning empty segment; `".."` → error mentioning path traversal; `not _NAME_RE.match(seg)` → error mentioning bad segment chars. No `lore.*` imports. Reuse the existing `_NAME_RE` compiled pattern at the top of `validators.py`. Note: the four `create_*` helpers convert the returned string into their own exception class — this story only ships the validator, per "Out of Scope".
- CLI wiring is NOT part of this story — validators are invoked from `create_doctrine`, `create_knight`, `create_watcher`, `create_artifact` (covered by US-001..US-004). The E2E scenarios in this story exercise the four existing `new` handlers only to prove the end-to-end error path once the validator is wired in by those stories.

### Test File Locations

- Unit: `tests/unit/test_validators.py` (existing) — add `TestValidateGroup` class. Plus a single `test_validators_has_no_lore_imports` test.
- E2E: covered incidentally by `tests/e2e/test_doctrine_new.py`, `test_knight_crud.py`, `test_watcher_crud.py`, `test_artifact_new.py` — add the four invalid-group scenarios below in whichever file is closest to the exercised entity (one scenario per file).

### Test Stubs

```python
# tests/e2e/test_doctrine_new.py
# anchor: conceptual-workflows-validators (single chokepoint)

def test_doctrine_new_invalid_group_dotdot_rejected(runner, project_dir):
    # US-005 Scenario 1 — path traversal
    _write_sources(project_dir, "d.yaml", "d.design.md", name="d1")
    result = runner.invoke(main, [
        "doctrine", "new", "d1", "--group", "../etc", "-f", "d.yaml", "-d", "d.design.md",
    ])
    assert result.exit_code == 1
    assert "invalid group '../etc'" in result.stderr
    assert "path traversal" in result.stderr
    assert not any((project_dir / ".lore/doctrines").rglob("d1.yaml"))
```

```python
# tests/e2e/test_knight_crud.py
# anchor: conceptual-workflows-validators

def test_knight_new_invalid_group_leading_slash_rejected(runner, project_dir):
    # US-005 Scenario 2 — absolute path
    (project_dir / "p.md").write_text("---\nid: k1\n---\n")
    result = runner.invoke(main, ["knight", "new", "k1", "--group", "/abs", "--from", "p.md"])
    assert result.exit_code == 1
    assert "invalid group '/abs'" in result.stderr
    assert "absolute" in result.stderr or "leading" in result.stderr
    assert not any((project_dir / ".lore/knights").rglob("k1.md"))
```

```python
# tests/e2e/test_watcher_crud.py
# anchor: conceptual-workflows-validators

def test_watcher_new_invalid_group_empty_segment_rejected(runner, project_dir):
    # US-005 Scenario 3 — empty segment
    (project_dir / "w.yaml").write_text("id: w1\n")
    result = runner.invoke(main, ["watcher", "new", "w1", "--group", "a//b", "-f", "w.yaml"])
    assert result.exit_code == 1
    assert "invalid group 'a//b'" in result.stderr
    assert "empty segment" in result.stderr
    assert not any((project_dir / ".lore/watchers").rglob("w1.yaml"))
```

```python
# tests/e2e/test_artifact_new.py
# anchor: conceptual-workflows-validators

def test_artifact_new_invalid_group_backslash_rejected(runner, project_dir):
    # US-005 Scenario 4 — backslash
    (project_dir / "a.md").write_text("---\nid: a1\ntitle: T\nsummary: s\n---\n")
    result = runner.invoke(main, ["artifact", "new", "a1", "--group", "a\\b", "--from", "a.md"])
    assert result.exit_code == 1
    assert "invalid group 'a\\\\b'" in result.stderr or "backslash" in result.stderr
    assert not any((project_dir / ".lore/artifacts").rglob("a1.md"))
```

```python
# tests/unit/test_validators.py
# anchor: conceptual-workflows-validators

class TestValidateGroup:
    def test_none_returns_none(self):
        assert validate_group(None) is None
    def test_valid_single_segment(self):
        assert validate_group("a") is None
    def test_valid_nested(self):
        assert validate_group("a/b/c") is None
    def test_valid_hyphen_underscore(self):
        assert validate_group("a-b/c_d") is None
    def test_empty_string_error(self):
        err = validate_group("")
        assert err is not None and "empty" in err
    def test_dotdot_root_error(self):
        assert "path traversal" in validate_group("..")
    def test_dotdot_prefix_error(self):
        assert "path traversal" in validate_group("../x")
    def test_dotdot_suffix_error(self):
        assert "path traversal" in validate_group("x/..")
    def test_backslash_error(self):
        assert "backslash" in validate_group("\\x")
        assert "backslash" in validate_group("a\\b")
    def test_leading_slash_error(self):
        err = validate_group("/x")
        assert err is not None and ("absolute" in err or "leading" in err)
    def test_trailing_slash_error(self):
        err = validate_group("x/")
        assert err is not None and "trailing" in err
    def test_empty_segment_error(self):
        assert "empty segment" in validate_group("a//b")
    def test_bad_chars_in_segment_error(self):
        err = validate_group("a/!/b")
        assert err is not None and ("segment" in err or "characters" in err)
    def test_leading_hyphen_in_segment_error(self):
        # _NAME_RE requires alphanumeric start
        assert validate_group("-a") is not None

def test_validators_has_no_lore_imports():
    # Enforces standards-dependency-inversion: validators.py must not import lore.*
    import ast
    src = (Path(__file__).parents[2] / "src/lore/validators.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or not node.module.startswith("lore")
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("lore")
```

### Complexity Estimate

**S** — pure function addition to `validators.py` plus one AST import-check test; extensive unit matrix but straightforward logic.
