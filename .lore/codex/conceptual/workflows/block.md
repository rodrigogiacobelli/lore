---
id: conceptual-workflows-block
title: lore block Behaviour
summary: What the system does internally when `lore block <mission-id> <reason>` runs
  — ID format validation, status transition open/in_progress→blocked, reason string
  storage, parent quest status recomputation, and the complementary unblock path.
related:
- conceptual-entities-mission
- conceptual-workflows-claim
- conceptual-workflows-done
---

# `lore block` Behaviour

`lore block <mission-id> <reason>` transitions a mission from `open` or `in_progress` to `blocked`, storing a mandatory reason string. Only `open` and `in_progress` missions can be blocked — `closed` and already-`blocked` missions cannot. The command accepts exactly one mission ID per invocation (unlike `lore claim` and `lore done`, which accept multiple IDs).

## Preconditions

- The Lore project has been initialised.
- The mission ID must match the mission ID format.
- The reason argument is required and must be non-empty (enforced by CLI argument parsing).
- The mission must exist in the database.
- The mission status must be `open` or `in_progress`.

## Steps

### 1. Validate the mission ID format

The ID is validated against the mission ID pattern before any database access. If invalid, an error is printed to stderr and the command exits with code 1.

### 2. Load the mission

The mission is fetched within a `BEGIN IMMEDIATE` transaction. If not found, an error is returned and the transaction is rolled back.

### 3. Check current status

- **`open`:** Valid transition. Proceed to step 4.
- **`in_progress`:** Valid transition. Proceed to step 4.
- **`closed`:** Rejected. Error: `Cannot block mission "<id>": status is closed`. Exit code 1.
- **`blocked`:** Rejected. Error: `Cannot block mission "<id>": status is blocked`. Exit code 1.

### 4. Update the mission

Within the transaction:
- `status` is set to `blocked`
- `block_reason` is set to the provided reason string
- `updated_at` is set to the current UTC timestamp

### 5. Recompute parent quest status

If the mission belongs to a quest, the quest's derived status is recomputed to reflect the blocked mission.

### 6. Commit and report

The transaction is committed. The output reads:

```
<id>: blocked
```

## Unblocking

The reverse operation is `lore unblock <mission-id>`. It transitions `blocked` → `open`, clears the `block_reason`, and recomputes the parent quest status. Only `blocked` missions can be unblocked; attempting to unblock a mission in any other status fails with `Cannot unblock mission "<id>": status is <status>`.

## Failure Modes

| Failure point | Message (stderr) | Exit code |
|---|---|---|
| Invalid ID format | Validation error message | 1 |
| Mission not found | `Mission "<id>" not found` | 1 |
| Status is `closed` | `Cannot block mission "<id>": status is closed` | 1 |
| Status is `blocked` | `Cannot block mission "<id>": status is blocked` | 1 |

## JSON Mode

When the global `--json` flag is set, success output (to stdout):

```json
{"id": "<id>", "status": "blocked", "block_reason": "<reason>"}
```

Error output is written to stderr:

```json
{"error": "<message>"}
```

Exit code 1 on error.

## Out of Scope

- Bulk blocking of multiple missions in one command — use separate `lore block` invocations.
- Automatically blocking dependents — blocking a mission does not propagate to missions that depend on it.
- Time-based unblocking — there is no scheduled auto-unblock.

## Related

- conceptual-workflows-claim (lore codex show conceptual-workflows-claim) — transitioning open → in_progress
- conceptual-workflows-done (lore codex show conceptual-workflows-done) — transitioning any status → closed
- conceptual-entities-mission (lore codex show conceptual-entities-mission) — full mission status lifecycle
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
