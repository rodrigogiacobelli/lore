---
id: conceptual-entities-mission
title: Mission
summary: What a Mission is — the unit of work an agent executes and closes. Covers
  the free-form mission type field, the status state machine, and edge cases including
  orphaned missions and soft-delete.
related:
- conceptual-entities-quest
- conceptual-entities-glossary
- tech-db-schema
- conceptual-workflows-claim
- conceptual-workflows-done
- conceptual-relationships-mission--mission
- conceptual-workflows-dependencies
---

# Mission

A Mission is an individual task within a Quest (lore codex show conceptual-entities-quest). It is the unit of work that an agent picks up, executes, and closes. Missions are persistent — they stay in the record with their full history even after completion.

A Mission has a **title**, a **description**, and an optional **type**. The description is the critical field — it must contain everything the worker agent needs to know about *what* to do. The orchestrator is responsible for writing thorough descriptions. In principle, the description alone should be sufficient to complete the work.

Missions can also exist standalone (not belonging to any Quest).

## Python API

`Mission` is exported from `lore.models` as a typed, immutable dataclass. Python consumers (including Realm) import it as:

```python
from lore.models import Mission, MissionStatus
```

All Mission fields are accessible by name: `id`, `quest_id`, `title`, `description`, `status`, `mission_type`, `priority`, `knight`, `block_reason`, `created_at`, `updated_at`, `closed_at`, `deleted_at`. The `status` field holds a `MissionStatus` value (`MissionStatus.OPEN`, `MissionStatus.IN_PROGRESS`, `MissionStatus.BLOCKED`, or `MissionStatus.CLOSED`), not a plain string. Optional fields (`quest_id`, `mission_type`, `knight`, `block_reason`, `closed_at`, `deleted_at`) hold `None` when unset.

Mission objects are immutable — attempting to assign to any field raises `FrozenInstanceError`.

## Mission Types

A Mission may carry a `mission_type` — a short label that classifies the work according to the team's own vocabulary. Lore stores and exposes this value but does not interpret it or change behaviour based on it. What the label means, and how an orchestrator or consuming tool should act on it, is entirely up to the team.

There is no fixed set of permitted values. Teams use whatever labels fit their process: `knight`, `constable`, `human`, `review`, `approval`, `spike`, `qa`, or anything else. The field is optional — a Mission with no type set is equally valid, and is simply displayed without a type bracket.

When a type is set, it appears in brackets in listings and the ready queue (for example `[review]`), and as a `Type:` line in the mission detail view. When no type is set, these display elements are omitted entirely.

Status transitions, dependencies, blocking, and closing work identically regardless of whether a type is set.

## Status State Machine

A Mission moves through the following statuses:

| Transition | Trigger |
|---|---|
| `open` → `in_progress` | `lore claim` |
| `open` → `blocked` | `lore block` |
| `open` → `closed` | `lore done` |
| `in_progress` → `closed` | `lore done` |
| `in_progress` → `blocked` | `lore block` |
| `blocked` → `open` | `lore unblock` |
| `blocked` → `closed` | `lore done` |

**`closed` is terminal.** Closed Missions cannot be reopened. If a Mission was closed in error, create a new Mission — this preserves the historical record.

`lore done` accepts Missions in any non-closed status and moves them directly to `closed`, clearing any block reason. This avoids requiring a separate `lore unblock` call before closing.

Unblocking always returns a Mission to `open`, regardless of its previous status. If the Mission was `in_progress` before being blocked, the claim is cleared and the orchestrator must re-claim after unblocking.

`block_reason` is set by `lore block` and cleared by both `lore unblock` and `lore done`.

## Board

A Mission may carry a **board** — an ordered list of operational notes left by predecessor agents or the orchestrator. Board messages are the mechanism by which one pipeline step passes dynamic context (a file path, an ID, a decision) to the next step without requiring the orchestrator to edit the Mission description after dispatch.

Board messages appear in `lore show <mission-id>` under a `Board:` section, formatted one per line with a timestamp and optional sender:

```
Board:
  [2026-03-17T10:00:00Z] (q-a1b2/m-abc1) Analysis artifact at .lore/codex/specs/mission-board.md
  [2026-03-17T11:00:00Z] Ready to implement
```

When no active board messages exist, the `Board:` section is omitted entirely — the output stays clean.

Key properties:

- **Append-only from the reader's perspective.** Messages are added with `lore board add <mission-id> "<message>"`. There is no edit command; replace a stale message by deleting it and posting a new one.
- **Optional sender.** A message may name its source using `--sender <lore-id>`. The sender is a Lore entity ID (a mission or quest) and is informational only — its existence is not verified.
- **Deletion is final from the reader's perspective.** `lore board delete <message-id>` removes a message from the board immediately. Once deleted, it never reappears.
- **Board messages are mission-scoped.** A message posted to a mission's board does not appear on its parent quest's board, and vice versa.
- **Board messages do not appear in list views.** They are visible only in `lore show`.

## Dependencies

A Mission's dependency context is visible directly in `lore show <mission-id>` under a `Dependencies:` section. The section has two flat sub-sections — `Needs:` (direct upstream missions this mission depends on) and `Blocks:` (direct downstream missions that depend on this one). Only direct neighbours are shown. Each entry is a status symbol, mission ID, and title on one line.

```
Dependencies:
  Needs:
    ● q-4f5a/m-0e36 Design auth schema
    ○ q-4f5a/m-8383 Write auth tests
  Blocks:
    ○ m-d6b3 Implement dashboard API
```

Status symbols:
- `●` — closed
- `◕` — in_progress or blocked
- `○` — open

Intra-quest dependencies use short IDs (`m-xxxx`); cross-quest dependencies use fully-qualified IDs (`q-xxxx/m-xxxx`). Closed dependencies remain visible with the `●` symbol. A sub-section (`Needs:` or `Blocks:`) is omitted when it has no entries. The entire `Dependencies:` section is omitted when the mission has no dependencies in either direction.

In `--json` output, the `"dependencies"` field is always present with `"needs"` and `"blocks"` arrays, even when empty. Each array entry is an object with `"id"`, `"title"`, and `"status"` fields. Both arrays contain only direct neighbours — to traverse a full chain, use `lore show <quest-id> --json` where all missions are present with their direct deps.

`lore show` is the single command for reading dependency information. There is no separate dependency-inspection command.

## Edge Cases

- **Orphaned Missions:** If a Mission's Quest has been soft-deleted (without cascade), the Mission remains active but its parent is no longer visible. It is shown with a "(quest deleted)" annotation.
- **Mission soft-delete:** Soft-deleting a Mission marks it deleted, removes it from all listings, dashboards, ready queue, and stats, and re-derives the parent Quest's status. Dependency rows referencing the Mission are also marked deleted. Soft-deleted Missions cannot be restored via CLI.
- **Knight file missing:** If a Mission references a Knight (lore codex show conceptual-entities-knight) that no longer exists on disk, `lore show` displays the Mission normally and appends a warning. The Mission remains fully functional.

## Related

- Quest (lore codex show conceptual-entities-quest) — the grouping that Missions belong to
- Knight (lore codex show conceptual-entities-knight) — the persona file that guides how a worker executes a Mission
- Doctrine (lore codex show conceptual-entities-doctrine) — templates that describe patterns of Missions
- tech-db-schema (lore codex show tech-db-schema) — mission schema, cascade behaviour, dependency system
- tech-cli-commands (lore codex show tech-cli-commands) — `lore claim`, `lore done`, `lore block`, `lore unblock`, `lore new mission` command reference
