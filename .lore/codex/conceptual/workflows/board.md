---
id: conceptual-workflows-board
title: Board Messages
summary: >
  What the system does internally when posting, viewing, and deleting board messages on missions and quests, including sender validation and error paths.
related: ["conceptual-workflows-show", "conceptual-workflows-mission-crud", "tech-cli-commands", "decisions-009-mission-self-containment"]
stability: stable
---

# Board Messages

Board messages are the handoff mechanism between agents. `lore board add <entity-id> <message>` posts a message to a quest or mission. `lore board delete <message-id>` removes a message. Messages appear in `lore show` output for the corresponding entity.

## Preconditions

- The Lore project has been initialised.
- For `board add`: the entity ID must be a valid quest or mission ID; the entity must exist and not be soft-deleted; the message must be non-empty.
- For `board delete`: the integer message ID must exist and not already be soft-deleted.

## Steps — Add (`lore board add <entity-id> <message>`)

### 1. Validate entity ID format

`add_board_message` in `lore.db` calls `validate_entity_id`, which accepts `q-<hex>`, `m-<hex>`, or `q-<hex>/m-<hex>`. An invalid format returns `{"ok": False, "error": ...}` without any database access.

### 2. Validate message content

`validate_message` checks that the message is non-empty and not pure whitespace. An empty message returns `{"ok": False, "error": "Message cannot be empty."}`.

### 3. Route entity to table

`route_entity` maps `q-<hex>` to the `quests` table and mission IDs to the `missions` table.

### 4. Verify entity existence

The entity is queried with `deleted_at IS NULL`. If not found, the call returns `{"ok": False, "error": '<Label> "<id>" not found'}`.

### 5. Insert the message

The row is inserted into `board_messages` with `entity_id`, `message`, `sender` (may be NULL), and an auto-assigned SQLite `id` (integer primary key). `created_at` is set by the DB default (UTC timestamp).

### 6. Report

Text: `Board message posted (id: <N>).`

JSON:

```json
{
  "id": 1,
  "entity_id": "q-xxxx/m-yyyy",
  "sender": "m-zzzz",
  "created_at": "2026-03-24T12:00:00Z"
}
```

## Optional Sender

The `--sender / -s` option attaches a sender identifier (free-form string, typically a mission ID) to the message. No validation is applied to the sender value — it is stored as-is.

## Steps — Delete (`lore board delete <message-id>`)

### 1. Soft-delete

`delete_board_message` in `lore.db` runs `UPDATE board_messages SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL`. If no row was updated (the message does not exist or was already deleted), it returns `{"ok": False, "error": "Board message <N> not found."}`.

### 2. Report

Text: `Board message <N> deleted.`

JSON: `{"id": <N>, "deleted_at": "..."}`.

## Display in `lore show`

Board messages are fetched by `get_board_messages` (oldest first, `deleted_at IS NULL`) and rendered in the output of `lore show <quest-id>` and `lore show <mission-id>`.

Text format per message:

```
  [<created_at>] (<sender>) <message>
```

The `(<sender>)` part is omitted when `sender` is NULL.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Invalid entity ID format | Error to stderr | 1 |
| Empty or whitespace message | Error to stderr | 1 |
| Entity not found or soft-deleted | Error to stderr | 1 |
| Message ID not found (delete) | Error to stderr | 1 |
| Message already deleted (delete) | `rowcount == 0` → error to stderr | 1 |

## Out of Scope

- Editing an existing board message — there is no update path; delete and re-add instead.
- Listing all board messages globally across entities.
