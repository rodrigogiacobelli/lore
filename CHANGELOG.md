# Changelog

All notable changes to lore-agent-task-manager are recorded here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

See standards-public-api-stability for the public API stability and semver policy.

## [Unreleased]

## [0.2.1] - 2026-04-15

### Added

- **`lore artifact new`** — scaffold a new artifact file under `.lore/artifacts/` from the CLI.
- **`--group` flag on `lore knight new`, `lore watcher new`, and `lore doctrine new`** — create the entity directly inside a nested group/subfolder at creation time.
- Enriched `--help` output on all `new` and `list` subcommands, documenting the group/filter grammar and showing usage examples.
- `create_knight()` extracted as a reusable Python API entry point alongside the CLI command.

### Changed

- **Breaking:** `--filter` now uses slash-delimited path grammar (e.g. `--filter foo/bar`) across all list commands. Previous comma or dot-separated forms are no longer accepted.
- Group handling unified on slash-delimited paths throughout `paths.derive_group` and related helpers; list output displays groups using the slash form, and `--json` output reflects the same shape.
- New `validate_group` validator enforces the slash grammar at entity creation time, rejecting invalid group strings before they hit disk.

## [0.2.0] - 2026-04-10

### Added

- **`lore health`** — full codebase health audit command. Scans all five file-based entity
  types: codex documents (broken related links, missing `id` field, island nodes), artifacts
  (missing required frontmatter), doctrines (orphaned files, broken knight/artifact refs in
  steps), knights (active missions referencing absent knight files), and watchers (invalid
  YAML, broken doctrine refs).
- **`lore health --scope <type> [<type> ...]`** — limit the audit to one or more entity
  categories (e.g. `lore health --scope codex watchers`). Valid scopes: `codex`,
  `artifacts`, `doctrines`, `knights`, `watchers`.
- **`lore health --json`** — machine-readable JSON output of all issues found.
- **`lore health` exit codes** — `0` if clean or warnings only; `1` if any errors are
  present.
- Health report written as a markdown file to `codex/transient/` on every run, so the
  audit history is accessible through the codex.
- **`health_check()` Python API** — call `from lore.models import health_check` to run
  the audit programmatically; returns a `HealthReport` with structured `HealthIssue`
  entries. Both `HealthReport` and `HealthIssue` are now part of `lore.models.__all__`.
- **`lore <entity> list --filter <subtree>`** — filter listing output by folder subtree
  for artifacts, codex documents, doctrines, knights, and watchers.
- All list commands now accept an optional path argument to scope results to a specific
  group or subfolder.
- `lore doctrine show` accepts `--json` for machine-readable output.
- New doctrines are created with a companion `.design.md` file recording the doctrine's
  `id`, `title`, and `summary` alongside the YAML definition.
- **Doctrine redesign** — doctrines now cleanly separate knight personas from task
  definitions; updated default doctrine templates, knight files, and `lore doctrine show`
  output to reflect the new structure.

### Changed

- **Breaking:** `Doctrine` model fields renamed — `name` → `id`, `description` split into
  `title` and `summary`. Code importing `Doctrine.name` or `Doctrine.description` must
  update field references.
- **Breaking:** `DoctrineListEntry` model updated to match — `name` → `id`, `description`
  replaced by `title` and `summary`; `errors` field removed; `filename` now points to the
  `.design.md` file instead of the YAML file.
- Built-in knight personas reorganized into per-workflow subdirectories (e.g.
  `knights/feature-implementation/`); existing custom knights are unaffected.
- Default doctrines updated to use the new schema with explicit `id`, `title`, and
  `summary` fields.

## [0.1.0] — 2026-03-31

First release. Lore is the task engine and project memory system at the base of the
Camelot stack. It was built entirely by AI agents tracking their own work in Lore itself.

### Added

#### Task Engine
- **Quests** — named bodies of work with priorities (0–4), statuses (`open`, `in_progress`,
  `closed`), and optional auto-close when all missions are done
- **Missions** — individual executable tasks attached to a quest or standalone; support
  `open`, `in_progress`, `blocked`, and `closed` states with block reasons
- **Dependencies** — `lore needs` / `lore unneed` create directed "blocks" edges between
  missions; `lore ready` only surfaces work whose dependencies are fully closed
- **Claim / done / block / unblock** — lifecycle commands for orchestrators and worker agents
- **Board messages** — lightweight async communication channel per quest or mission

#### Project Memory (Codex)
- **Codex** — queryable knowledge graph of typed markdown documents stored in `.lore/codex/`;
  documents carry `id`, `title`, `summary` frontmatter and a `related` list for graph links
- **`lore codex search`** — case-insensitive keyword search across titles and summaries
- **`lore codex map`** — BFS traversal up to N hops from any document
- **`lore codex chaos`** — random-walk traversal with configurable coverage threshold (30–100%)

#### Knight Personas
- Knights are markdown files that define how an agent should behave for a class of work
- `lore show <mission-id>` returns the assigned Knight's full content alongside mission details,
  so agents receive persona and task in a single call

#### Doctrine Workflow Templates
- Doctrines are YAML templates that define ordered, dependency-linked steps for a body of work
- Cycle detection prevents invalid dependency graphs at creation time
- The `/start-quest` skill reads a doctrine and materialises it as a quest with missions

#### Artifacts & Watchers
- **Artifacts** — reusable document templates agents scaffold new files from
- **Watchers** — YAML definitions for agents that monitor and react to project state

#### CLI & Python API
- Full Click-based CLI (`lore [command]`) covering every operation
- Immutable frozen-dataclass public API in `lore.models.__all__` — stable across semver minor
  versions; internal modules are not part of the public contract
- `--json` flag on all read commands for machine-readable output
- `lore init` bootstraps a project with default doctrines, knights, artifacts, watchers, and
  the Claude skills needed for Realm integration

#### Infrastructure
- SQLite backend with WAL mode, 5-second busy timeout, and foreign-key enforcement
- Schema auto-migration (v1 → v6) on first connection
- Soft deletion throughout — entities carry `deleted_at` and are excluded from normal listings
  without losing referential integrity
- `lore oracle` generates human-readable markdown reports in `.lore/reports/`
- `lore stats` provides aggregate counts across all quests and missions