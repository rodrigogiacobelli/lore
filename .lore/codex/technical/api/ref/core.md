---
id: ref-lore_api-core
title: Lore Python API — core surface
summary: Reference doc for the Lore Python API — what is public per entity, where the
  intentional gaps are, and the cross-cutting contracts (group= kwarg, filter_groups=
  kwarg, return-dict shapes for high-traffic operations, typed-model boundary).
  Source of truth is lore.api.__all__ (ADR-010); lore.models continues to host the
  dataclasses but is no longer the consumer-facing import path.
binds:
- src/lore/api.py
- src/lore/models.py
- tests/unit/test_models.py
- tests/unit/test_models_impacts.py
- tests/unit/test_api_surface.py
- tests/e2e/test_python_api.py
related:
- decisions-010-public-api-stability
- decisions-011-api-parity-with-cli
- decisions-007-artifact-communication-protocol
- tech-arch-api-facade
- tech-cli-entity-crud-matrix
- ref-lore_db-core
- conceptual-workflows-python-api
- conceptual-workflows-health
- conceptual-workflows-impacts
- standards-facade
- standards-public-api-stability
- conceptual-entities-glossary
- conceptual-workflows-glossary
- decisions-013-toml-for-config-yaml-for-glossary
- decisions-020-codex-voice-is-enforced
---

# Lore Python API — core surface

**Covers:** `lore.api` (the facade), and through it: every CRUD, lifecycle, traversal, validator, schema, health, impacts, priority, and reporting function in `lore-agent-task-manager`. The internal modules behind the facade (`lore.db`, `lore.codex`, `lore.artifact`, `lore.doctrine`, `lore.knight`, `lore.watcher`, `lore.glossary`, `lore.impacts`, `lore.priority`, `lore.models`, `lore.health`, `lore.validators`, `lore.schemas`, `lore.init`, `lore.oracle`, `lore.config`, `lore.root`) are not part of the public surface.

**Source of truth:** `src/lore/api.py` — `lore.api.__all__` enumerates the entire public API. Function signatures, type annotations, and exhaustive return-dict structures live in the operational modules behind the facade and in the dataclasses in `lore.models`. The facade itself contains no business logic; see `tech-arch-api-facade`.

## Why this exists

`lore.api.__all__` defines the stable public API per ADR-010 — anything not in `__all__` is internal and may change without notice. Realm, Citadel, the future Lore Server, and any third-party consumer must import exclusively from `lore.api`. The CLI is a thin wrapper over the same surface (ADR-011), and Lore's own `cli.py` consumes the facade via the same boundary (using leading-underscore aliases re-exported from `api.py` rather than direct submodule imports). This doc captures the cross-cutting contracts agents need before reaching for source: what operations exist per entity, what is *deliberately* missing, and the few return-dict shapes that encode contract callers must handle.

## Gotchas

- **`lore.api.__all__` is the boundary.** Names outside it (e.g. `_paths`, `_knight`, internal helpers like `_read_related`) are internal even when importable. Realm imports must reference `lore.api` only — never `from lore.models import ...` or `from lore.db import ...`.

- **`lore.db.*` (re-exported through `lore.api`) takes `project_root: Path` first.** File-module functions re-exported through `lore.api` (`list_knights`, `find_knight`, `create_knight`, `update_knight`, `delete_knight`, the doctrine/artifact/watcher equivalents, and `read_document`, `scan_codex`, `search_documents`, `map_documents`, `chaos_documents`) take the relevant subdirectory path (`knights_dir`, `doctrines_dir`, `artifacts_dir`, `watchers_dir`, `codex_dir`) instead. Mixing the two is the most common API misuse.

- **`group=` on every `create_*`.** All four entity create helpers — `create_doctrine`, `create_knight`, `create_watcher`, `create_artifact` (all re-exported through `lore.api`) — accept `group: str | None = None` (keyword-only). `None` = entity root. `"a/b/c"` = nested under `base / Path("a/b/c")` after `mkdir(parents=True, exist_ok=True)`. Validation lives in `lore.validators.validate_group` (also exported); CLI and Python paths are byte-identical (ADR-011). Invalid group raises the entity's exception (`DoctrineError` for doctrines; `ValueError` for the rest).

- **`filter_groups=` on every `list_*` / `scan_*`.** Lock-step with `group=`. `None` returns all entities. A list applies slash-delimited segment-prefix matching via internal helpers. Hyphen-delimited form is no longer accepted.

- **Duplicate-name detection is subtree-wide.** `rglob` over the entity root, regardless of `group`. Two doctrines named `foo` cannot coexist in different subdirectories.

- **`lore.api` `db.*` callables return raw `sqlite3.Row` and dict.** Typed models in `lore.models` (re-exported through `lore.api`) are a presentation layer constructed via classmethods (`Quest.from_row`, `Mission.from_row`, `BoardMessage.from_dict`, etc). The DB callables behind the facade never return typed objects.

- **Knight / Watcher locator helpers reject path-traversal.** `find_knight` and `find_watcher` (both re-exported through `lore.api`) return `Path | None`, but raise `ValueError` for names containing `/` or `\\`. Never glob `.lore/knights/**/*.md` directly.

- **`get_board_messages` filters soft-deleted at SQL.** The typed `BoardMessage` model has no `deleted_at` field — read-side contract excludes deleted rows. The `add_board_message` validator also filters by `deleted_at IS NULL` (stricter than `add_dependency`, which doesn't); board posts to soft-deleted entities are rejected.

- **`get_ready_missions` is exported from `lore.priority`, not `lore.db`.** `lore.api` re-exports it. The pass-through in `db.py` was deleted in the ADR-012 refactor; the only path to ready-mission selection is `lore.api.get_ready_missions(root, count)`.

- **`Dependency.from_row` is unused at the public layer.** The typed model exists but no callable returns full dependency rows. Use `get_mission_depends_on_details` / `get_mission_blocks_details` (return joined dicts, not Row).

- **`scan_glossary` returns `[]` if file missing; raises on parse failure.** `scan_glossary(root)` is fail-soft on absence (empty file or no file), fail-loud on schema/parse errors (raises `GlossaryError`). `read_glossary_item(root, kw)` is case-insensitive on the keyword; aliases are NOT lookup keys.

- **`match_glossary` operates on body strings.** Pass a `dict[doc_id, body]` (or list of bodies). Canonical-only token-run matching. Used by `lore codex show` auto-surface. There is no corpus-level deprecated-term scan — `find_deprecated_terms` has been removed.

- **Schema validation is callable from Realm.** `load_schema(kind)` returns the cached schema dict; `validate_entity_file(path, kind)` returns `list[HealthIssue]` with zero stdout/stderr side effects (ADR-011). Both are in `lore.api.__all__`. For project-local custom frontmatter, `validate_entity(kind, data, project_root=...)`, `resolve_merged_schema(kind, project_root)`, and `project_validator_for(kind, project_root)` build the overlay-merged validator from `.lore/custom-schemas/<kind>.yaml` (the two codex kinds; see tech-arch-schemas). An overlay governs canonical codex docs and the `sources/` layer only — docs under `.lore/codex/transient/` validate against the packaged schema alone at every seam (decisions-019-overlay-scope-stops-at-transient). `update_frontmatter_fields(kind="codex", ...)` sits on the same overlay path. A malformed overlay raises `OverlayError` (a `ValueError`).

- **`impacts(token, *, project_root, direct_links=False) -> ImpactsResult`.** The Python mirror of `lore impacts` (conceptual-workflows-impacts). `ImpactsResult` is a tagged-union dataclass — `kind == "codex"` populates `codex_items: tuple[CodexBinding, ...]`; `kind == "code"` populates `code_items: tuple[CodeBinding, ...]`. Errors surface as `ImpactsError` (subclass of `ValueError`) — unknown codex id, path outside repo, `..` traversal. The function takes `project_root: Path` (NOT `codex_dir`) because path-seed lookups normalise against the repo root, not the codex subdir.

- **Direct-Python `create_mission(project_root, title)` auto-attaches.** Calling `create_mission` from `lore.api` with no `quest_id` argument and exactly one open quest in the project attaches the new mission to that sole-open-quest. The CLI handler and the direct-Python path infer the parent identically (ADR-011 parity — FLAG #4 in the facade Review Ledger).

## Shape — entity matrix

Y = public function exists in `lore.api.__all__`. — = no concept in this dimension. ✗ = not implemented; see Gaps below for rationale.

| Entity | Create | Read | List | Search | Traverse | Update | Delete |
|--------|:------:|:----:|:----:|:------:|:--------:|:------:|:------:|
| Quest | Y | Y | Y | — | — | Y | Y |
| Mission | Y | Y | Y | — | — | Y | Y |
| Knight | Y | Y | Y | — | — | Y | Y |
| Doctrine | Y | Y | Y | — | — | Y | Y |
| Watcher | Y | Y | Y | — | — | Y | Y |
| Codex | ✗ | Y | Y | Y | Y | ✗ | ✗ |
| Glossary | ✗ | Y | Y | Y | — | ✗ | ✗ |
| Artifact | Y | Y | Y | — | — | Y | Y |
| Board Message | Y | Y | Y | — | — | ✗ (immutable) | Y |
| Dependency | Y | Y (details) | — | — | — | — | Y |

### Gaps and rationale

- **Codex create/update/delete** — none. Codex is hand-edited by humans/agents. Lore's role is to read, search, and traverse.
- **Glossary write paths** — none. The glossary is a single YAML file edited directly with the `glossary-design` checklist as the gate.
- **Knight/Doctrine/Artifact full CRUD** — `update_*` and `delete_*` are now in `lore.api.__all__` for all three (per ADR-007 Amendment for artifacts and the ADR-010 facade buildout for knight/doctrine). The CLI exposes the matching `edit` and `delete` subcommands at full parity.
- **Quest/Mission search** — no full-text search behind the facade. Use `list_*` + filter in caller.

## Operational re-exports through `lore.api`

The facade re-exports the operational surface in named sections; this list mirrors the structure of `__all__` in `src/lore/api.py`. New exports are appended within the relevant section, never sprinkled across sections.

- **Types & enums** — `QuestStatus`, `MissionStatus`, `DependencyType`, `Quest`, `Mission`, `Dependency`, `BoardMessage`, `Artifact`, `CodexDocument`, `DoctrineStep`, `Doctrine`, `Knight`, `DoctrineListEntry`, `GlossaryItem`, `Watcher`, `HealthIssue`, `HealthReport`, `SchemaIssue`, `CodeBinding`, `CodexBinding`, `ImpactsError`, `ImpactsResult`, `DoctrineError`, `GlossaryError`, `OverlayError`, `ProjectNotFoundError`, `ConflictingDepthFlags`, `Config`.
- **Project root** — `find_project_root`.
- **Validators** — `validate_message`, `validate_entity_id`, `validate_mission_id`, `validate_priority`, `validate_name`, `validate_group`, `validate_quest_id_loose`, `validate_chaos_threshold`, `validate_binds_entry`, `is_glob_pattern`, `route_entity`.
- **DB: quest CRUD** — `create_quest`, `list_quests`, `get_quest`, `edit_quest`, `edit_quest_full`, `delete_quest`, `close_quest`.
- **DB: mission CRUD** — `create_mission`, `list_missions`, `list_missions_grouped`, `get_mission`, `edit_mission`, `edit_mission_full`, `delete_mission`.
- **DB: status transitions** — `claim_mission`, `claim_missions`, `close_mission`, `close_entities`, `block_mission`, `unblock_mission`.
- **DB: dependencies** — `add_dependency`, `remove_dependency`, `add_dependencies`, `remove_dependencies`, `get_mission_depends_on`, `get_mission_blocks`, `get_mission_depends_on_details`, `get_mission_blocks_details`, `get_all_dependencies_for_quest`.
- **DB: board** — `add_board_message`, `get_board_messages`, `delete_board_message`.
- **DB: dashboard / stats / soft-delete** — `get_dashboard_quests`, `get_aggregate_stats`, `get_deleted_at`, `get_missions_for_quest`.
- **DB: envelopes** — `get_mission_detail`, `get_quest_detail`, `delete_entity`.
- **DB: connections / migrations** — `get_connection`, `init_database`.
- **Priority** — `get_ready_missions`.
- **Knight** — `list_knights`, `find_knight`, `read_knight`, `create_knight`, `update_knight`, `delete_knight`.
- **Doctrine** — `list_doctrines`, `show_doctrine`, `create_doctrine`, `update_doctrine`, `delete_doctrine`.
- **Artifact** — `scan_artifacts`, `read_artifact`, `create_artifact`, `update_artifact`, `delete_artifact`.
- **Watcher** — `list_watchers`, `find_watcher`, `load_watcher`, `create_watcher`, `update_watcher`, `delete_watcher`.
- **Codex** — `scan_codex`, `search_documents`, `read_document`, `read_documents_with_glossary`, `map_documents`, `chaos_documents`.
- **Glossary** — `scan_glossary`, `read_glossary_item`, `search_glossary`, `match_glossary`.
- **Impacts** — `impacts`, `classify_token`.
- **Health** — `health_check`.
- **Schemas** — `load_schema`, `validate_entity`, `validate_entity_file`, `resolve_merged_schema`, `project_validator_for`.
- **Init / reports / config** — `run_init`, `generate_reports`, `load_config`.

The authoritative list lives in `src/lore/api.py`. If this doc and the source drift, the source wins; report the drift via `lore health` or a codex update.

## Return-dict contracts that callers must handle

The contract for these three is non-trivial and worth pinning here. Other functions return success/error dicts whose shape is obvious from source.

### `claim_mission(root, id)`

Includes quest status change information so callers do not run a follow-up query when the parent quest transitions `open → in_progress`. Keys present on every path: `ok`, `status`, `error`, `quest_id`, `quest_status_changed`, `quest_status`. `quest_id` and `quest_status` are `None` for standalone missions and for not-found / invalid-transition errors.

### `close_mission(root, id)`

Includes `quest_id` on every path (string or `None` for standalone missions). On the auto-close path: `quest_closed=True`. On the already-closed idempotent path: `quest_id=None`. The `quest_id` presence rule lets callers route follow-up notifications without re-querying.

### `add_board_message(root, entity_id, message, sender=None)`

Validates entity existence inside the same `BEGIN IMMEDIATE` as the insert. Validation lives in the operational layer only; the CLI handler does not pre-check. Empty/whitespace messages are rejected by the DB layer with `"Message cannot be empty"`. Soft-deleted entities are rejected with `"Quest \"...\" not found"` / `"Mission \"...\" not found"`.

## Diagnostic operations

`health_check(project_root, scope=None)` audits all file-based entity types, validates every entity file's shape against its JSON Schema, audits codex `binds:` and `rites:` reference integrity, and audits canonical codex prose against the voice rules. Never prints. Returns `HealthReport` (frozen dataclass with `errors`, `warnings`, `has_errors`, `issues`). Valid scope tokens: `codex`, `artifacts`, `doctrines`, `knights`, `watchers`, `schemas`, `glossary`, `bindings`, `rites`, `voice`. `None` runs every scope.

`HealthIssue` is a frozen dataclass with `severity`, `entity_type`, `id`, `check`, `detail`, plus three optional fields populated only on schema checks: `schema_id`, `rule`, `pointer`. `HealthIssue.from_dict(d)` round-trips JSON output and tolerates legacy payloads without the schema fields.

The `bindings` scope emits two check names: `dead_binding` (severity `error`, dead literal `binds:` path) and `empty_glob_binding` (severity `warning`, glob `binds:` matching zero files). Both rows carry `entity_type="codex"`, `id=<codex-entry-id>`, and `schema_id`/`rule`/`pointer` all `None`. Realm filters by `issue.check` to message authoring knights before dispatch (ADR-011 parity with the CLI). See conceptual-workflows-health (lore codex show conceptual-workflows-health).

The `voice` scope emits five check names — `voice_past_narration`, `voice_expiry_hedge`, `voice_forward_promise`, `voice_dangling_deixis`, `voice_sales_register` — all with severity `warning`, `entity_type="codex"`, `id=<codex-id>`, and `schema_id`/`rule`/`pointer` all `None`. No `voice_*` row ever sets `has_errors`; a caller that wants a voice gate applies its own threshold over `report.warnings` (`decisions-020-codex-voice-is-enforced`). `lore artifact show codex-voice` is the normative rule set.
