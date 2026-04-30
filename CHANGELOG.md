# Changelog

All notable changes to lore-agent-task-manager are recorded here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

See standards-public-api-stability for the public API stability and semver policy.

## [Unreleased]

## [0.4.0] - 2026-04-30

### Added

#### Glossary

- **New `Glossary` codex artefact** — single canonical YAML file at `.lore/codex/glossary.yaml` holding short, project-specific term definitions keyed by `keyword`. Each item has a `keyword` and `definition` plus optional `aliases` and `do_not_use` lists. The `keyword` is the natural key — no `id` field. See `conceptual-entities-glossary`.
- **`lore glossary` CLI group (read-only)** — three subcommands:
  - `lore glossary list` (alias `lore glossary`) — list every entry alphabetically by keyword. `--json` supported.
  - `lore glossary search <query>` — case-insensitive match against `keyword`, `aliases`, `do_not_use`, and `definition`. Multi-word queries supported with quoting.
  - `lore glossary show <keyword> [<keyword>...]` — return full entries by canonical keyword (case-insensitive lookup; aliases are NOT accepted as lookup keys).
  No `new`/`edit`/`delete` — maintainers edit the YAML directly. Mirrors the artifact CLI pattern.
- **Auto-surface on `lore codex show`** — when `show-glossary-on-codex-commands = true` (default) in `.lore/config.toml` and `--skip-glossary` is not passed, the system tokenises every returned codex document body, matches against keyword + alias token-tuples, and appends a trailing `## Glossary` section listing each matched item alphabetically. Multi-doc dedup at two levels: within-body and across-bodies. JSON envelope gains an always-present `"glossary": [...]` array. `do_not_use` matches do NOT auto-surface — they only surface in `lore health`. Fail-soft: a malformed glossary emits one stderr `glossary unavailable: <reason>` line and continues; `lore codex show` still exits 0.
- **`--skip-glossary` flag on `lore codex show`** — per-call escape hatch that suppresses the `## Glossary` section unconditionally and returns an empty `"glossary"` array in JSON mode.
- **`.lore/config.toml` (new project config file)** — generic, forward-compatible TOML config loader. Unknown keys are accepted and ignored to enable additive evolution. First (and only) MVP setting: `show-glossary-on-codex-commands` (bool, default `true`). Missing file → defaults silently. Malformed file → defaults + one stderr warning per process. Loaded by a new `lore.config` module; `Config` is internal-only and not exported via `lore.models.__all__`.
- **`lore health --scope glossary`** — runs glossary-only checks: schema validation, intra-file collision audits (duplicate keyword case-insensitive → error; alias-keyword collision → warning escalated to error; `do_not_use` overlap with another item's keyword/alias → error), and a cross-codex `glossary_deprecated_term` scan that emits one warning per occurrence of any `do_not_use` term in any codex document body. The `glossary` token combines with other scopes per ADR-012 (e.g. `lore health --scope codex glossary`).
- **`lore.glossary` Python module** — exports `scan_glossary`, `read_glossary_item`, `search_glossary`, `match_glossary` (canonical-only matches, alphabetised, deduplicated), `find_deprecated_terms` (per-occurrence health scan), `GlossaryError`. Built on a single shared word-boundary tokeniser (`re.compile(r"[^\w]+", re.UNICODE)` + `str.casefold()`) and lookup primitive reused by both surfaces.
- **`GlossaryItem` exported from `lore.models`** — frozen immutable dataclass with `keyword`, `definition`, `aliases`, `do_not_use`. `from_dict` classmethod constructs from raw YAML.
- **`glossary` JSON Schema** — packaged at `src/lore/schemas/glossary.yaml` (`$id: lore://schemas/glossary`). `_check_schemas` extended to support literal-filename globs (single fixed file at a known path) alongside `**/*.yaml` patterns.
- **ADR-013 — TOML for project config; YAML for glossary content** — `.lore/config.toml` uses TOML for ergonomic single-file key/value editing; `.lore/codex/glossary.yaml` uses YAML to match all other codex content (frontmatter, schemas, doctrines). Records the `lore init` carve-out below.
- **`conceptual-entities-glossary` codex doc** — full lifecycle, surfaces, properties, edge cases, and a "What Belongs Here" section gating glossary additions through three questions (project-specific? not an entity? not a named workflow?). Links to the design-doc artifact.
- **`conceptual-workflows-glossary` codex doc** — read-side workflows for `list`, `search`, `show`, auto-surface, and `--skip-glossary`. Test-anchor for every E2E scenario.
- **`glossary-design` design-document artifact** — checklist agents must run before adding any glossary entry. Contains the three-question gate, worked good/bad examples (Constable passes; Quest, ADR, Soft-delete, Auto-surface, Weapon all fail), YAML stanza template, and a "where to put it instead" table. Retrievable via `lore artifact show glossary-design`. Referenced from `tech-writer` knight, `ingest-source`/`refresh-source` skills, the seeded `CODEX.md`, and the seeded `glossary.yaml` header — every default that writes to the codex now points at the gate.

#### `lore init` and seeded defaults

- **`lore init` seeds `.lore/codex/glossary.yaml`** with a project-agnostic skeleton (`items: []` + a header pointing at `lore artifact show glossary-design`). The Glossary is the only file `lore init` seeds under `.lore/codex/` — a deliberate carve-out from the prior "init never writes to `.lore/codex/`" rule. The skeleton lands directly at `.lore/codex/glossary.yaml`, NOT under `.lore/codex/default/`, because the file is user-tracked vocabulary and a `default/` placement would be gitignored and overwritten on every re-init. Idempotent: existing files are left byte-for-byte untouched.
- **`lore init` seeds `.lore/config.toml`** with `show-glossary-on-codex-commands = true` and a header comment naming known keys. Idempotent.
- **`!config.toml` added to the seeded `.lore/.gitignore`** so the new config file is git-tracked alongside the rest of `.lore/`.
- **Seeded default skills and knights gained glossary references** — `explore-codex/SKILL.md` (added `lore glossary list/search/show` to the command table), `start-quest/SKILL.md` (vocabulary-alignment line), `feature-implementation/scout.md` (glossary added as a primary input alongside PRD and codex), `LORE-AGENT.md` (orientation surface), `CODEX.md` (rewrote the glossary guidance with the strict three-question gate). Dev knights (`tdd-red`, `tdd-green`, `tdd-refactor`, `tech-lead`) deliberately untouched — they don't write codex content.
- **`.lore/skills/.gitignore` seeded at init** — `lore init` now writes a `.gitignore` inside `.lore/skills/` listing every Lore-shipped skill directory. When a user copies the skills directory into their project's `.claude/skills/`, the bundled skills are ignored automatically without needing manual gitignore edits. User-added skills in the same directory are unaffected. The list is generated dynamically from `src/lore/defaults/skills/`, so newly shipped defaults are picked up on the next init.

### Changed

- **Python minimum bumped to 3.11** — required for stdlib `tomllib` to load `.lore/config.toml` without vendoring `tomli`.
- **`lore codex show` JSON envelope** — now always includes a `"glossary"` key (empty array when skipped, disabled, no-match, or fail-soft). Existing `"documents"` key unchanged.
- **`lore health --scope` accepts multiple values** per ADR-012 (`lore health --scope codex glossary`). Previous single-value form still works.
- **`_ALL_SCOPES` and `_SCHEMA_KINDS` extended** with `glossary`. `_check_schemas` resolves literal-filename globs (no `*` in pattern) via `entity_root / glob` instead of `glob()`, supporting single-fixed-file schema kinds.

## [0.3.1] - 2026-04-22

### Fixed

- **Packaging** — removed redundant `[tool.hatch.build.targets.wheel.force-include]` block that duplicated `src/lore/schemas/` in the wheel (the directory was already packaged via `packages = ["src/lore"]`). The 0.3.0 build emitted `Duplicate name:` warnings and the resulting wheel was rejected by PyPI with `400 Invalid distribution file. ZIP archive not accepted: Duplicate filename in local headers`. 0.3.1 is the first release of the 0.3 line available on PyPI; no behavior changes vs 0.3.0.

## [0.3.0] - 2026-04-22

### Added

#### Codex sources layer

- **New `sources/` codex content class** — third layer alongside stable and in-flight, for ingesting raw upstream material (Jira tickets, meeting transcripts, pasted docs, Confluence pages) as point-in-time snapshots under `.lore/codex/sources/<system>/<id>.md`. Sources are deletable at any time — any fact worth keeping lives in a canonical doc.
- **`codex-source-frontmatter` JSON Schema** — required `id`, `title`, `summary`, and non-empty outbound `related` listing every canonical codex doc the source touched; `additionalProperties: false`. `lore codex map <source-id> --depth 1` surfaces touched canonical docs via this list.
- **`lore health` schema dispatch** — files under `.lore/codex/sources/**/*.md` are now validated against `codex-source-frontmatter` instead of `codex-frontmatter`, surfacing with `entity_type="codex-source"` in the report.
- **Island-node skip for sources** — sources are inbound-orphans by design under the one-way link rule, so the island-node pass now excludes their IDs (previously would emit noisy `no documents link here` warnings).
- **`canonical_links_to_source` health error** — fires when any non-source codex doc includes a source ID in its `related` list, enforcing the canonical→source back-link ban at validation time.
- **`ingest-source` skill** — default agent-executed skill for first-time source capture. Access-method agnostic (pasted text, local file, URL, MCP tool). Writes a verbatim snapshot, identifies affected canonical docs, and populates the snapshot's outbound `related` with the touched canonical IDs.
- **`refresh-source` skill** — mirror of `ingest-source` for re-ingestion. Diffs fresh content vs stored snapshot, propagates approved changes into canonical docs, rewrites `related` from scratch each run (additions + removals), and overwrites the snapshot in place (no history file — git holds prior state).

#### Other additions

- **`lore artifact new`** — scaffold a new artifact file under `.lore/artifacts/` from the CLI.
- **`--group` flag on `lore knight new`, `lore watcher new`, and `lore doctrine new`** — create the entity directly inside a nested group/subfolder at creation time.
- Enriched `--help` output on all `new` and `list` subcommands, documenting the group/filter grammar and showing usage examples.
- `create_knight()` extracted as a reusable Python API entry point alongside the CLI command.
- **Schema validation across every entity** — codex, artifacts, doctrines, knights, and watchers are now validated against bundled YAML schemas on every `lore health` run. Invalid frontmatter, missing required fields, and bad field types are reported as structured errors.
- **`lore health --scope schemas`** — restrict an audit run to schema validation only, skipping graph and reference checks.
- Schema errors are rendered in both human-readable text and `--json` output, with the exact entity id, file path, field path, and rule that failed.
- Unparseable YAML and entity files missing frontmatter now surface as loud schema errors instead of being silently skipped.
- The transient health report written to `codex/transient/` gained a dedicated **Schema validation** section listing every schema issue found in the run.
- **`lore.schemas.load_schema()`** — bundled YAML schemas are now packaged as resources and loadable from the public Python API.
- **Python API parity** — schema validation is exposed through `lore.models`, so Realm and other importers can validate entities programmatically without going through the CLI.
- `parse_frontmatter_raw()` helper preserves every key on disk during parsing, enabling round-trip-safe validation against the schemas.

### Changed

- **Default `CODEX.md` restructured** — the "Stable vs In-Flight" section is now **The Three Content Classes** (Stable, In-Flight, Sources) with a deletion-test row per class, the sources layout, the four-field frontmatter rule, the verbatim rule, the one-way linking rule, and the refresh rule.
- **`conceptual-entities-artifact` gained outbound `related`** — closes an outbound-orphan hub so `lore codex map conceptual-entities-artifact --depth 1` now returns reachable docs.
- **Breaking:** `--filter` now uses slash-delimited path grammar (e.g. `--filter foo/bar`) across all list commands. Previous comma or dot-separated forms are no longer accepted.
- Group handling unified on slash-delimited paths throughout `paths.derive_group` and related helpers; list output displays groups using the slash form, and `--json` output reflects the same shape.
- New `validate_group` validator enforces the slash grammar at entity creation time, rejecting invalid group strings before they hit disk.
- Create-time validators for every entity now delegate to `lore.schemas`, so the same schema contract governs both file-on-disk audits and in-memory creation paths.
- `lore init` now produces a project that passes `lore health` schema validation out of the box; bundled default doctrines, knights, watchers, and artifacts were updated to satisfy the schemas.
- **Standards References section in `fi-user-story` template** — Tech Lead populates a `Standards References` block in every story's Tech Notes, listing relevant codex docs per role (Tester, Implementer). Red and Green agents read these before starting work, eliminating reliance on agents independently searching for standards.
- **Wiring scenarios and wiring stubs** — BA and Tech Lead steps in all three feature-implementation doctrines now explicitly require integration test scenarios and stubs for any page, container, or view that assembles child components. Component isolation tests are no longer sufficient.
- **`tdd-red` and `tdd-green` personas** — Red reads `Standards References → Tester` before writing any test; Green reads `Standards References → Implementer` before touching any file. Acceptance criteria are the starting point, not the complete contract.
- **`tdd-implementation` doctrine** — Red performs a wiring and coverage check against the Tech Spec file tree before marking done; Green verifies E2E test files are matched by the runner config; Refactor audits runner coverage as a quality check.

### Fixed

- Restored the `_validator_for` cache in `_check_schemas` via a dependency-injection seam, eliminating repeated schema compilation on large `lore health` runs.
- **CODEX.md default artifact** — frontmatter documentation now matches the actual schema enforced by `lore health`. Removed non-existent `type`, `stability`, `persona`, and `entities_involved` fields; corrected required fields to `id`, `title`, `summary` with `related` as the only optional field.
- **`start-quest` skill** — `lore needs` step now instructs agents to use fully-qualified `q-xxxx/m-yyyy` mission IDs. Bare `m-yyyy` IDs caused "Mission not found" errors.
- **Feature-implementation PM and BA knights** — UI feature requests now correctly scope page integration. PM captures end-to-end user workflows when a page is mentioned; BA requires a page-integration story for every UI component.

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