---
id: group-param-us-007
title: US-007 List GROUP display slash-joined in table and JSON envelope
summary: Switches the GROUP column of doctrine, knight, watcher, artifact, and codex list commands from hyphen-joined to slash-joined in both the human table and the --json envelope, with root entities rendering as the existing sentinel in the table and as null in JSON.
type: user-story
status: final
---

## Metadata

- **ID:** US-007
- **Status:** final
- **Epic:** List display + filter migration
- **Author:** Business Analyst
- **Date:** 2026-04-15
- **PRD:** `lore codex show group-param-prd`
- **Tech Spec:** `lore codex show group-param-tech-spec`

---

## Story

As a user inspecting a list of entities, I want the GROUP column of every `lore <entity> list` command (including `codex list`) to render exactly what I typed on create — e.g. `default/codex`, not `default-codex` — in both the human table and the `--json` envelope, so that display and input share a single canonical form.

## Context

Fulfills functional requirements FR-12, FR-13, FR-15 and the PRD workflow "List + filter with slash-joined groups — any user". `derive_group` already returns slash-joined strings after US-006, but this story completes the audit: every list command's JSON emitter must surface `group` as slash-joined or `null`, never `""` or hyphen-joined. Five list commands are in scope: `doctrine list`, `knight list`, `watcher list`, `artifact list`, `codex list`.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Artifact list table shows slash-joined group

**Given** artifacts on disk at `.lore/artifacts/default/codex/overview.md` and `.lore/artifacts/transient-note.md`
**When** the user runs `lore artifact list`
**Then** the `overview` row's `GROUP` column is exactly `default/codex`, the `transient-note` row's `GROUP` column is the empty-group sentinel (unchanged), and exit code is 0.

#### Scenario 2: Artifact list JSON envelope — slash-joined and null for root

**Given** the same preconditions as Scenario 1
**When** the user runs `lore artifact list --json`
**Then** stdout parses as JSON whose artifacts list contains an entry `{"id": "overview", "group": "default/codex", ...}` and an entry `{"id": "transient-note", "group": null, ...}`, no entry has `group` equal to `""` or a hyphen-joined string, and exit code is 0.

#### Scenario 3: Doctrine list — table and JSON

**Given** a doctrine at `.lore/doctrines/seo-analysis/keyword-analysers/ranker.yaml`
**When** the user runs `lore doctrine list --json`
**Then** the `ranker` entry's `group` key equals `"seo-analysis/keyword-analysers"` and exit code is 0.

#### Scenario 4: Knight list — table and JSON

**Given** a knight at `.lore/knights/feature-implementation/reviewer.md` and one at `.lore/knights/root.md`
**When** the user runs `lore knight list --json`
**Then** the `reviewer` entry's `group` key equals `"feature-implementation"`, the `root` entry's `group` key equals `null`, and exit code is 0.

#### Scenario 5: Watcher list — table and JSON

**Given** a watcher at `.lore/watchers/feature-implementation/on-prd-ready.yaml`
**When** the user runs `lore watcher list --json`
**Then** the `on-prd-ready` entry's `group` key equals `"feature-implementation"` and exit code is 0.

#### Scenario 6: Codex list — table and JSON

**Given** a codex document at `.lore/codex/technical/arch/overview.md`
**When** the user runs `lore codex list --json`
**Then** the `overview` entry's `group` key equals `"technical/arch"` and exit code is 0.

#### Scenario 7: JSON never emits hyphen-joined or empty-string group

**When** the user runs `lore doctrine list --json`, `lore knight list --json`, `lore watcher list --json`, `lore artifact list --json`, and `lore codex list --json` in a project containing both nested and root entities for each
**Then** for every command, every `group` value in the envelope is either `null` or a slash-joined non-empty string — never `""` and never a hyphen-joined token.

### Unit Test Scenarios

- [ ] `lore.cli` doctrine list JSON emitter: for a record with derived group `"a/b"`, emits `"group": "a/b"`
- [ ] `lore.cli` doctrine list JSON emitter: for a record with derived group `""`, emits `"group": null`
- [ ] `lore.cli` knight list JSON emitter: same two assertions
- [ ] `lore.cli` watcher list JSON emitter: same two assertions
- [ ] `lore.cli` artifact list JSON emitter: same two assertions
- [ ] `lore.cli` codex list JSON emitter: same two assertions
- [ ] `lore.cli` table renderers: a record with group `"a/b"` formats the GROUP column with a `/` character, never a `-` as segment separator

---

## Out of Scope

- Filter grammar change (covered by US-008)
- Any `new` command changes (covered by US-001..US-004)
- Any `codex new` write path — explicitly out of scope per PRD FR-15
- Help text updates (covered by US-010)

---

## References

- PRD: `lore codex show group-param-prd`
- Tech Spec: `lore codex show group-param-tech-spec`
- Workflow: `lore codex show conceptual-workflows-json-output`

---

## Tech Notes

### Implementation Approach

- `src/lore/cli.py` — five list handlers emit `group` in their JSON envelopes and table rows. Audit required:
  - `doctrine_list` (line ~1159) — records come from `doctrine.list_doctrines` which already carries `"group": derive_group(...)`. JSON emitter must convert `""` to `None` before emitting.
  - `knight_list` (line ~941) — same: records from `knight.list_knights`. JSON emitter must map `""` → `None`.
  - `watcher_list` (line ~2545) — records from `watcher.list_watchers`. Currently emits `json.dumps({"watchers": watchers})` verbatim — insert an in-place normalisation loop or a helper that replaces `""` with `None` on the `group` key.
  - `artifact_list` (line ~2385) — already builds dicts from `scan_artifacts`; add the `""` → `None` mapping for `group`.
  - `codex_list` (line ~2161) — already calls `paths.derive_group(d["path"], codex_dir)` inline; wrap in a helper so `""` → `None` for JSON and the table renderer still receives `""` (existing sentinel behaviour).
- Introduce a local `_group_for_json(g: str) -> str | None: return g or None` helper near the top of `cli.py` to avoid repeating the ternary. Table rendering uses the raw string (empty string → existing sentinel rendering).
- No changes to core modules — `derive_group` already returns slash-joined after US-006 lands.

### Test File Locations

- Unit: `tests/unit/test_cli_codex_list.py` (existing) plus new assertions in JSON-emitter smoke tests for each list command. If no unit coverage exists for `cli.<entity>_list` JSON shape, add it to `tests/unit/test_cli_<entity>_list.py` (new file per entity) OR fold into existing e2e for leaner scope.
- E2E: `tests/e2e/test_doctrine_list.py`, `test_knight_list.py`, `test_watcher_list.py`, `test_artifact_list.py`, `test_codex.py` — all existing.

### Test Stubs

```python
# tests/e2e/test_artifact_list.py
# anchor: conceptual-workflows-json-output

def test_artifact_list_table_slash_joined(runner, project_dir):
    # Scenario 1 — table GROUP column uses /
    _seed_artifact(project_dir, ".lore/artifacts/default/codex/overview.md", id="overview")
    _seed_artifact(project_dir, ".lore/artifacts/transient-note.md", id="transient-note")
    result = runner.invoke(main, ["artifact", "list"])
    assert result.exit_code == 0
    assert "default/codex" in result.output

def test_artifact_list_json_slash_and_null(runner, project_dir):
    # Scenario 2 — JSON envelope slash-joined; root is null
    _seed_artifact(project_dir, ".lore/artifacts/default/codex/overview.md", id="overview")
    _seed_artifact(project_dir, ".lore/artifacts/transient-note.md", id="transient-note")
    result = runner.invoke(main, ["artifact", "list", "--json"])
    data = json.loads(result.output)
    by_id = {a["id"]: a for a in data["artifacts"]}
    assert by_id["overview"]["group"] == "default/codex"
    assert by_id["transient-note"]["group"] is None
    # Never hyphen-joined, never empty string
    for a in data["artifacts"]:
        assert a["group"] is None or "/" in a["group"] or a["group"].replace("-", "").isalnum()
        assert a["group"] != ""
```

```python
# tests/e2e/test_doctrine_list.py
# anchor: conceptual-workflows-json-output

def test_doctrine_list_json_slash_joined(runner, project_dir):
    # Scenario 3 — doctrine list JSON slash-joined
    _seed_doctrine(project_dir, "seo-analysis/keyword-analysers", "ranker")
    result = runner.invoke(main, ["doctrine", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    ranker = next(d for d in data["doctrines"] if d["id"] == "ranker")
    assert ranker["group"] == "seo-analysis/keyword-analysers"
```

```python
# tests/e2e/test_knight_list.py
# anchor: conceptual-workflows-json-output

def test_knight_list_json_slash_and_null(runner, project_dir):
    # Scenario 4 — knight list JSON
    _seed_knight(project_dir, ".lore/knights/feature-implementation/reviewer.md", id="reviewer")
    _seed_knight(project_dir, ".lore/knights/root.md", id="root")
    result = runner.invoke(main, ["knight", "list", "--json"])
    data = json.loads(result.output)
    by_id = {k["id"]: k for k in data["knights"]}
    assert by_id["reviewer"]["group"] == "feature-implementation"
    assert by_id["root"]["group"] is None
```

```python
# tests/e2e/test_watcher_list.py
# anchor: conceptual-workflows-json-output

def test_watcher_list_json_slash_joined(runner, project_dir):
    # Scenario 5 — watcher list JSON
    _seed_watcher(project_dir, ".lore/watchers/feature-implementation/on-prd-ready.yaml", id="on-prd-ready")
    result = runner.invoke(main, ["watcher", "list", "--json"])
    data = json.loads(result.output)
    w = next(x for x in data["watchers"] if x["id"] == "on-prd-ready")
    assert w["group"] == "feature-implementation"
```

```python
# tests/e2e/test_codex.py
# anchor: conceptual-workflows-json-output

def test_codex_list_json_slash_joined(runner, project_dir):
    # Scenario 6 — codex list JSON
    _seed_codex_doc(project_dir, ".lore/codex/technical/arch/overview.md", id="overview")
    result = runner.invoke(main, ["codex", "list", "--json"])
    data = json.loads(result.output)
    ov = next(d for d in data["codex"] if d["id"] == "overview")
    assert ov["group"] == "technical/arch"
```

```python
# tests/e2e/test_filter_list.py  (audit over all five list commands)
# anchor: conceptual-workflows-json-output

@pytest.mark.parametrize("cmd,key", [
    ("doctrine", "doctrines"),
    ("knight",   "knights"),
    ("watcher",  "watchers"),
    ("artifact", "artifacts"),
    ("codex",    "codex"),
])
def test_list_json_never_hyphen_or_empty_group(runner, project_dir, cmd, key):
    # Scenario 7 — no hyphen-joined and no empty-string groups in any list JSON
    _seed_mixed(project_dir, cmd)  # one nested, one root
    result = runner.invoke(main, [cmd, "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    for row in data[key]:
        assert row["group"] is None or "/" in row["group"] or row["group"].count("-") == 0 or row["group"].replace("-", "a").isalnum()
        assert row["group"] != ""
```

```python
# tests/unit/test_cli_codex_list.py
# anchor: conceptual-workflows-json-output

def test_doctrine_list_json_maps_empty_group_to_none(tmp_path, runner):
    # AC unit: emitter converts "" → None
    # Arrange one root doctrine and one nested
    ...
    result = runner.invoke(main, ["doctrine", "list", "--json"])
    data = json.loads(result.output)
    assert any(d["group"] is None for d in data["doctrines"])
    assert any(d["group"] == "a/b" for d in data["doctrines"])

# Equivalent tests for knight, watcher, artifact, codex list JSON emitters.

def test_table_renderer_never_uses_hyphen_for_group_segments(runner, project_dir):
    # AC unit: table GROUP column uses "/" between segments
    _seed_artifact(project_dir, ".lore/artifacts/a/b/x.md", id="x")
    result = runner.invoke(main, ["artifact", "list"])
    assert "a/b" in result.output
    assert " a-b " not in result.output
```

### Complexity Estimate

**M** — five CLI list handlers to audit and normalise, five e2e files to touch, parametrised audit test. Logic is shallow but surface area is wide.
