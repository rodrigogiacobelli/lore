---
id: conceptual-workflows-done
title: lore done Behaviour
summary: What the system does internally when `lore done <id>` runs — missions transition
  any non-closed status to closed, dependents are cascade-unblocked, parent quest
  auto-close logic fires, and quests can also be closed directly. Idempotent for already-closed
  entities.
related:
- conceptual-entities-mission
- conceptual-entities-quest
- conceptual-workflows-claim
- conceptual-workflows-block
---

# `lore done` Behaviour

`lore done <id> [<id> ...]` closes one or more missions or quests. For **missions**, any non-closed status transitions to `closed`, dependents are cascade-unblocked, and the parent quest's derived status is recomputed (potentially auto-closing the quest). For **quests**, the quest is directly closed regardless of mission statuses. The command is **idempotent** — passing an already-closed ID is not an error.

The command accepts a mix of mission IDs and quest IDs in a single invocation. An ID that starts with `q-` and contains no `/` is treated as a quest ID; all other valid-format IDs are treated as mission IDs.

## Preconditions

- The Lore project has been initialised.
- Each ID must be a valid mission ID (`q-<hex>/m-<hex>` or `m-<hex>`) or a quest ID (`q-<hex>`).
- The entity must exist in the database.

## Steps — Mission Closure

### 1. Validate the mission ID format

The ID is validated against the mission ID pattern. Malformed IDs produce an error to stderr and are skipped.

### 2. Load the mission

The mission is fetched within a `BEGIN IMMEDIATE` transaction. If not found, an error is returned and the transaction is rolled back.

### 3. Check current status

- **`closed`:** Already done. The command treats this as success (idempotent) — no database write, transaction rolled back cleanly. The output line reads `<id>: closed`.
- **Any other status** (`open`, `in_progress`, `blocked`): proceed to step 4. Any non-closed status can transition directly to `closed`.

### 4. Update the mission

Within the transaction:
- `status` is set to `closed`
- `block_reason` is set to `NULL` (cleared if the mission was previously blocked)
- `closed_at` and `updated_at` are set to the current UTC timestamp

### 5. Cascade: auto-unblock dependents

After closing the mission, any missions that had this mission as a `needs` dependency are re-evaluated. If a blocked mission's only remaining blocker was this mission, it transitions from `blocked` back to `open`. (This is handled by `_derive_quest_status` which recomputes all mission statuses within the quest.)

### 6. Recompute parent quest status (with potential auto-close)

If the mission belongs to a quest, the quest's derived status is recomputed. If the quest has `auto_close = true` and all missions in the quest are now `closed`, the quest is automatically closed. The output line in this case reads:

```
<id>: closed (quest auto-closed)
```

Otherwise the output line reads:

```
<id>: closed
```

## Steps — Quest Closure

Quest closure does not check or modify individual mission statuses. The quest is closed directly regardless of whether its missions are all done. This is intended for quests with `auto_close` disabled that need explicit closure.

- If the quest is already closed, the output reads `<id>: already closed`.
- If the quest is successfully closed, the output reads `<id>: closed (closed_at: <timestamp>)`.

## Multi-Entity Behaviour

Same as `lore claim`: each entity is processed independently; failures on individual IDs do not stop processing; overall exit code is 1 if any entity failed.

## Failure Modes

| Failure point | Message (stderr) | Exit code |
|---|---|---|
| Invalid mission ID format | Validation error message | 1 |
| Mission not found | `Mission "<id>" not found` | 1 |
| Quest not found | Quest-specific error message | 1 |
| Already closed | _(no error — idempotent success)_ | 0 |

## JSON Mode

When the global `--json` flag is set:

```json
{
  "updated": ["q-xxxx/m-yyyy"],
  "quest_closed": ["q-xxxx"],
  "errors": []
}
```

`updated` contains IDs of all successfully closed entities (missions and quests). `quest_closed` lists quest IDs that were auto-closed as a result of mission closure. `errors` lists error strings for failed IDs.

## Out of Scope

- Closing all missions in a quest at once — each mission must be closed individually.
- Partial closure — there is no concept of partial completion.

## Related

- conceptual-workflows-claim (lore codex show conceptual-workflows-claim) — the preceding step in the typical mission lifecycle
- conceptual-workflows-block (lore codex show conceptual-workflows-block) — blocking a mission rather than closing it
- conceptual-entities-mission (lore codex show conceptual-entities-mission) — full mission status lifecycle and auto-unblock rules
- conceptual-entities-quest (lore codex show conceptual-entities-quest) — quest status rules and auto_close behaviour
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
