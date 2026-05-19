---
id: ref-lore_api-core
title: Lore Python API — core surface
summary: Reference doc for the Lore Python API — what is public per entity, where the
  intentional gaps are, and the cross-cutting contracts (group= kwarg, filter_groups=
  kwarg, return-dict shapes for high-traffic operations, typed-model boundary).
  Source of truth is the modules themselves and `lore.models.__all__`.
binds:
- src/lore/models.py
- tests/unit/test_models.py
- tests/unit/test_models_impacts.py
- tests/e2e/test_python_api.py
related:
- decisions-010-public-api-stability
- decisions-011-api-parity-with-cli
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
---

# Lore Python API — core surface

**Covers:** `lore.db`, `lore.codex`, `lore.artifact`, `lore.doctrine`, `lore.knight`, `lore.watcher`, `lore.glossary`, `lore.impacts`, `lore.priority`, `lore.models`, `Quest`, `Mission`, `Knight`, `Doctrine`, `DoctrineListEntry`, `DoctrineStep`, `Watcher`, `CodexDocument`, `Artifact`, `GlossaryItem`, `BoardMessage`, `Dependency`, `HealthReport`, `HealthIssue`, `ImpactsResult`, `CodexBinding`, `CodeBinding`, `ImpactsError`, `claim_mission`, `close_mission`, `add_board_message`, `health_check`, `load_schema`, `validate_entity_file`, `scan_glossary`, `read_glossary_item`, `search_glossary`, `match_glossary`, `impacts`
**Source of truth:** `src/lore/` (each module's `__init__.py` + `lore.models.__all__` enumerate the public surface). Function signatures, type annotations, and exhaustive return-dict structures live in code, not here.

## Why this exists

`lore.models.__all__` defines the stable public API per ADR-010 — anything not in `__all__` is internal and may change without notice. Realm depends on this surface; the CLI is a thin wrapper over it (ADR-011). This doc captures the cross-cutting contracts agents need before reaching for source: what operations exist per entity, what is *deliberately* missing, and the few return-dict shapes that encode contract callers must handle.

## Gotchas

- **`lore.models.__all__` is the boundary.** Names outside it (e.g. `Config`, `_read_related`) are internal even when importable. Realm imports must reference `__all__` only.

- **`lore.db.*` takes `project_root: Path` first.** File-module functions (`lore.knight.*`, `lore.doctrine.*`, `lore.watcher.*`, `lore.artifact.*`, `lore.codex.*`) take the relevant subdirectory path instead. Mixing the two is the most common API misuse.

- **`group=` on every `create_*`.** All four entity create helpers — `lore.doctrine.create_doctrine`, `lore.knight.create_knight`, `lore.watcher.create_watcher`, `lore.artifact.create_artifact` — accept `group: str | None = None` (keyword-only). `None` = entity root. `"a/b/c"` = nested under `base / Path("a/b/c")` after `mkdir(parents=True, exist_ok=True)`. Validation lives in `lore.validators.validate_group`; CLI and Python paths are byte-identical (ADR-011). Invalid group raises the entity's exception (`DoctrineError` for doctrines; `ValueError` for the rest).

- **`filter_groups=` on every `list_*` / `scan_*`.** Lock-step with `group=`. `None` returns all entities. A list applies slash-delimited segment-prefix matching via `paths.group_matches_filter`. Hyphen-delimited form is no longer accepted.

- **Duplicate-name detection is subtree-wide.** `rglob` over the entity root, regardless of `group`. Two doctrines named `foo` cannot coexist in different subdirectories.

- **`lore.db` returns raw `sqlite3.Row` and dict.** Typed models in `lore.models` are a presentation layer constructed via classmethods (`Quest.from_row`, `Mission.from_row`, `BoardMessage.from_dict`, etc). The DB layer never returns typed objects.

- **Knight / Watcher locator helpers reject path-traversal.** `lore.knight.find_knight` and `lore.watcher.find_watcher` return `Path | None`, but raise `ValueError` for names containing `/` or `\\`. Never glob `.lore/knights/**/*.md` directly.

- **`get_board_messages` filters soft-deleted at SQL.** The typed `BoardMessage` model has no `deleted_at` field — read-side contract excludes deleted rows. The `add_board_message` validator also filters by `deleted_at IS NULL` (stricter than `add_dependency`, which doesn't); board posts to soft-deleted entities are rejected.

- **`db.get_ready_missions` was removed.** Use `lore.priority.get_ready_missions(root, count)`. The pass-through in `db.py` was deleted in the ADR-012 refactor.

- **`Dependency.from_row` is unused at the public layer.** The typed model exists but no `lore.db` function returns full dependency rows. Use `db.get_mission_depends_on_details` / `db.get_mission_blocks_details` (return joined dicts, not Row).

- **`scan_glossary` returns `[]` if file missing; raises on parse failure.** `lore.glossary.scan_glossary(root)` is fail-soft on absence (empty file or no file), fail-loud on schema/parse errors (raises `GlossaryError`). `read_glossary_item(root, kw)` is case-insensitive on the keyword; aliases are NOT lookup keys.

- **`match_glossary` operates on body strings.** Pass a `dict[doc_id, body]` (or list of bodies). Canonical-only token-run matching. Used by `lore codex show` auto-surface. There is no corpus-level deprecated-term scan — `find_deprecated_terms` has been removed.

- **Schema validation is callable from Realm.** `lore.models.load_schema(kind)` returns the cached schema dict; `lore.models.validate_entity_file(path, kind)` returns `list[HealthIssue]` with zero stdout/stderr side effects (ADR-011). Both are in `__all__`.

- **`lore.models.impacts(token, *, project_root, direct_links=False) -> ImpactsResult`.** The Python mirror of `lore impacts` (conceptual-workflows-impacts). `ImpactsResult` is a tagged-union dataclass — `kind == "codex"` populates `codex_items: tuple[CodexBinding, ...]`; `kind == "code"` populates `code_items: tuple[CodeBinding, ...]`. Errors surface as `ImpactsError` (subclass of `ValueError`) — unknown codex id, path outside repo, `..` traversal. The function takes `project_root: Path` (NOT `codex_dir`) because path-seed lookups normalise against the repo root, not the codex subdir.

## Shape — entity matrix

Y = public function exists. — = no concept in this dimension. CLI = available via CLI but not (yet) exposed in `lore.models.__all__`. ✗ = not implemented; see Gaps below for rationale.

| Entity | Create | Read | List | Search | Traverse | Update | Delete |
|--------|:------:|:----:|:----:|:------:|:--------:|:------:|:------:|
| Quest | Y | Y | Y | — | — | Y | Y |
| Mission | Y | Y | Y | — | — | Y | Y |
| Knight | Y | Y | Y | — | — | CLI | CLI |
| Doctrine | Y | Y | Y | — | — | CLI | CLI |
| Watcher | Y | Y | Y | — | — | Y | Y |
| Codex | ✗ | Y | Y | Y | Y | ✗ | ✗ |
| Glossary | ✗ | Y | Y | Y | — | ✗ | ✗ |
| Artifact | Y | Y | Y | — | — | ✗ | ✗ |
| Board Message | Y | Y | Y | — | — | ✗ (immutable) | Y |
| Dependency | Y | Y (details) | — | — | — | — | Y |

### Gaps and rationale

- **Codex create/update/delete** — none. Codex is hand-edited by humans/agents. Lore's role is to read, search, and traverse.
- **Glossary write paths** — none. The glossary is a single YAML file edited directly with the `glossary-design` checklist as the gate.
- **Artifact update/delete** — out of scope. Artifacts are intended as long-lived templates; mutation is on-disk.
- **Knight/Doctrine update/delete** — CLI-only post-MVP; the create paths landed in the recent group-aware refactor.
- **Quest/Mission search** — no full-text search in `lore.db`. Use `list_*` + filter in caller.

## Return-dict contracts that callers must handle

The contract for these three is non-trivial and worth pinning here. Other functions return success/error dicts whose shape is obvious from source.

### `claim_mission(root, id)`

Includes quest status change information so callers do not run a follow-up query when the parent quest transitions `open → in_progress`. Keys present on every path: `ok`, `status`, `error`, `quest_id`, `quest_status_changed`, `quest_status`. `quest_id` and `quest_status` are `None` for standalone missions and for not-found / invalid-transition errors.

### `close_mission(root, id)`

Includes `quest_id` on every path (string or `None` for standalone missions). On the auto-close path: `quest_closed=True`. On the already-closed idempotent path: `quest_id=None`. The `quest_id` presence rule lets callers route follow-up notifications without re-querying.

### `add_board_message(root, entity_id, message, sender=None)`

Validates entity existence inside the same `BEGIN IMMEDIATE` as the insert. Validation lives in `db.add_board_message` only; the CLI handler does not pre-check. Empty/whitespace messages are rejected by the DB layer with `"Message cannot be empty"`. Soft-deleted entities are rejected with `"Quest \"...\" not found"` / `"Mission \"...\" not found"`.

## Diagnostic operations

`health_check(project_root, scope=None)` audits all file-based entity types, validates every entity file's shape against its JSON Schema, and audits codex `binds:` reference integrity. Never prints. Returns `HealthReport` (frozen dataclass with `errors`, `warnings`, `has_errors`, `issues`). Valid scope tokens: `codex`, `artifacts`, `doctrines`, `knights`, `watchers`, `schemas`, `glossary`, `bindings`. `None` runs every scope.

`HealthIssue` is a frozen dataclass with `severity`, `entity_type`, `id`, `check`, `detail`, plus three optional fields populated only on schema checks: `schema_id`, `rule`, `pointer`. `HealthIssue.from_dict(d)` round-trips JSON output and tolerates legacy payloads without the schema fields.

The `bindings` scope emits two check names: `dead_binding` (severity `error`, dead literal `binds:` path) and `empty_glob_binding` (severity `warning`, glob `binds:` matching zero files). Both rows carry `entity_type="codex"`, `id=<codex-entry-id>`, and `schema_id`/`rule`/`pointer` all `None`. Realm filters by `issue.check` to message authoring knights before dispatch (ADR-011 parity with the CLI). See conceptual-workflows-health (lore codex show conceptual-workflows-health).
