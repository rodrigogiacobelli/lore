---
id: tech-overview
title: Technical Overview
summary: Technology choices (Python, Click, SQLite WAL, PyYAML, packaging), concurrency strategy (WAL mode, busy timeout, BEGIN IMMEDIATE), and out-of-scope boundaries. Notes the --no-auto-close hidden/visible asymmetry between `lore new quest` and `lore edit`.
related: ["tech-db-schema", "tech-arch-source-layout", "vision-camelot-system", "tech-arch-schemas"]
---

# Technical Overview

## Technology

| Component | Choice |
|-----------|--------|
| Language | Python 3.10+ (minimum; uses `match` statements and modern type hints) |
| CLI framework | Click 8.x |
| Storage | SQLite 3.35+ (ships with Python 3.10+; uses `RETURNING` clause in INSERT statements for ID confirmation) |
| Template format | YAML via PyYAML (for Doctrines) |
| JSON Schema validation | `jsonschema>=4.18` — Draft 2020-12 validator, pure-Python, MIT. Runtime dependency added for entity-file schema validation used by both `lore health` and create-time validators. See tech-arch-schemas. |
| IDs | Short random hex (4–6 chars), generated from truncated `uuid4` values, hierarchical with `/` separator |
| Packaging | Single `uv pip install lore-agent-task-manager`. No extras, no optional dependencies. |
| Public API types | `lore.models` — `@dataclass(frozen=True)` for all boundary entity types. Zero new runtime dependencies. |
| Type checking | `mypy` in dev dependencies with `[tool.mypy]` strict configuration. `py.typed` PEP 561 marker ships with the package. |

For the full database schema, see tech-db-schema (lore codex show tech-db-schema). For ID generation details, see tech-db-schema (lore codex show tech-db-schema).

## Module Layering

The codebase follows the dependency hierarchy established by ADR-012:

```
cli.py  ──→  db.py  ──→  validators.py   (foundation: no lore.* imports)
   │                           ↑
   └───────────────────────────┘   (cli also imports validators for UX error translation)
   │
   ├──→  paths.py          (path helpers — centralises ".lore" string, derive_group)
   ├──→  knight.py    ──→  frontmatter.py
   │        └───────────→  paths.py
   ├──→  watcher.py  ──→  paths.py
   │        └───────────→  (no frontmatter.py — uses yaml.safe_load directly)
   ├──→  graph.py          (topological sort)
   ├──→  oracle.py
   ├──→  doctrine.py  ──→  paths.py, schemas.py
   ├──→  knight.py    ──→  schemas.py
   ├──→  watcher.py   ──→  schemas.py
   ├──→  artifact.py  ──→  frontmatter.py, schemas.py
   ├──→  codex.py     ──→  frontmatter.py
   ├──→  schemas.py   ──→  frontmatter.py   (loads packaged YAML schemas; no lore.* entity imports)
   └──→  health.py    ──→  schemas.py, frontmatter.py, doctrine.py, knight.py, watcher.py, artifact.py, codex.py
```

Dependency rules:

- `validators.py` has zero imports from any `lore.*` module. It is the safe foundation.
- `db.py` imports `validators` and `ids`; it does not import `cli.py` or `priority.py`
  (the `get_ready_missions` pass-through wrapper was removed in REFACTOR-9).
- `cli.py` imports `db`, `validators`, `paths`, `knight`, `watcher`, `graph`, `oracle`, `doctrine`,
  `codex`, `artifact`, and `root`. It does not contain business logic.
- `frontmatter.py` is imported by `codex.py`, `artifact.py`, `knight.py`, and `schemas.py`; it has no `lore.*` dependencies.
- `schemas.py` is the single authoritative home for entity JSON Schemas (shared by create-time validators in `doctrine.py`, `knight.py`, `watcher.py`, `artifact.py` and the audit-time `lore health` schema check). It imports only `frontmatter.py` and has no other `lore.*` dependencies.
- `paths.py` is imported by `cli.py`, `oracle.py`, `db.py`, `knight.py`, `doctrine.py`,
  and `artifact.py`.

## Concurrency and File Safety

Lore targets a single-user, single-machine workflow. Multiple agents may run CLI commands concurrently (e.g., two worker agents closing missions at the same time), so the database must handle concurrent writes safely.

- **SQLite WAL mode** is enabled on every connection (`PRAGMA journal_mode=WAL`). WAL allows concurrent readers and a single writer without blocking reads.
- **Busy timeout** is set to 5000ms (`PRAGMA busy_timeout=5000`). If a write lock is held by another process, SQLite retries for up to 5 seconds before returning `SQLITE_BUSY`.
- **No application-level file locking.** SQLite's built-in locking is sufficient.
- **All write operations use explicit transactions** (`BEGIN IMMEDIATE ... COMMIT`). `BEGIN IMMEDIATE` acquires a write lock at transaction start rather than on first write, preventing deadlocks when multiple processes race.
- **No connection pooling.** Each CLI invocation opens a connection, does its work, and closes it. The process exits immediately after.

The exact pragma statements are documented in tech-db-schema (lore codex show tech-db-schema).

## `--no-auto-close` Asymmetry

The `--no-auto-close` flag behaves differently on `lore new quest` vs `lore edit`:

- On **`lore new quest`**: `--no-auto-close` is marked `hidden=True` in `cli.py` (line 197) and does not appear in `--help` output. This is intentional — auto-close is disabled by default for new quests (`DEFAULT 0` in the schema), so the flag serves no purpose.
- On **`lore edit`**: `--no-auto-close` is a visible flag (line 1331). This is the correct mechanism to explicitly disable auto-close on an existing quest that previously had `--auto-close` enabled.

The source documentation (`docs/cli.md`) presents `--no-auto-close` as a user-visible flag in both contexts. The migrated documentation (this file and tech-cli-commands (lore codex show tech-cli-commands)) resolves this inconsistency by noting the hidden status explicitly.

## Out of Scope

The following are explicitly out of scope for Lore's current implementation:

- **Multi-machine sync or federation** — Single machine, single file
- **Automatic summarization or compaction** — No memory decay, no digest generation
- **Template engine in Doctrines** — No variable substitution, no inheritance, no composition. Claude interprets Doctrines.
- **Workflow enforcement** — Lore does not enforce workflow sequencing. Agents can claim and work on missions in any order regardless of dependencies. The dependency system is advisory for task ordering (surfaced via `lore ready`) but enforces structural integrity (no circular dependencies).
- **Agent spawning or orchestration** — The tool tracks work. Claude manages agents.
- **Fanout gates or conditional dependencies** — Only `blocks` dependency type
- **External integrations** — No sync with third-party tools
- **Inline Knights** — Knights are always files, never inline text in Missions or Doctrines
- **Undo/restore soft-deleted entities** — Soft-deleted entities are retained but restore commands are not provided. Manual SQL or file rename can recover them if needed.
- **Bulk edit** — Entity editing is one entity at a time, consistent with creation.
- **Interactive editing** — No `$EDITOR` support; content comes from flags, files, or stdin.
- **Moving missions between quests** — Requires ID rewriting which breaks external references. Workaround: create a new mission in the target quest and soft-delete the old one.
- **Renaming knight/doctrine files** — Use delete + create instead.
- **Messaging** — Agent-to-agent communication is not supported in the current version.
