---
id: group-param-us-008
title: US-008 --filter slash-delimited tokens with segment-prefix matching
summary: Breaking change to --filter grammar on all five list commands — filter tokens are now slash-delimited, parsed by splitting on /, and matched segment-by-segment against each entity's subdirectory path. Leading or trailing slashes are stripped silently; empty tokens still error.
type: user-story
status: final
---

## Metadata

- **ID:** US-008
- **Status:** final
- **Epic:** List display + filter migration
- **Author:** Business Analyst
- **Date:** 2026-04-15
- **PRD:** `lore codex show group-param-prd`
- **Tech Spec:** `lore codex show group-param-tech-spec`

---

## Story

As a user filtering a list of entities by group, I want `--filter seo-analysis/keyword-analysers` to match the same rows that show `GROUP = seo-analysis/keyword-analysers` in `list`, so that the token I type at create, the string I read in `list`, and the token I pass to `--filter` are all identical.

## Context

Fulfills functional requirement FR-14 and the PRD workflow "List + filter with slash-joined groups — any user". The PRD picks option (b) from the business context map: migrate the filter grammar in lock-step with the display delimiter, rather than accepting both forms or translating in the display layer. This is a user-visible breaking change — the CHANGELOG must document it.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Slash-delimited filter returns expected row — doctrine

**Given** a doctrine at `.lore/doctrines/seo-analysis/keyword-analysers/ranker.yaml` and an unrelated doctrine at `.lore/doctrines/other/foo.yaml`
**When** the user runs `lore doctrine list --filter seo-analysis/keyword-analysers`
**Then** the output table contains the `ranker` row and does NOT contain `foo`, and exit code is 0.

#### Scenario 2: Segment-prefix match — partial path

**Given** the same preconditions as Scenario 1
**When** the user runs `lore doctrine list --filter seo-analysis`
**Then** the output table contains the `ranker` row (its group segments begin with `seo-analysis`), and exit code is 0.

#### Scenario 3: Bare prefix that is not a full segment does NOT match

**Given** a doctrine at `.lore/doctrines/technical/api/x.yaml`
**When** the user runs `lore doctrine list --filter tech`
**Then** the `x` row does NOT appear in the output (bare substring `tech` is not a full `technical` segment), and exit code is 0.

#### Scenario 4: Root rows always included

**Given** a doctrine at `.lore/doctrines/seo-analysis/ranker.yaml` and a root doctrine at `.lore/doctrines/flat.yaml`
**When** the user runs `lore doctrine list --filter seo-analysis`
**Then** both `ranker` and `flat` appear (root rows are included regardless of filter, unchanged inclusion rule), and exit code is 0.

#### Scenario 5: Leading or trailing slash is stripped silently

**When** the user runs `lore artifact list --filter /default/codex/`
**Then** the output equals the output of `lore artifact list --filter default/codex`, and exit code is 0.

#### Scenario 6: Empty token still errors

**When** the user runs `lore artifact list --filter ""`
**Then** stderr contains an empty-filter error message, exit code is non-zero, and no rows are printed.

#### Scenario 7: Breaking change — hyphen-delimited input no longer matches

**Given** an artifact at `.lore/artifacts/default/codex/overview.md`
**When** the user runs `lore artifact list --filter default-codex`
**Then** the `overview` row does NOT appear (hyphen form is no longer accepted as nested match), and exit code is 0. An artifact whose literal single segment equals `default-codex` would still match by exact segment.

#### Scenario 8: All five list commands accept the new grammar

**When** the user runs `lore doctrine list --filter <tok>`, `lore knight list --filter <tok>`, `lore watcher list --filter <tok>`, `lore artifact list --filter <tok>`, and `lore codex list --filter <tok>` — each seeded with one nested entity matching `<tok>` and one unrelated entity
**Then** each command returns only the matching nested entity plus root-group rows, and each exits 0.

### Unit Test Scenarios

- [ ] `lore.paths.group_matches_filter`: empty group `""` always matches (root inclusion rule)
- [ ] `lore.paths.group_matches_filter`: exact match — group `"a/b"` matches filter `["a/b"]`
- [ ] `lore.paths.group_matches_filter`: proper prefix — group `"a/b/c"` matches filter `["a/b"]`
- [ ] `lore.paths.group_matches_filter`: non-prefix — group `"a/b"` does NOT match filter `["a/c"]`
- [ ] `lore.paths.group_matches_filter`: bare substring — group `"technical/api"` does NOT match filter `["tech"]`
- [ ] `lore.paths.group_matches_filter`: trailing-slash token `"a/b/"` treated as `"a/b"`
- [ ] `lore.paths.group_matches_filter`: leading-slash token `"/a/b"` treated as `"a/b"`
- [ ] `lore.paths.group_matches_filter`: multi-token OR — group `"a/b"` matches filter `["z", "a"]`
- [ ] `lore.paths.group_matches_filter`: hyphen in a segment is preserved — group `"a-b/c"` matches filter `["a-b"]`, does NOT match filter `["a"]`
- [ ] `lore.cli` filter parsing: empty filter string raises the existing empty-filter error

---

## Out of Scope

- Display delimiter change (covered by US-006, US-007)
- Any non-group filter (name/status/other) — this story only changes the group-token grammar
- Quest and mission list commands — they have no group concept

---

## References

- PRD: `lore codex show group-param-prd`
- Tech Spec: `lore codex show group-param-tech-spec`
- Workflow: `lore codex show conceptual-workflows-filter-list`

---

## Tech Notes

### Implementation Approach

- `src/lore/paths.py` `group_matches_filter` (line ~59) — rewrite body to segment-prefix match on `/`. Pseudocode:

  ```python
  def group_matches_filter(group: str, filter_groups: list[str]) -> bool:
      if group == "":
          return True  # root always included, unchanged
      group_segs = group.split("/")
      for token in filter_groups:
          tok_segs = token.strip("/").split("/")
          if not tok_segs or tok_segs == [""]:
              continue  # defensive; empty token is rejected by CLI layer
          if group_segs[: len(tok_segs)] == tok_segs:
              return True
      return False
  ```
- Leading/trailing `/` stripping happens inside `group_matches_filter`; callers pass raw tokens. Empty-filter validation stays in `cli.py` where the existing error path already rejects empty strings — unchanged.
- Every list CLI handler already passes `filter_groups` straight through to the core list function; no CLI edits needed for Doctrine/Knight/Watcher/Artifact/Codex list. Codex goes through the same helper.

### Test File Locations

- Unit: `tests/unit/test_filter_subtree.py` (existing) — rewrite every assertion for the new segment-prefix semantics and add the hyphen-preservation and multi-token OR cases.
- E2E: `tests/e2e/test_filter_list.py` (existing) — add the scenario matrix across five list commands. Each list-specific e2e file (`test_doctrine_list.py` etc.) adds one filter scenario in its own file.

### Test Stubs

```python
# tests/unit/test_filter_subtree.py
# anchor: conceptual-workflows-filter-list

def test_root_group_always_matches():
    # AC unit: empty string group matches any filter (root inclusion rule)
    assert group_matches_filter("", ["a/b"]) is True

def test_exact_match():
    # AC unit: exact group/filter match
    assert group_matches_filter("a/b", ["a/b"]) is True

def test_proper_prefix_match():
    # AC unit: group is longer than token — token is a segment prefix
    assert group_matches_filter("a/b/c", ["a/b"]) is True

def test_non_prefix_rejected():
    # AC unit: different segment rejected
    assert group_matches_filter("a/b", ["a/c"]) is False

def test_bare_substring_rejected():
    # AC unit: partial segment string is not accepted
    assert group_matches_filter("technical/api", ["tech"]) is False

def test_trailing_slash_token_stripped():
    # AC unit: trailing slash treated as equivalent
    assert group_matches_filter("a/b", ["a/b/"]) is True

def test_leading_slash_token_stripped():
    # AC unit: leading slash treated as equivalent
    assert group_matches_filter("a/b", ["/a/b"]) is True

def test_multi_token_or():
    # AC unit: any token match wins
    assert group_matches_filter("a/b", ["z", "a"]) is True

def test_hyphen_in_segment_preserved():
    # AC unit: hyphens inside a segment are part of that segment
    assert group_matches_filter("a-b/c", ["a-b"]) is True
    assert group_matches_filter("a-b/c", ["a"]) is False
```

```python
# tests/e2e/test_filter_list.py
# anchor: conceptual-workflows-filter-list

def test_doctrine_filter_slash_delimited(runner, project_dir):
    # Scenario 1 — exact slash-delimited filter
    _seed_doctrine(project_dir, "seo-analysis/keyword-analysers", "ranker")
    _seed_doctrine(project_dir, "other", "foo")
    result = runner.invoke(main, ["doctrine", "list", "--filter", "seo-analysis/keyword-analysers"])
    assert result.exit_code == 0
    assert "ranker" in result.output
    assert "foo" not in result.output

def test_doctrine_filter_segment_prefix(runner, project_dir):
    # Scenario 2 — partial-path segment prefix
    _seed_doctrine(project_dir, "seo-analysis/keyword-analysers", "ranker")
    result = runner.invoke(main, ["doctrine", "list", "--filter", "seo-analysis"])
    assert result.exit_code == 0
    assert "ranker" in result.output

def test_doctrine_filter_bare_substring_no_match(runner, project_dir):
    # Scenario 3 — bare substring must not match a full segment
    _seed_doctrine(project_dir, "technical/api", "x")
    result = runner.invoke(main, ["doctrine", "list", "--filter", "tech"])
    assert result.exit_code == 0
    assert "x" not in result.output

def test_doctrine_filter_root_always_included(runner, project_dir):
    # Scenario 4 — root entities always appear regardless of filter
    _seed_doctrine(project_dir, "seo-analysis", "ranker")
    _seed_doctrine(project_dir, "", "flat")
    result = runner.invoke(main, ["doctrine", "list", "--filter", "seo-analysis"])
    assert result.exit_code == 0
    assert "ranker" in result.output
    assert "flat" in result.output

def test_artifact_filter_leading_trailing_slash_stripped(runner, project_dir):
    # Scenario 5 — leading/trailing / silently stripped
    _seed_artifact(project_dir, ".lore/artifacts/default/codex/overview.md", id="overview")
    a = runner.invoke(main, ["artifact", "list", "--filter", "/default/codex/"])
    b = runner.invoke(main, ["artifact", "list", "--filter", "default/codex"])
    assert a.exit_code == 0 and b.exit_code == 0
    assert a.output == b.output

def test_artifact_filter_empty_token_errors(runner, project_dir):
    # Scenario 6 — empty filter still errors (existing behaviour)
    result = runner.invoke(main, ["artifact", "list", "--filter", ""])
    assert result.exit_code != 0
    assert "empty" in result.stderr.lower() or "filter" in result.stderr.lower()

def test_artifact_filter_hyphen_no_longer_matches_nested(runner, project_dir):
    # Scenario 7 — breaking change: hyphen input no longer matches nested
    _seed_artifact(project_dir, ".lore/artifacts/default/codex/overview.md", id="overview")
    result = runner.invoke(main, ["artifact", "list", "--filter", "default-codex"])
    assert result.exit_code == 0
    assert "overview" not in result.output

@pytest.mark.parametrize("cmd", ["doctrine", "knight", "watcher", "artifact", "codex"])
def test_all_five_list_commands_accept_slash_filter(runner, project_dir, cmd):
    # Scenario 8 — grammar migration covers all five list commands
    _seed_nested_and_root(project_dir, cmd, token="a/b", nested_id="nested", root_id="root")
    result = runner.invoke(main, [cmd, "list", "--filter", "a/b"])
    assert result.exit_code == 0
    assert "nested" in result.output
    # Root rows always included
    assert "root" in result.output
```

### Complexity Estimate

**M** — core logic rewrite in `group_matches_filter`, full unit matrix flip, parametrised cross-entity e2e suite; logic is simple but the grammar break is user-visible so test coverage is wide.
