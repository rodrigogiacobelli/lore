---
id: conceptual-entities-quest
title: Quest
summary: What a Quest is — a live grouping of Missions representing a body of work (a feature, bug fix, refactor, or spike). Covers status derivation, the auto_close toggle, and edge cases for empty quests, reopening, and soft-delete.
related: ["conceptual-entities-mission", "conceptual-entities-doctrine", "tech-db-schema"]
stability: stable
---

# Quest

A Quest is a live grouping of Missions (lore codex show conceptual-entities-mission). It represents a body of work — a feature, a bug fix, a refactor, a research spike. Quests can be created ad-hoc or by an orchestrator following a Doctrine (lore codex show conceptual-entities-doctrine) as a guide.

A Quest is complete when all its Missions are closed. Quest status is automatically derived from its Missions — it is never set directly. See tech-db-schema (lore codex show tech-db-schema) for the derivation algorithm.

## Python API

`Quest` is exported from `lore.models` as a typed, immutable dataclass. Python consumers (including Realm) import it as:

```python
from lore.models import Quest, QuestStatus
```

All Quest fields are accessible by name: `id`, `title`, `description`, `status`, `priority`, `auto_close`, `created_at`, `updated_at`, `closed_at`, `deleted_at`. The `status` field holds a `QuestStatus` value (`QuestStatus.OPEN`, `QuestStatus.IN_PROGRESS`, or `QuestStatus.CLOSED`), not a plain string. The `auto_close` field holds a Python `bool` (not the raw `0`/`1` integer that the database stores). Optional timestamp fields (`closed_at`, `deleted_at`) hold `None` when unset.

Quest objects are immutable — attempting to assign to any field raises `FrozenInstanceError`.

## The `auto_close` Toggle

Each Quest has an `auto_close` setting that controls whether it closes automatically when all its Missions are done:

- **`auto_close` enabled:** The Quest closes automatically when all Missions are closed. No manual intervention is needed.
- **`auto_close` disabled (default for new Quests):** The Quest remains open even when all Missions are closed. It must be explicitly closed via `lore done q-xxxx`.

The default for new Quests is `auto_close` disabled. Use `--auto-close` at creation time or toggle it later with `lore edit`. See tech-cli-commands (lore codex show tech-cli-commands) for the flag details.

## Status Rules

- A Quest's status is derived from its Missions, not stored directly.
- A Quest with no Missions stays `open` indefinitely — there is nothing to trigger a close.
- If a new Mission is added to a `closed` Quest, the Quest reopens to `open` and its `closed_at` is cleared.
- A Quest with `auto_close` disabled and all Missions closed remains visible on the dashboard and in listings — this is intentional; the user opted out of auto-close.

## Mission List

`lore show <quest-id>` renders the quest's missions as a flat topologically-sorted list — parents always appear before children. Each mission line shows a status symbol, the short mission ID, the title, the mission type in brackets (omitted when no type is set), and any direct parent mission IDs after a `←` symbol (omitted when the mission has no parents). All `←` symbols are tab-aligned so they form a consistent right-hand column. Missions with no parents appear at the natural top of the topological sort. Cross-quest parents use fully-qualified IDs (`q-xxxx/m-xxxx`); intra-quest parents use short IDs (`m-xxxx`). Closed missions remain in the list — they are not hidden.

```
Missions:
○ m-0e36 Design auth schema [knight]
○ m-a6d0 Design dashboard UI [knight]         ← q-4f5a/m-0e36
○ m-d6b3 Implement dashboard API [knight]     ← m-a6d0, q-4f5a/m-8383
○ m-9501 Deploy dashboard [constable]         ← m-d6b3, q-4f5a/m-cdf7
```

Status symbols shown on each line:
- `●` — closed
- `◕` — in_progress or blocked
- `○` — open

In `--json` output, each mission object in the `"missions"` array includes a `"dependencies"` field with `"needs"` and `"blocks"` arrays (always present, even when empty). Each entry is an object with `"id"`, `"title"`, and `"status"`. IDs are always fully-qualified. Both arrays contain only direct neighbours — to traverse the full chain, read all missions in the array and follow their `"needs"`/`"blocks"` references.

## Board

A Quest may carry a **board** — an ordered list of operational notes scoped to the quest as a whole. Quest board messages are suited to context that applies across multiple missions: a phase completion announcement, a shared file path, or a key decision that all downstream workers should know about.

Board messages appear in `lore show <quest-id>` under a `Board:` section, positioned after the missions table, formatted one per line with a timestamp and optional sender:

```
Board:
  [2026-03-17T12:00:00Z] Phase 1 complete. All analysis artifacts produced.
  [2026-03-17T13:00:00Z] (q-a1b2/m-abc1) Shared config path: .lore/config/pipeline.yaml
```

When no active board messages exist, the `Board:` section is omitted entirely.

Key properties:

- **Quest board and mission board are independent.** A message posted to a quest's board does not appear in any of its missions' boards, and vice versa.
- **Append-only from the reader's perspective.** Messages are added with `lore board add <quest-id> "<message>"`. Replace a stale message by deleting it and posting a new one.
- **Optional sender.** A message may name its source using `--sender <lore-id>`. The sender is a Lore entity ID and is informational only — its existence is not verified.
- **Deletion is final from the reader's perspective.** `lore board delete <message-id>` removes a message immediately. Once deleted, it never reappears.
- **Board messages do not appear in list views.** They are visible only in `lore show`.

## Edge Cases

- **Empty Quest:** A Quest with no Missions stays `open`. It does not auto-close.
- **Adding Missions to a closed Quest:** The Quest reopens to `open`.
- **Manual close:** A Quest with `auto_close` disabled must be closed explicitly. Closing an already-closed Quest is a no-op (exit code 0).
- **Quest soft-delete:** Soft-deleting a Quest marks it deleted; it is excluded from all listings, dashboards, and status derivation. Without cascade, only the Quest row is marked deleted — its Missions remain active but are effectively orphaned (they retain their IDs and are still visible with a "(quest deleted)" annotation). With cascade, the Quest and all its Missions are soft-deleted, along with dependency rows referencing those Missions. Soft-deleted Quests cannot be restored via CLI.
- **All-missions-soft-deleted Quest:** When all Missions in a Quest are soft-deleted but the Quest itself is not, the Quest derives to `open` (empty Quest behaviour, since soft-deleted Missions are excluded). To close such a Quest, soft-delete it directly.

## Related

- Mission (lore codex show conceptual-entities-mission) — the individual tasks that belong to a Quest
- Doctrine (lore codex show conceptual-entities-doctrine) — the optional template an orchestrator follows when structuring a Quest
- tech-db-schema (lore codex show tech-db-schema) — quest status derivation algorithm and schema
- tech-cli-commands (lore codex show tech-cli-commands) — `lore new quest`, `lore done`, `lore edit`, `lore delete` command reference
