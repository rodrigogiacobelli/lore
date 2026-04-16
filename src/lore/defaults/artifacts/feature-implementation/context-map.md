---
id: fi-context-map
title: Context Map
summary: Template for the Scout to produce a context map for a feature. Identifies
  all relevant codex documents from one lens (business or technical). Used twice per
  feature cycle — once per Scout. Mandatory input for all planning agents.
---

# Context Map — {Feature Name} ({lens: business|technical})

**Author:** Scout ({lens} lens)
**Date:** {date}
**Feature:** _{one-line feature description}_
**Lens:** _{business | technical}_

---

## Relevant Documents

| ID | Title | Why relevant |
|----|-------|-------------|
| `{codex-id-1}` | {title} | _{Specific reason — e.g. "Contains the user workflow this feature extends", "Defines the schema for the table being modified"}_ |
| `{codex-id-2}` | {title} | _{Specific reason}_ |
| `{codex-id-3}` | {title} | _{Specific reason}_ |

> Add one row per relevant document. The "why relevant" column must be specific enough that a downstream agent knows exactly why to read it.

---

## How to Use This Map

Every agent that receives this map should:
1. Run `lore codex show <id1> <id2> ...` with all IDs in the table above
2. Read every document listed before starting their mission
3. Do not explore the codex independently — this map is your entry point

---

## Scout Notes

_{Any observations about gaps, ambiguities, or areas where the codex may need updating after this feature ships. Not instructions — observations.}_
