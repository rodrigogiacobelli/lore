---
id: conceptual-workflows-python-api
title: Python DB API Contracts
summary: 'What the Python DB API (lore.db) guarantees — return-type contracts, key
  presence on all code paths, error dicts instead of exceptions, and edge-case characterisation
  behaviours.

  '
related:
- tech-api-surface
- decisions-011-api-parity-with-cli
---

# Python DB API Contracts

`lore.db` exposes a set of public functions that the CLI and tests call directly. These functions have documented return-type contracts that callers rely on.

## General Conventions

### Error dicts, not exceptions

Mutating functions return a dict with at minimum an `"ok"` boolean key:

- `{"ok": True, ...}` on success.
- `{"ok": False, "error": "<message>", ...}` on failure.

Callers check `result["ok"]` before reading other fields. This avoids try/except at the CLI layer for predictable error conditions (entity not found, wrong status, etc.).

**Exception to this rule:** `create_quest` and `create_mission` raise `ValueError` or `RuntimeError` instead of returning error dicts. The CLI catches these explicitly.

### UTC timestamps

All timestamp fields are ISO 8601 strings with a `Z` suffix (e.g., `"2026-03-24T12:00:00Z"`). The helper `_now_utc()` produces this format.

### Key presence on all code paths

Every key documented in a success dict is always present, even when its value is `None`. For example:

```python
result = claim_mission(project_root, mission_id)
# result always has: ok, status, quest_status_changed, quest_id, quest_status, error
```

Callers must not use `.get("key", default)` as a substitute for checking `result["ok"]` — the key will always be there.

## Function Contracts

### `create_quest(...) -> str`

Returns the new quest ID string on success. Raises `ValueError` if a constraint is violated. Raises `RuntimeError` on ID collision.

### `create_mission(...) -> str`

Returns the new mission ID string. Raises `ValueError` if the specified `quest_id` does not exist. Raises `RuntimeError` on ID collision.

### `claim_mission(project_root, mission_id) -> dict`

```python
{"ok": True, "status": "in_progress", "quest_status_changed": bool, "quest_id": str|None, "quest_status": str|None}
{"ok": False, "error": str}
```

`quest_status_changed` is `True` when the parent quest's derived status changed as a result. Idempotent for `in_progress` missions (returns `ok=True, status="in_progress"`).

### `close_mission(project_root, mission_id) -> dict`

```python
{"ok": True, "status": "closed", "quest_closed": bool, "auto_close_note": str}
{"ok": False, "error": str}
```

`quest_closed` is `True` when auto-close triggered. Idempotent for already-closed missions.

### `add_dependency(project_root, from_id, to_id) -> dict`

```python
{"ok": True, "duplicate": bool, "closed_target": bool}
{"ok": False, "error": str}
```

`duplicate` is `True` when the dependency already existed. `closed_target` is `True` when `to_id` is already closed (no blocking occurs).

### `remove_dependency(project_root, from_id, to_id) -> dict`

```python
{"removed": True}
{"removed": False}
```

No `ok` key — callers check `result.get("removed", False)`.

### `add_board_message(project_root, entity_id, message, sender) -> dict`

```python
{"ok": True, "id": int, "entity_id": str, "sender": str|None, "created_at": str}
{"ok": False, "error": str}
```

### `delete_board_message(project_root, message_id) -> dict`

```python
{"ok": True, "id": int, "deleted_at": str}
{"ok": False, "error": str}
```

### `get_mission(project_root, mission_id) -> sqlite3.Row | None`

Returns `None` when the mission does not exist or is soft-deleted. Callers must check for `None`.

### `get_quest(project_root, quest_id) -> sqlite3.Row | None`

Returns `None` when the quest does not exist or is soft-deleted.

### `get_aggregate_stats(project_root) -> dict`

Always returns:

```python
{
    "quests": {"open": int, "in_progress": int, "closed": int},
    "missions": {"open": int, "in_progress": int, "blocked": int, "closed": int}
}
```

All status keys are always present even when their count is 0.

## Edge-Case Behaviours

- Claiming an `in_progress` mission: `ok=True`, no DB write, `quest_status_changed=False`.
- Closing an already-closed mission: `ok=True`, idempotent, no DB write.
- Blocking an already-`blocked` mission: `ok=False, error="Cannot block..."`.
- Adding a dependency where `to_id` is already closed: `ok=True, duplicate=False, closed_target=True`.
- `get_board_messages` for a non-existent entity: returns an empty list (no error).

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Missing `schema_version` in lore_meta | `RuntimeError` propagates | 1 |
| FK violation | `IntegrityError` propagates (caught by callers) | 1 |
| Cycle detection | `add_dependency` returns `{"ok": False, "error": ...}` | — |

## Out of Scope

- Async or connection-pooled access — all functions open, use, and close a connection synchronously.
- Typed Python objects — all query results use `sqlite3.Row` (dict-like access).
