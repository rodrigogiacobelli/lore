---
id: tech-oracle-internals
title: Oracle Module Internals
summary: Technical reference for src/lore/oracle.py. Documents the generate_reports()
  entry point, the wipe-and-recreate behaviour (shutil.rmtree on every run — a destructive
  operation), per-quest and per-mission file generation, and the make_entity_slug()
  naming scheme.
related:
- tech-cli-oracle-slugification
- tech-cli-commands
- tech-db-schema
---

# Oracle Module Internals

**Source module:** `src/lore/oracle.py`
**Module size:** 203 lines

This module implements `lore oracle` — the human-readable markdown report generator. It writes a report tree under `.lore/reports/`.

## WARNING: Wipe-and-Recreate Behaviour

**Every invocation of `lore oracle` deletes the entire `.lore/reports/` directory before regenerating it.**

The relevant code in `generate_reports()`:

```python
if reports_dir.exists():
    shutil.rmtree(reports_dir)
reports_dir.mkdir(parents=True)
```

This means:
- Any manual edits made to files under `.lore/reports/` are permanently lost on the next `lore oracle` run.
- Any files added to `.lore/reports/` by external tools are permanently lost.
- There is no backup, no diff, and no confirmation prompt.

The reports directory is **not** a safe place to store anything. Treat it as a generated artefact that is always overwritten.

This behaviour is not configurable and is documented in `lore oracle --help` and in this internals reference.

## Public Interface

### `generate_reports(project_root: Path) -> None`

Entry point. Called by the `lore oracle` CLI command.

**What it does:**

1. Computes `reports_dir` via `paths.reports_dir(project_root)` from `src/lore/paths.py`
   (equivalent to `project_root / ".lore" / "reports"`). As of the ADR-012 refactor,
   `oracle.py` obtains this path via `paths.reports_dir` rather than inline construction.
   The behaviour is unchanged.
2. **Deletes `reports_dir` if it exists** (see warning above).
3. Recreates `reports_dir`.
4. Writes `reports_dir / "summary.md"` via `_write_summary()`.
5. Calls `list_quests(project_root, include_closed=True)` to get all quests.
6. For each quest that has at least one mission:
   - Creates `reports_dir / "quests" / {quest_slug}/` where `quest_slug = make_entity_slug(quest["id"], quest["title"])`.
   - Writes `index.md` in that directory via `_write_quest_index()`.
   - For each mission in the quest, writes a per-mission `.md` file via `_write_mission_file()`.
7. Calls `list_missions(project_root, include_closed=True)` and processes standalone missions (those with `quest_id = None`):
   - Creates `reports_dir / "missions" /` directory.
   - Writes one `.md` file per standalone mission via `_write_mission_file()`.

**Database imports:** `get_aggregate_stats`, `get_mission_blocks`, `get_mission_depends_on`, `get_missions_for_quest`, `list_missions`, `list_quests` — all imported from `lore.db` at function call time (deferred import inside the function body).

**Quests with no missions are skipped.** No directory or index file is created for them.

## Slugification

See tech-cli-oracle-slugification (lore codex show tech-cli-oracle-slugification) for the full two-stage algorithm.

Summary of usage within `generate_reports()`:

| Usage | Call | 40-char limit applies to |
|-------|------|--------------------------|
| Quest directory name | `make_entity_slug(quest["id"], quest["title"])` | Full `{quest_id}-{slug}` |
| Quest-scoped mission filename | `make_entity_slug(m_part, mission["title"]) + ".md"` where `m_part` is the ID component after `/` | Full `{m_part}-{slug}` |
| Standalone mission filename | `make_entity_slug(mission_id, mission["title"]) + ".md"` | Full `{mission_id}-{slug}` |

For quest-scoped missions, `m_part` is derived by splitting on `/`: `mission_id.split("/")[-1]` — this strips the `q-xxxx/` prefix and leaves just `m-yyyy`.

## Report File Formats

### `summary.md`

Written by `_write_summary(path, stats)`. Contains two markdown tables: quest counts by status (open / in_progress / closed) and mission counts by status (open / in_progress / blocked / closed).

### Quest `index.md`

Written by `_write_quest_index(path, quest, missions)`. Contains:
- H1 heading with quest title
- Quest ID, status, and priority
- Quest description
- A markdown table listing all missions with columns: ID, Title, Status, Priority, Type, Knight

### Per-mission `.md` file

Written by `_write_mission_file(path, mission, depends_on, blocks)`. Contains:
- H1 heading with mission title
- Mission ID, status, priority, type, knight
- `## Description` section
- `## Dependencies` section with `Needs:` and `Blocks:` lines
- `## Block Reason` section (only present if `block_reason` is non-null)

## Internal Helpers

| Function | Purpose |
|----------|---------|
| `_write_summary(path, stats)` | Writes `.lore/reports/summary.md` |
| `_write_quest_index(path, quest, missions)` | Writes quest `index.md` |
| `_write_mission_file(path, mission, depends_on, blocks)` | Writes per-mission markdown file |
| `slugify(title)` | Stage 1 of slug algorithm |
| `make_entity_slug(entity_id, title)` | Stage 2 of slug algorithm |

## Related

- tech-cli-oracle-slugification (lore codex show tech-cli-oracle-slugification) — slugification algorithm detail
- tech-cli-commands (lore codex show tech-cli-commands) — `lore oracle` CLI command
- tech-db-schema (lore codex show tech-db-schema) — database functions called by this module
