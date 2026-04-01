---
id: conceptual-workflows-oracle
title: Report Generation — lore oracle
summary: >
  What the system does internally when lore oracle runs — report generation, directory structure, per-quest markdown files, mission-type inclusion, and slug derivation.
related: ["tech-oracle-internals", "tech-cli-commands"]
stability: stable
---

# Report Generation — `lore oracle`

`lore oracle` generates human-readable markdown reports in `.lore/reports/`. It is a destructive operation on the reports directory: the entire directory is wiped and recreated on every run. Reports are intended for human stakeholders and are not consumed by agents.

## Preconditions

- The Lore project has been initialised.
- Write access to `.lore/reports/` (directory is created if absent; deleted and recreated if present).

## Steps

### 1. Delete and recreate the reports directory

`generate_reports` in `lore.oracle` calls `shutil.rmtree(reports_dir)` then `reports_dir.mkdir(parents=True)`. Any custom files previously placed in `.lore/reports/` are lost.

### 2. Write `summary.md`

`get_aggregate_stats` is called and written to `.lore/reports/summary.md` with the quest and mission counts in a human-readable markdown table.

### 3. Generate per-quest reports

For each quest (including closed, excluding soft-deleted) that has at least one mission:

1. A per-quest directory is created under `.lore/reports/quests/<quest-slug>/`. The slug is derived by `make_entity_slug(quest_id, title)` — see Slug Derivation below.
2. `index.md` is written inside the quest directory with the quest's metadata and a mission list.
3. For each mission in the quest, a file `<m-slug>.md` is written with the mission's metadata, `mission_type` (if set), and dependency lists.

### 4. Generate standalone mission reports

Standalone missions (those with `quest_id IS NULL`) are written to `.lore/reports/missions/<mission-slug>.md`.

### 5. Report to stdout

```
Reports generated in .lore/reports/
```

No JSON output is supported for `oracle`. The `--json` flag is accepted but ignored.

## Slug Derivation

`slugify(title)`:

1. Lowercase.
2. Replace non-alphanumeric characters with hyphens.
3. Collapse consecutive hyphens.
4. Trim leading/trailing hyphens.
5. Truncate to 40 characters at the last word boundary (hyphen).

`make_entity_slug(entity_id, title)`:

Combines as `{entity_id}-{slug(title)}`. The 40-character limit applies to the combined result. If the combined string exceeds 40 characters, it is truncated at the last hyphen after the entity ID prefix.

## `mission_type` in Reports

If a mission has a non-null `mission_type`, it is included in the mission's report file. The oracle renders it as a metadata field — it does not interpret or filter on the value.

## Directory Structure

```
.lore/reports/
  summary.md
  quests/
    q-xxxx-my-feature/
      index.md
      m-yyyy-first-task.md
      m-zzzz-second-task.md
  missions/
    m-aaaa-standalone-task.md
```

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Project not initialised | Error to stderr | 1 |
| Write permission denied on reports dir | OS-level exception propagates | 1 |

## Out of Scope

- Incremental updates — every run is a full wipe and regenerate.
- Machine-readable JSON output from `oracle`.
- Agent consumption of reports — use `lore codex` for agent-readable docs.
