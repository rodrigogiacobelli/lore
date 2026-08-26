---
id: standards-public-api-stability
title: Public API Stability
summary: 'Everything in lore.api.__all__ is the public API of lore-agent-task-manager.
  Semver policy for pre-1.0: adding names or fields → minor bump; removals, renames,
  positional-arg or return-shape changes → major bump or explicit breaking-change
  notice in CHANGELOG.md. Internal modules (every module except lore.api) may be
  refactored freely as long as lore.api.__all__ is preserved.

  '
related:
- ref-lore_api-core
- standards-facade
- tech-arch-api-facade
- decisions-010-public-api-stability
- decisions-011-api-parity-with-cli
---

# Public API Stability

## Public API Definition

**The public API of `lore-agent-task-manager` is the set of names listed in
`lore.api.__all__`.**

`lore.api` is a pure re-export facade (zero `def`, zero `class`) — see `tech-arch-api-facade`. Every operational callable, type, enum, and exception that consumers may import is re-exported through it.

As of the current development branch, `lore.api.__all__` contains:

```python
__all__ = [
    # types & enums
    "QuestStatus",
    "MissionStatus",
    "DependencyType",
    "Quest",
    "Mission",
    "Dependency",
    "BoardMessage",
    "Artifact",
    "CodexDocument",
    "DoctrineStep",
    "Doctrine",
    "Knight",
    "DoctrineListEntry",
    "GlossaryItem",
    "Watcher",
    "HealthIssue",
    "HealthReport",
    "SchemaIssue",
    "CodeBinding",
    "CodexBinding",
    "ImpactsError",
    "ImpactsResult",
    "GlossaryError",
    "OverlayError",
    "ProjectNotFoundError",
    "ConflictingDepthFlags",
    "Config",
    "AccessMode",
    "FileAction",
    "AgentTarget",
    "PlannedFile",
    "InitAnswers",
    "InitPlan",
    "InitResult",
    # project root
    "find_project_root",
    # validators
    "validate_message",
    "validate_entity_id",
    "validate_mission_id",
    "validate_priority",
    "validate_name",
    "validate_group",
    "validate_quest_id_loose",
    "validate_chaos_threshold",
    "validate_access_mode",
    "validate_skill_family",
    "validate_agent_id",
    "validate_agent_selection",
    "validate_binds_entry",
    "is_glob_pattern",
    "route_entity",
    # db: quest CRUD
    "create_quest",
    "list_quests",
    "read_quest",
    "update_quest",
    "update_quest_full",
    "delete_quest",
    "close_quest",
    # db: mission CRUD
    "create_mission",
    "list_missions",
    "list_missions_grouped",
    "read_mission",
    "update_mission",
    "update_mission_full",
    "delete_mission",
    # db: status transitions
    "claim_mission",
    "claim_missions",
    "close_mission",
    "close_entities",
    "block_mission",
    "unblock_mission",
    # db: dependencies
    "add_dependency",
    "remove_dependency",
    "add_dependencies",
    "remove_dependencies",
    "list_mission_depends_on",
    "list_mission_blocks",
    "get_all_dependencies_for_quest",
    # db: board
    "add_board_message",
    "list_board_messages",
    "delete_board_message",
    # db: dashboard / stats / soft-delete
    "get_dashboard_quests",
    "get_aggregate_stats",
    "get_deleted_at",
    "get_missions_for_quest",
    # db: envelopes
    "get_mission_detail",
    "get_quest_detail",
    "delete_entity",
    "get_connection",
    "init_database",
    # priority
    "get_ready_missions",
    # knight
    "list_knights",
    "read_knight",
    "create_knight",
    "update_knight",
    "delete_knight",
    # doctrine
    "list_doctrines",
    "read_doctrine",
    "create_doctrine",
    "update_doctrine",
    "delete_doctrine",
    # artifact
    "list_artifacts",
    "read_artifact",
    "create_artifact",
    "update_artifact",
    "delete_artifact",
    # watcher
    "list_watchers",
    "read_watcher",
    "create_watcher",
    "update_watcher",
    "delete_watcher",
    # frontmatter field-edit (cross-entity)
    "update_frontmatter_fields",
    # codex
    "list_codex",
    "search_documents",
    "read_document",
    "read_documents_with_glossary",
    "map_documents",
    "chaos_documents",
    "create_document",
    "update_document",
    "delete_document",
    # glossary
    "scan_glossary",
    "read_glossary_item",
    "search_glossary",
    "match_glossary",
    "create_glossary_item",
    "update_glossary_item",
    "delete_glossary_item",
    # impacts
    "impacts",
    "classify_token",
    # health
    "health_check",
    # schemas
    "load_schema",
    "validate_entity",
    "validate_entity_file",
    "resolve_merged_schema",
    "project_validator_for",
    # init / reports / config
    "plan_init",
    "apply_init",
    "run_init",
    "generate_reports",
    "load_config",
    # paths
    "entity_location",
]
```

The authoritative copy lives in `src/lore/api.py`. If this doc and the source drift, the source wins.

## Internal Modules — Not Part of the Public API

Every module under `lore` **other than `lore.api`** is internal. None of the following may be imported by external consumers; all may be renamed, split, merged, or removed between any two releases as long as `lore.api.__all__` is preserved:

- `lore.cli` — Click handlers and CLI entry point
- `lore.db` — SQLite connection and operations
- `lore.models` — internal typed-record index (dataclasses & enums sourced by `lore.api`)
- `lore.validators` — input validation utilities
- `lore.paths` — `.lore/` path helpers
- `lore.graph` — graph algorithms on mission dependency sets
- `lore.priority` — ready-queue logic
- `lore.knight` — knight filesystem operations
- `lore.doctrine` — doctrine YAML loading, normalisation, validation
- `lore.watcher` — watcher YAML filesystem operations
- `lore.artifact` — artifact filesystem operations
- `lore.codex` — codex scanning, retrieval, search, traversal
- `lore.glossary` — glossary loading and matcher
- `lore.impacts` — codex↔code surfacing primitive
- `lore.health` — `lore health` audit implementation
- `lore.schemas` — JSON Schema loader + entity validators
- `lore.frontmatter` — shared frontmatter parsing
- `lore.config` — TOML config loader
- `lore.init` — `lore init` implementation (`plan_init`, `apply_init`, `run_init`)
- `lore.initplan` — the frozen init result types re-exported through `lore.api`
- `lore.agents` — packaged agent-registry loader
- `lore.skills` — skill catalogue loader and access-mode renderer
- `lore.manifest` — install-manifest read/write and hashing
- `lore.reconcile` — desired-vs-recorded-vs-on-disk reconciliation
- `lore.prompts` — CLI-layer interactive prompts
- `lore.oracle` — report generation
- `lore.ids` — hash-based ID generation
- `lore.root` — project root detection (re-exported through `lore.api` as `find_project_root` and `ProjectNotFoundError`)
- `lore.migrations.*` — schema migration modules
- The CLI entry point `lore.cli:main`

Lore's own `cli.py` reaches its internal helpers through leading-underscore namespace aliases re-exported from `lore.api` (e.g. `lore.api._paths.knights_dir`). External consumers do not have access to those aliases — they are excluded from `lore.api.__all__` by the underscore prefix per Spec §1.

## Semver Policy (Pre-1.0)

The package is pre-1.0. Under standard semver, `0.x` releases allow breaking changes in
minor version bumps. This project applies a more conservative policy:

| Change type | Required version bump |
|-------------|----------------------|
| Adding a new name to `lore.api.__all__` | Minor bump (e.g., `0.6.0` → `0.7.0`) |
| Adding a new field to an existing exported dataclass | Minor bump |
| Adding a new keyword argument with a default value to an exported function | Minor bump |
| Removing a name from `lore.api.__all__` | **Major bump** OR explicit breaking-change notice in `CHANGELOG.md` |
| Renaming a name in `lore.api.__all__` | **Major bump** OR explicit breaking-change notice |
| Changing the type of an existing exported field | **Major bump** OR explicit breaking-change notice |
| Changing the positional-arg list or the return shape of an exported function | **Major bump** OR explicit breaking-change notice |
| Bug fix with no API surface change | Patch bump (e.g., `0.6.0` → `0.6.1`) |

"Explicit breaking-change notice" means a `BREAKING CHANGE:` section in `CHANGELOG.md`
under the release entry, plus a note in release tags and any communication channels used
for the Camelot system.

## CHANGELOG.md

A `CHANGELOG.md` at the repository root (Keep a Changelog format) is the canonical record
of public API changes. Every release that touches names exported from `lore.api` must
include a changelog entry.

Changelog format:

```markdown
## [0.7.0] - 2026-MM-DD

### Added
- `lore.api` facade module — pure re-export of the public surface (ADR-010).
- `lore.api.__all__` — full operational API (CRUD, lifecycle, traversal, validators,
  schemas, health, impacts, priority, reporting). Replaces `lore.models.__all__` as the
  consumer-facing contract.
- `py.typed` PEP 561 marker (unchanged)

### Changed
- (any changed API surface)

### Removed
- (any removed names — BREAKING if without major bump)
```

## How Realm Should Pin

Realm must specify a minimum version and an upper bound when declaring its dependency:

```toml
# In Realm's pyproject.toml or requirements file:
lore-agent-task-manager>=0.7.0,<1.0
```

This range is safe **as long as this semver policy holds**: minor version bumps are
additive only; removals and renames require either a major bump or an explicit
breaking-change notice.

Realm must **not** pin to an exact version (e.g., `==0.7.0`).

## Transition to 1.0.0

The package will transition to `1.0.0` when:

1. The public API (names in `lore.api.__all__`) is considered stable for production
   external consumers beyond the Camelot system.
2. The Camelot team explicitly decides that the API contract is ready for full semver
   major-version semantics.

The 1.0.0 transition is a deliberate decision, not a scheduled event. At that point,
standard semver applies in full: breaking changes require a major version bump with no
exceptions.

## Rules for Contributors

- `lore/api.py` must maintain `__all__` as the authoritative list of exported names.
  Any addition to or removal from `__all__` triggers the semver policy above.
- Every release that changes the public API must include a `CHANGELOG.md` entry.
- Realm's dependency declaration must use a `>=min,<1.0` range, not an exact pin.
- Adding a new name to the public surface requires re-exporting it through `lore.api`,
  adding it to `lore.api.__all__`, and updating the changelog. Importability via an
  internal module is not enough — `lore.api.__all__` is the contract.
- Internal refactors that do not touch `lore.api.__all__` or the field shapes of
  exported types are free to proceed without a semver bump or changelog entry. This
  includes renaming, splitting, or merging modules below the facade.
