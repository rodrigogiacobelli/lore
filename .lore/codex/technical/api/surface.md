---
id: tech-api-surface
title: Python API Entity CRUD Matrix
summary: Maps every Lore entity to its available Python API operations (lore.db, lore.codex, lore.artifact, lore.doctrine). Shows the function call for each CRUD and traversal operation and highlights gaps. Companion to tech-cli-entity-crud-matrix.
related: ["decisions-010-public-api-stability", "decisions-011-api-parity-with-cli", "tech-cli-entity-crud-matrix", "tech-db-schema", "tech-arch-codex-map", "tech-arch-codex-chaos", "conceptual-workflows-health", "standards-facade", "standards-public-api-stability", "conceptual-workflows-python-api", "tech-arch-schemas"]
---

# Python API Entity CRUD Matrix

Import root is `lore`. Typed models live in `lore.models`. All `lore.db` functions take `project_root: Path` as first argument; file-module functions take the relevant subdirectory path.

| Entity | Create | Read | List | Search | Traverse | Update | Delete |
|--------|--------|------|------|--------|----------|--------|--------|
| **Quest** | `lore.db.create_quest(root, title, ...)` → `str` | `lore.db.get_quest(root, id)` → `Row` | `lore.db.list_quests(root, include_closed)` → `list[Row]` | — | — | `lore.db.edit_quest(root, id, ...)` → `dict` | `lore.db.delete_quest(root, id, cascade)` → `dict` |
| **Mission** | `lore.db.create_mission(root, title, ...)` → `str` — note: quest inference (if exactly one open quest exists, assign it) has been moved to `cli.py`; calling with `quest_id=None` creates a standalone mission with no automatic assignment | `lore.db.get_mission(root, id)` → `Row` | `lore.db.list_missions(root, quest_id, include_closed)` → `dict[quest_id, list[Row]]` | — | — | `lore.db.edit_mission(root, id, ...)` → `dict` | `lore.db.delete_mission(root, id)` → `dict` |
| **Knight** | `lore.knight.create_knight(knights_dir, name, content, *, group=None)` → `dict` | `lore.knight.find_knight(knights_dir, name)` → `Path \| None` | `lore.knight.list_knights(knights_dir, filter_groups=None)` → `list[dict]` — dict keys: `id`, `group`, `title`, `summary`, `name`, `filename` | — | — | — | — |
| **Doctrine** | `lore.doctrine.create_doctrine(name, yaml_source_path, design_source_path, doctrines_dir, *, group=None)` → `dict` | `lore.doctrine.show_doctrine(id, doctrines_dir)` → `dict` — keys: `id`, `title`, `summary`, `design` (raw str), `raw_yaml` (raw str), `steps` (list) | `lore.doctrine.list_doctrines(doctrines_dir, filter_groups=None)` → `list[dict]` — dict keys: `id`, `group`, `title`, `summary`, `filename`, `valid` (always True; orphaned entries skipped) | — | — | — | — |
| **Watcher** | `lore.watcher.create_watcher(watchers_dir, name, content, *, group=None)` → `dict` | `lore.watcher.find_watcher(watchers_dir, name)` → `Path \| None`, then `lore.watcher.load_watcher(filepath)` → `dict` | `lore.watcher.list_watchers(watchers_dir, filter_groups=None)` → `list[dict]` | — | — | `lore.watcher.update_watcher(watchers_dir, name, content)` → `dict` | `lore.watcher.delete_watcher(watchers_dir, name)` → `dict` |
| **Codex** | ✗ | `lore.codex.read_document(codex_dir, id)` → `dict` | `lore.codex.scan_codex(codex_dir, filter_groups=None)` → `list[dict]` | `lore.codex.search_documents(codex_dir, keyword)` → `list[dict]` | `lore.codex.map_documents(codex_dir, start_id, depth)` → `list[dict] | None`<br>`lore.codex.chaos_documents(codex_dir, start_id, threshold, rng=None)` → `list[dict] | None` | ✗ | ✗ |
| **Artifact** | `lore.artifact.create_artifact(artifacts_dir, name, content, *, group=None)` → `dict` | `lore.artifact.read_artifact(artifacts_dir, id)` → `dict` | `lore.artifact.scan_artifacts(artifacts_dir, filter_groups=None)` → `list[dict]` | — | — | ✗ | ✗ |
| **Board Message** | `lore.db.add_board_message(root, entity_id, message, sender)` → `dict` | `lore.db.get_board_messages(root, entity_id)` → `list[dict]` | same as Read | — | — | ✗ (immutable) | `lore.db.delete_board_message(root, message_id)` → `dict` |

### `add_board_message` return shapes

| Path | Return dict |
|------|-------------|
| Success | `{"ok": True, "id": int, "entity_id": str, "sender": str \| None, "created_at": str}` |
| Empty or whitespace-only message | `{"ok": False, "error": "Message cannot be empty"}` |
| Entity not found (or soft-deleted) | `{"ok": False, "error": "Quest \"q-xxxx\" not found"}` or `"Mission \"q-xxxx/m-yyyy\" not found"` |

Validation lives exclusively in `lore.db.add_board_message`. The CLI handler calls `add_board_message` and formats the `{"ok": False}` result without pre-checking.

## Lifecycle Operations

| Operation | Quest | Mission |
|-----------|-------|---------|
| Close | `lore.db.close_quest(root, id)` | `lore.db.close_mission(root, id)` |
| Claim | — | `lore.db.claim_mission(root, id)` |
| Block | — | `lore.db.block_mission(root, id, reason)` |
| Unblock | — | `lore.db.unblock_mission(root, id)` |
| Top unblocked | — | `lore.priority.get_ready_missions(root, count)` — note: `db.get_ready_missions` was removed in the ADR-012 refactor (REFACTOR-9); it was a pass-through wrapper with no purpose |

### `close_mission` return shapes

`close_mission(root, id)` always includes `quest_id` in the return dict. `quest_id` is the string ID of the parent quest, or `None` for standalone missions.

| Path | Return dict |
|------|-------------|
| Success — quest auto-closed | `{"ok": True, "status": "closed", "error": None, "quest_closed": True, "quest_id": str}` |
| Success — quest not closed | `{"ok": True, "status": "closed", "error": None, "quest_closed": False, "quest_id": str \| None}` |
| Already closed (idempotent) | `{"ok": True, "status": "closed", "error": None, "quest_closed": False, "quest_id": None}` |
| Not found | `{"ok": False, "status": None, "error": "Mission \"...\" not found", "quest_closed": False, "quest_id": None}` |

### `claim_mission` return shapes

`claim_mission(root, id)` includes quest status change information in the return dict so callers do not need follow-up queries to detect a quest transitioning from `open` to `in_progress`.

| Path | Return dict |
|------|-------------|
| Success — quest status changed | `{"ok": True, "status": "in_progress", "error": None, "quest_id": str, "quest_status_changed": True, "quest_status": "in_progress"}` |
| Success — quest status unchanged | `{"ok": True, "status": "in_progress", "error": None, "quest_id": str \| None, "quest_status_changed": False, "quest_status": str \| None}` |
| Already in progress (idempotent) | `{"ok": True, "status": "in_progress", "error": None, "quest_id": None, "quest_status_changed": False, "quest_status": None}` |
| Not found | `{"ok": False, "status": None, "error": "Mission \"...\" not found", "quest_id": None, "quest_status_changed": False, "quest_status": None}` |
| Invalid transition | `{"ok": False, "status": str, "error": "Cannot claim ...", "quest_id": None, "quest_status_changed": False, "quest_status": None}` |

`quest_id` and `quest_status` are `None` for standalone missions (missions not attached to a quest).

## Dependency Operations (Mission only)

| Operation | Function |
|-----------|----------|
| Add | `lore.db.add_dependency(root, from_id, to_id)` |
| Remove | `lore.db.remove_dependency(root, from_id, to_id)` |
| What does this mission need? | `lore.db.get_mission_depends_on(root, id)` → `list[str]` |
| What does this mission block? | `lore.db.get_mission_blocks(root, id)` → `list[str]` |

## Model Hydration

All `lore.db` functions return raw `sqlite3.Row` objects. Wrap them with typed models from `lore.models`:

```python
from lore.models import Quest, Mission, BoardMessage, Artifact, CodexDocument
from lore.models import Doctrine, DoctrineListEntry, Knight, Watcher

Quest.from_row(row)
Mission.from_row(row)
BoardMessage.from_dict(d)          # from get_board_messages()
Artifact.from_dict(d)              # from read_artifact() only — not scan_artifacts()
CodexDocument.from_dict(d)         # from scan_codex() or read_document()
Doctrine.from_dict(show_doctrine(id, doctrines_dir))   # from show_doctrine() — keys: id, title, summary, steps
DoctrineListEntry.from_dict(d)     # from list_doctrines() — keys: id, group, title, summary, filename, valid
Knight(name=path.stem, content=path.read_text())   # use lore.knight.find_knight(knights_dir, name) to locate the file first
Watcher.from_dict(load_watcher(path))   # or Watcher.from_dict(list_watchers(dir)[i])
```

**Knight hydration:** Use `lore.knight.find_knight(knights_dir, name)` to locate the file. Do not glob `.lore/knights/**/*.md` directly. `find_knight` returns `Path | None` (not found) and raises `ValueError` on path-traversal attempts (names containing `/` or `\\`).

**Watcher hydration:** Use `lore.watcher.find_watcher(watchers_dir, name)` to locate the file. `find_watcher` returns `Path | None` (not found) and raises `ValueError` on path-traversal attempts.

## `group=` kwarg on entity `create_*` helpers

Every entity create helper accepts `group: str | None = None` as a keyword-only argument. The kwarg is validated internally via `lore.validators.validate_group` — CLI and Python API behaviour are strictly identical per ADR-011 (API parity with CLI).

| Helper | Signature | Return dict gains |
|--------|-----------|-------------------|
| `lore.doctrine.create_doctrine` | `(name, yaml_source_path, design_source_path, doctrines_dir, *, group=None) -> dict` | `group` (str\|None), `path` (str) |
| `lore.knight.create_knight` | `(knights_dir, name, content, *, group=None) -> dict` | `group` (str\|None), `path` (str) |
| `lore.watcher.create_watcher` | `(watchers_dir, name, content, *, group=None) -> dict` | `group` (str\|None), `path` (str) |
| `lore.artifact.create_artifact` | `(artifacts_dir, name, content, *, group=None) -> dict` | `group` (str\|None), `path` (str) |

Contract:

- `group=None` places the entity at the entity root (unchanged default behaviour for existing callers).
- `group="<slash/delimited/path>"` places the entity at `base_dir / Path(group)` after `mkdir(parents=True, exist_ok=True)`.
- Invalid group (`..`, backslash, absolute path, leading/trailing `/`, empty segment, bad-char segment) raises the entity's exception (`DoctrineError` for doctrines, `ValueError` for knight/watcher/artifact).
- Duplicate-name detection is subtree-wide via `rglob` on the entity root, regardless of group.
- The returned `group` value is slash-joined in memory (or `None`). JSON envelopes that wrap these dicts emit `None` as `null`.

Every `list_*` / `scan_*` function gains a `filter_groups: list[str] | None = None` keyword argument in lock-step. Passing `None` (the default) returns all entities — existing callers are unaffected. Passing a list applies slash-delimited segment-prefix matching via `paths.group_matches_filter` on each record's slash-joined `group`.

## Diagnostic Operations

```python
from lore.models import health_check, HealthReport, HealthIssue
from pathlib import Path

report: HealthReport = health_check(project_root=Path("."), scope=None)
report: HealthReport = health_check(project_root=Path("."), scope=["codex"])
report: HealthReport = health_check(project_root=Path("."), scope=["doctrines", "watchers"])
```

`health_check(project_root, scope=None)` audits all file-based entity types AND validates every entity file's shape against its JSON Schema (or a subset when `scope` is provided, including the new `"schemas"` scope). Returns a `HealthReport`. Never prints to stdout or stderr.

Valid `scope` tokens: `"codex"`, `"artifacts"`, `"doctrines"`, `"knights"`, `"watchers"`, `"schemas"`. Passing `scope=None` runs every scope including `"schemas"`.

### Schema Validation Helpers

```python
from lore.models import load_schema, validate_entity_file
from pathlib import Path

schema = load_schema("knight")  # dict (cached per-process)
issues = validate_entity_file(Path(".lore/knights/default/feature-implementation/pm.md"), "knight")
for issue in issues:
    print(issue.schema_id, issue.rule, issue.pointer, issue.detail)
```

`load_schema(kind)` returns the cached parsed schema dict for a kind. Raises `FileNotFoundError` for unknown kinds. Kinds: `"doctrine-yaml"`, `"doctrine-design-frontmatter"`, `"knight"`, `"watcher"`, `"codex"`, `"artifact"`.

`validate_entity_file(path, kind)` returns a list of `HealthIssue` records (empty on success). Each issue has `check="schema"`, `severity="error"`, and populated `schema_id` / `rule` / `pointer` fields. The function is self-contained — it opens the file, parses YAML or frontmatter as appropriate for the kind, and runs the validator. Callable from Realm with zero CLI-layer side effects (ADR-011).

Both `load_schema` and `validate_entity_file` are in `lore.models.__all__`.

### `HealthReport` fields

| Field | Type | Description |
|-------|------|-------------|
| `errors` | `tuple[HealthIssue, ...]` | All error-severity issues |
| `warnings` | `tuple[HealthIssue, ...]` | All warning-severity issues |
| `has_errors` | `bool` (property) | `True` if `errors` is non-empty |
| `issues` | `tuple[HealthIssue, ...]` (property) | All issues — errors then warnings |

### `HealthIssue` fields

| Field | Type | Description |
|-------|------|-------------|
| `severity` | `str` | `"error"` or `"warning"` |
| `entity_type` | `str` | `"codex"`, `"artifacts"`, `"doctrines"`, `"knights"`, `"watchers"`, or one of the schema kinds (`"doctrine-yaml"`, `"doctrine-design-frontmatter"`, `"knight"`, `"watcher"`, `"codex"`, `"artifact"`) |
| `id` | `str` | Entity ID, or filepath string when ID is unknown (schema errors always use a repo-relative path) |
| `check` | `str` | Check name: `"broken_related_link"`, `"missing_frontmatter"`, `"island_node"`, `"orphaned_file"`, `"broken_knight_ref"`, `"broken_artifact_ref"`, `"missing_file"`, `"broken_doctrine_ref"`, `"invalid_yaml"`, `"scan_failed"`, `"schema"` |
| `detail` | `str` | Human-readable explanation |
| `schema_id` | `str \| None` | For `check="schema"`: the `lore://schemas/<kind>` URI. `None` for every other check. |
| `rule` | `str \| None` | For `check="schema"`: the failing JSON-Schema keyword (`"required"`, `"additionalProperties"`, `"type"`, `"enum"`, ...) or one of the special rules `"yaml-parse"`, `"missing-frontmatter"`, `"read-failed"`. `None` for every other check. |
| `pointer` | `str \| None` | For `check="schema"`: JSON-Pointer to the failing node (e.g. `"/stability"`, `"/"`). `None` for every other check. |

Both `HealthIssue` and `HealthReport` are frozen dataclasses in `lore.models.__all__`. `HealthIssue.from_dict(d)` is provided for round-tripping JSON output and accepts dicts with or without the three schema fields — legacy payloads produced before the schema validation feature continue to round-trip.

## Gaps

| Entity | Missing | Notes |
|--------|---------|-------|
| **Doctrine** | Update, Delete | `create_doctrine()` now accepts `group=None`. Update and delete remain CLI-only (Post-MVP). |
| **Knight** | Update, Delete | `create_knight()` introduced this release (extracted from `cli.py`; accepts `group=None`). Update and delete remain CLI-only. |
| **Codex** | Create, Update, Delete | No write functions in any module. List display and filter grammar switch to slash-delimited form in lock-step. |
| **Artifact** | Update, Delete | `create_artifact()` introduced this release (first artifact write path; accepts `group=None`). Update and delete remain on-disk. |
| **Quest / Mission** | Search | No full-text search in `lore.db`. |
| **Dependency** | `Dependency.from_row()` | Model exists but no `lore.db` function returns a full dep row yet. Use `get_mission_depends_on_details()` / `get_mission_blocks_details()` instead. |

**Note on `_read_related`:** `_read_related(filepath, index)` in `codex.py` is a private helper used internally by `map_documents` and the bidirectional adjacency pre-pass in `chaos_documents`. It is not part of the public API surface and should not be called directly.

### `chaos_documents` Notes

`chaos_documents(codex_dir, start_id, threshold, rng=None)` returns `None` when
`start_id` is not found (same contract as `map_documents`). On success, each dict
has keys `id`, `title`, `summary`.

The `rng` parameter accepts any object with a `.choice()` method; defaults to the
`random` module. Pass `random.Random(seed)` for reproducible results in tests.

`validate_chaos_threshold` in `lore.validators` enforces the 30–100 range;
`chaos_documents` raises `ValueError` on invalid input. `cli.py` also enforces
the range via `click.IntRange(min=30, max=100)` per ADR-011.
