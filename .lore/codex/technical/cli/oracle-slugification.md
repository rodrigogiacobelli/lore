---
id: tech-cli-oracle-slugification
title: Oracle Slugification Algorithm
summary: Two-stage slugification used by lore oracle to derive filesystem-safe filenames
  from entity IDs and titles. Covers slugify() (40-char slug portion) and make_entity_slug()
  (40-char combined {id}-{slug} result).
related:
- tech-oracle-internals
- tech-cli-commands
---

# Oracle Slugification Algorithm

**Source module:** `src/lore/oracle.py`

The `lore oracle` command generates a markdown report tree under `.lore/reports/`. Every quest subdirectory and every per-mission markdown file is named using a two-stage slugification algorithm implemented in `oracle.py`.

## Stage 1 — `slugify(title: str) -> str`

Converts a free-text title into a URL-friendly slug fragment.

**Algorithm:**

1. Lowercase the entire string.
2. Replace any run of non-alphanumeric characters (`[^a-z0-9]+`) with a single hyphen.
3. Collapse consecutive hyphens.
4. Strip leading and trailing hyphens.
5. If the result exceeds 40 characters, truncate to 40 characters then walk backwards to the last hyphen. If a hyphen exists before position 0, truncate there. Strip any trailing hyphen from the final result.

**Output:** A slug of at most 40 characters. The 40-character limit applies to the slug fragment alone, before the entity ID prefix is added.

**Example:**

```
slugify("My Long Quest Title Here")  →  "my-long-quest-title-here"
```

## Stage 2 — `make_entity_slug(entity_id: str, title: str) -> str`

Combines an entity ID with the slugified title to produce the final filesystem name: `{entity_id}-{title_slug}`.

**Algorithm:**

1. Call `slugify(title)` to obtain the slug fragment.
2. Concatenate: `combined = f"{entity_id}-{slug}"`.
3. If `combined` exceeds 40 characters, truncate to 40 characters, then walk backwards to the last hyphen. The walk-back only cuts at a hyphen that falls after the end of the entity ID prefix (guard: `last_hyphen > len(entity_id)`). Strip any trailing hyphen.

**Output:** A combined slug of at most 40 characters. The 40-character limit applies to the entire `{id}-{slug}` result, not to the slug fragment alone.

**Key distinction between Stage 1 and Stage 2:**

| Property | `slugify()` | `make_entity_slug()` |
|----------|-------------|----------------------|
| Input | Title string | Entity ID + title string |
| Output | Slug fragment | Full `{id}-{slug}` name |
| 40-char limit applies to | Slug fragment only | Full combined result |
| Walk-back guard | `last_hyphen > 0` | `last_hyphen > len(entity_id)` |

The guard in Stage 2 prevents the walk-back from cutting into the entity ID itself. If the only available hyphen is within the entity ID portion, the truncated string is kept as-is (minus any trailing hyphen), which may result in a partial slug fragment being appended.

## Usage in Report Generation

`make_entity_slug()` is called in two places within `generate_reports()`:

- **Quest directory names:** `make_entity_slug(quest["id"], quest["title"])` → directory under `.lore/reports/quests/`
- **Mission file names:** `make_entity_slug(m_part, mission["title"]) + ".md"` where `m_part` is the mission ID component after the `/` (e.g., `m-020c` from `q-fd95/m-020c`)

## Related

- tech-oracle-internals (lore codex show tech-oracle-internals) — full oracle.py module reference including `generate_reports()` and the wipe-and-recreate behaviour.
