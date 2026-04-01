---
id: codex-list-group-business-map
lens: business
feature: codex-list-group
title: Context Map — codex-list-group (business)
summary: Business-lens context map for the codex-list-group feature — fixing lore codex list output to include GROUP column and match other entity list commands.
---

# Context Map — codex-list-group (business)

**Author:** Scout (business lens)
**Date:** 2026-03-27
**Feature:** _Fix `lore codex list` to output ID, GROUP, TITLE, SUMMARY columns — matching the consistent four-column pattern used by all other entity list commands_
**Lens:** _business_

---

## Relevant Documents

| ID | Title | Why relevant |
|----|-------|-------------|
| `conceptual-workflows-codex` | Codex Commands — lore codex | Documents the current `lore codex list` behaviour: outputs ID, TYPE, TITLE, SUMMARY — missing the GROUP column. This is the primary workflow this feature changes. |
| `conceptual-workflows-knight-list` | lore knight list Behaviour | The gold standard for the target output format: ID, GROUP, TITLE, SUMMARY — this is what `lore codex list` should match. |
| `conceptual-workflows-doctrine-list` | lore doctrine list Behaviour | Another entity list command with the same ID, GROUP, TITLE, SUMMARY four-column output; demonstrates the expected pattern is consistent across entities. |
| `conceptual-workflows-artifact-list` | lore artifact list Behaviour | Artifact list uses ID, TYPE, GROUP, TITLE, SUMMARY (five columns); shows how GROUP is integrated across entity lists even when TYPE is also present. |
| `conceptual-workflows-watcher-list` | lore watcher list Behaviour | Watcher list also uses the ID, GROUP, TITLE, SUMMARY four-column format — confirms the pattern this feature targets. |
| `tech-cli-commands` | CLI Command Reference | Complete CLI reference: documents the current `lore codex list` output format, which will need updating to reflect the new GROUP column once this feature ships. |
| `tech-cli-entity-crud-matrix` | CLI Entity CRUD Matrix | Entity-to-command mapping; useful to confirm codex list is the only list command currently missing GROUP. |

---

## How to Use This Map

Every agent that receives this map should:
1. Run `lore codex show conceptual-workflows-codex conceptual-workflows-knight-list conceptual-workflows-doctrine-list conceptual-workflows-watcher-list tech-cli-commands` with all IDs in the table above
2. Read every document listed before starting their mission
3. Do not explore the codex independently — this map is your entry point

---

## Scout Notes

The inconsistency is clear: every entity list command (`lore knight list`, `lore doctrine list`, `lore watcher list`) outputs ID, GROUP, TITLE, SUMMARY. The `lore artifact list` command even includes GROUP alongside TYPE. Only `lore codex list` omits GROUP entirely and includes TYPE instead of GROUP — this is the UX gap this feature closes.

The feature adds GROUP to codex list output and drops TYPE from the default table view (while GROUP is derived from directory structure, TYPE remains available in JSON mode). The `conceptual-workflows-codex` document will need updating after implementation to reflect the new column layout.

The JSON schema for `lore codex list --json` currently has no `group` field; after this feature ships it should gain one, consistent with the `{"knights": [{..., "group": ...}]}` pattern.
