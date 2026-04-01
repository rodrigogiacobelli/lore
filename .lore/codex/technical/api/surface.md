---
id: tech-api-surface
title: Python API Entity CRUD Matrix
summary: Maps every Lore entity to its available Python API operations (lore.db, lore.codex, lore.artifact, lore.doctrine). Shows the function call for each CRUD and traversal operation and highlights gaps. Companion to tech-cli-entity-crud-matrix.
related: ["decisions-010", "decisions-011", "tech-cli-entity-crud-matrix", "tech-db-schema", "tech-arch-codex-map", "tech-arch-codex-chaos"]
stability: stable
---

# Python API Entity CRUD Matrix

Import root is `lore`. Typed models live in `lore.models`. All `lore.db` functions take `project_root: Path` as first argument; file-module functions take the relevant subdirectory path.

| Entity | Create | Read | List | Search | Traverse | Update | Delete |
|--------|--------|------|------|--------|----------|--------|--------|
| **Quest** | `lore.db.create_quest(root, title, ...)` → `str` | `lore.db.get_quest(root, id)` → `Row` | `lore.db.list_quests(root, include_closed)` → `list[Row]` | — | — | `lore.db.edit_quest(root, id, ...)` → `dict` | `lore.db.delete_quest(root, id, cascade)` → `dict` |
| **Mission** | `lore.db.create_mission(root, title, ...)` → `str` — note: quest inference (if exactly one open quest exists, assign it) has been moved to `cli.py`; calling with `quest_id=None` creates a standalone mission with no automatic assignment | `lore.db.get_mission(root, id)` → `Row` | `lore.db.list_missions(root, quest_id, include_closed)` → `dict[quest_id, list[Row]]` | — | — | `lore.db.edit_mission(root, id, ...)` → `dict` | `lore.db.delete_mission(root, id)` → `dict` |
| **Knight** | — | `lore.knight.find_knight(knights_dir, name)` → `Path \| None` | `lore.knight.list_knights(knights_dir)` → `list[dict]` — dict keys: `id`, `group`, `title`, `summary`, `name`, `filename` | — | — | — | — |
| **Doctrine** | — | `lore.doctrine.load_doctrine(filepath)` → `dict` | `lore.doctrine.list_doctrines(doctrines_dir)` → `list[dict]` — dict keys: `id`, `group`, `title`, `summary`, `name`, `filename`, `description`, `valid`, (optionally `errors`) | — | — | — | — |
| **Watcher** | `lore.watcher.create_watcher(watchers_dir, name, content)` → `dict` | `lore.watcher.find_watcher(watchers_dir, name)` → `Path \| None`, then `lore.watcher.load_watcher(filepath)` → `dict` | `lore.watcher.list_watchers(watchers_dir)` → `list[dict]` | — | — | `lore.watcher.update_watcher(watchers_dir, name, content)` → `dict` | `lore.watcher.delete_watcher(watchers_dir, name)` → `dict` |
| **Codex** | ✗ | `lore.codex.read_document(codex_dir, id)` → `dict` | `lore.codex.scan_codex(codex_dir)` → `list[dict]` | `lore.codex.search_documents(codex_dir, keyword)` → `list[dict]` | `lore.codex.map_documents(codex_dir, start_id, depth)` → `list[dict] | None`<br>`lore.codex.chaos_documents(codex_dir, start_id, threshold, rng=None)` → `list[dict] | None` | ✗ | ✗ |
| **Artifact** | ✗ | `lore.artifact.read_artifact(artifacts_dir, id)` → `dict` | `lore.artifact.scan_artifacts(artifacts_dir)` → `list[dict]` | — | — | ✗ | ✗ |
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
Doctrine.from_dict(load_doctrine(path))
DoctrineListEntry.from_dict(d)     # from list_doctrines() — enriched: id, group, title, summary, name, filename, description, valid, errors
Knight(name=path.stem, content=path.read_text())   # use lore.knight.find_knight(knights_dir, name) to locate the file first
Watcher.from_dict(load_watcher(path))   # or Watcher.from_dict(list_watchers(dir)[i])
```

**Knight hydration:** Use `lore.knight.find_knight(knights_dir, name)` to locate the file. Do not glob `.lore/knights/**/*.md` directly. `find_knight` returns `Path | None` (not found) and raises `ValueError` on path-traversal attempts (names containing `/` or `\\`).

**Watcher hydration:** Use `lore.watcher.find_watcher(watchers_dir, name)` to locate the file. `find_watcher` returns `Path | None` (not found) and raises `ValueError` on path-traversal attempts.

## Gaps

| Entity | Missing | Notes |
|--------|---------|-------|
| **Doctrine** | Create, Update, Delete | CLI-only write path. |
| **Codex** | Create, Update, Delete | No write functions in any module. |
| **Artifact** | Create, Update, Delete | Read-only by design. |
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
