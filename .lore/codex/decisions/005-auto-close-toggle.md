---
id: "005"
title: "auto_close toggle on quests"
summary: "ADR recording the decision to add a per-quest auto_close toggle, defaulting to disabled for new quests. Covers the schema design, migration default split, and the mechanism for manually closing quests."
related: ["tech-db-schema", "tech-cli-commands", "conceptual-entities-quest"]
stability: stable
---

# ADR 005 — auto_close Toggle on Quests

## Context

Before this decision, Lore unconditionally derived a quest's status as `closed` when all its missions were closed. There was no opt-out mechanism. This caused friction in real-world usage:

- Quests closed automatically before an orchestrator had a chance to review the completed work.
- There was no CLI mechanism to close a quest explicitly; `lore done` only accepted mission IDs.
- Quests with `auto_close` disabled (once introduced) needed a manual close path.

The all-round improvements spec (D-4, `docs/specs/all-round-improvements.md`, now archived) introduced a per-quest toggle to address this.

The design required two related choices:

1. **Schema default:** what should `auto_close` default to for new quests?
2. **Migration default:** what should existing quests (created before this column existed) get?

These two defaults intentionally differ.

## Decision

An `auto_close INTEGER NOT NULL DEFAULT 0 CHECK (auto_close IN (0, 1))` column is added to the `quests` table.

- **New quests default to `auto_close = 0`** (auto-close disabled). The orchestrator must explicitly close a quest with `lore done q-xxxx` when it is satisfied with the completed work.
- **Existing quests (via migration v2 to v3) default to `auto_close = 1`** (auto-close enabled). This preserves the behaviour those quests were created under, avoiding surprising existing users.
- **`lore new quest`** accepts `--auto-close` (set to 1) and `--no-auto-close` (default, set to 0).
- **`lore edit q-xxxx`** accepts `--auto-close` and `--no-auto-close` to change the toggle on an existing quest.
- **`lore done q-xxxx`** is extended to accept quest IDs, providing the explicit close path for quests with `auto_close = 0`.
- **`lore show q-xxxx`** displays the `auto_close` value in both human-readable and JSON output.

When `auto_close = 0` and all missions complete, `_derive_quest_status()` returns the next applicable non-closed status (`in_progress` if any mission was in progress, otherwise `open`). The quest remains visible on the dashboard until explicitly closed.

## Rationale

**Why default new quests to `auto_close = 0`:**

In an agent-driven workflow, a quest completing silently is a loss of a review checkpoint. The orchestrator should decide when a quest is done, not have that decision made automatically. `auto_close = 0` is the safer default: the orchestrator retains control. The `--auto-close` flag is available for cases where automatic closure is desired.

**Why the migration default differs from the schema default:**

Existing quests were created under the assumption of auto-close. Changing their behaviour retroactively would break running workflows. The migration applies `DEFAULT 1` to preserve existing behaviour. Fresh databases use `schema.sql` with `DEFAULT 0`, which applies to all quests created after this feature ships.

This is a deliberate default split, not an inconsistency.

**Why extend `lore done` to accept quest IDs:**

Without an explicit close mechanism, quests with `auto_close = 0` could never be closed through the CLI. Extending `lore done` is consistent with existing patterns: the ID routing mechanism already distinguishes quest IDs (`q-xxxx`) from mission IDs (`q-xxxx/m-yyyy`). No new command is needed.

**Cross-platform rename safety:**

The AGENTS.md backup behaviour introduced in the same spec (D-2) uses `Path.replace()` rather than `Path.rename()` because `rename()` raises `FileExistsError` on Windows when the destination exists. `replace()` is atomic and cross-platform. This is noted here because the two decisions shipped together and the rationale is documented in the same source spec.

## Alternatives Rejected

**Keep unconditional auto-close; no toggle.** Rejected because it removes the orchestrator's ability to review completed quests before they disappear from the active dashboard. Real-world agent usage demonstrated that silent auto-close caused quests to vanish before review was complete.

**Default new quests to `auto_close = 1` (maintain existing default).** Rejected because it perpetuates the behaviour that motivated the change. The deliberate default change to `0` signals that explicit close is the recommended practice for new quests.

**Separate `lore close quest` command.** Rejected in favour of extending `lore done`. The `done` command already expresses "this work is finished." Adding a separate verb for the same semantic action on a different entity type would increase the command surface unnecessarily. ID routing (already in place) handles the dispatch.

**Quest `blocked` status.** Rejected. Quest status remains `open`, `in_progress`, `closed`. Quest-level blocking is not added — blocking is a mission-level concept. Quests reflect the aggregate status of their missions; a quest does not independently block.

**Content-diffing for customized default files (D-3 scope).** Rejected in favour of unconditional overwrite. Users who customise default files should use different filenames. Diffing and merging user customisations adds complexity that is not warranted for the use case.
