---
id: conceptual-workflows-claim
title: lore claim Behaviour
summary: What the system does internally when `lore claim <mission-id>` runs — ID format validation, status transition open→in_progress, idempotency on already-in_progress missions, parent quest status recomputation, and multi-mission batch support.
related: ["conceptual-workflows-ready", "conceptual-workflows-done", "conceptual-entities-mission"]
stability: stable
---

# `lore claim` Behaviour

`lore claim <mission-id> [<mission-id> ...]` transitions one or more missions from `open` to `in_progress`. It is **idempotent** for missions already in `in_progress` status. It rejects missions that are in any other status (`closed`, `blocked`).

The command accepts one or more mission IDs in a single invocation. All IDs are processed; failures on individual IDs do not prevent processing of subsequent IDs.

## Preconditions

- The Lore project has been initialised.
- Each provided ID must match the mission ID format: `q-<hex>/m-<hex>` or standalone `m-<hex>`.
- The mission must exist in the database and not be soft-deleted.
- The mission status must be `open` or `in_progress` (idempotent).

## Steps

### 1. Validate the mission ID format

Each mission ID is validated against the expected pattern before any database access. If the ID does not match the pattern, the error is printed to stderr and processing continues with the next ID.

### 2. Load the mission from the database

The mission is fetched from `lore.db` by ID within a `BEGIN IMMEDIATE` transaction. If the mission is not found, an error is returned for that ID and the transaction is rolled back.

### 3. Check current status

- **`in_progress`:** The mission is already claimed. The command treats this as success (idempotent) — no database write is performed, and the transaction is rolled back cleanly. The output line for this mission reads `<id>: in_progress`.
- **`open`:** The valid transition. Proceed to step 4.
- Any other status (`closed`, `blocked`): the command aborts this mission's transition with error `Cannot claim mission "<id>": status is <status>`. Exit code 1.

### 4. Update the mission status

Within the transaction, the mission's `status` is set to `in_progress` and `updated_at` is set to the current UTC timestamp.

### 5. Recompute parent quest status

If the mission belongs to a quest, the quest's derived status is recomputed based on the statuses of all its missions. If the quest status changes as a result (e.g. from `open` to `in_progress`), this change is tracked and reported in JSON mode.

### 6. Commit and report

The transaction is committed. The output line for a successfully claimed mission reads:

```
<id>: in_progress
```

## Multi-Mission Behaviour

When multiple IDs are provided:
- Each ID is processed independently.
- Failures on individual IDs produce errors to stderr but do not stop processing.
- If any ID failed, the exit code is 1 after all IDs are processed.
- If all IDs succeeded (or were already `in_progress`), exit code is 0.

## Failure Modes

| Failure point | Message (stderr) | Exit code |
|---|---|---|
| Invalid ID format | Validation error message | 1 |
| Mission not found | `Mission "<id>" not found` | 1 |
| Status is `closed` | `Cannot claim mission "<id>": status is closed` | 1 |
| Status is `blocked` | `Cannot claim mission "<id>": status is blocked` | 1 |
| Already `in_progress` | _(no error — idempotent success)_ | 0 |

## JSON Mode

When the global `--json` flag is set:

```json
{
  "updated": ["q-xxxx/m-yyyy"],
  "quest_status_changed": [{"id": "q-xxxx", "status": "in_progress"}],
  "errors": []
}
```

`updated` contains the IDs of successfully transitioned missions. `quest_status_changed` lists quests whose derived status changed. `errors` lists error strings for failed IDs. If any errors occurred, exit code is 1.

## Out of Scope

- Validating that the claimed mission has no unresolved dependencies — claiming is permitted regardless of whether dependencies are complete. The dependency system is advisory and influences the ready queue, not claim eligibility.
- Assigning a knight on claim — knights are assigned at mission creation time.

## Related

- conceptual-workflows-done (lore codex show conceptual-workflows-done) — the complementary closure step
- conceptual-workflows-block (lore codex show conceptual-workflows-block) — blocking a mission in progress
- conceptual-entities-mission (lore codex show conceptual-entities-mission) — full mission status lifecycle
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
