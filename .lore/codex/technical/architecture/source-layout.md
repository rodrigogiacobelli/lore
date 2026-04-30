---
id: tech-arch-source-layout
title: Source Layout
summary: >
  The src/lore/ source tree with one-line descriptions per module, including init.py, root.py, oracle.py, doctrine.py (two-file model: list_doctrines/show_doctrine/create_doctrine), codex.py (map_documents, chaos_documents, _read_related), artifact.py, validators.py (validate_chaos_threshold), paths.py (glossary_path, config_path), knight.py, frontmatter.py (extra_fields), graph.py, glossary.py (scan_glossary, match_glossary, find_deprecated_terms, _normalise_tokens, _build_lookup, _render_glossary_block), and config.py (Config dataclass, load_config — TOML loader for .lore/config.toml). Covers package entry points, defaults directory (paired .yaml + .design.md doctrines, knights, artifacts/transient/), migrations (v1-v6), py.typed, and tests layout. Documents lore.models public API (frozen dataclasses, from_row/from_dict, __all__) — now includes GlossaryItem. Notes breaking Doctrine API change: name/description removed; id/title/summary added.
related: ["tech-overview", "standards-dry", "standards-single-responsibility", "standards-dependency-inversion", "tech-arch-project-root-detection", "conceptual-workflows-oracle", "tech-arch-schemas", "conceptual-entities-glossary", "conceptual-workflows-glossary", "decisions-013-toml-for-config-yaml-for-glossary"]
---

# Source Layout

The Lore source code repository. Default Doctrines, Knights, and Artifacts are shipped with the package and copied into target projects on `lore init`.

```
lore/
|- pyproject.toml
|- README.md
|- CHANGELOG.md
|- LICENSE
|- src/
|  +-- lore/
|      |- __init__.py           # Package marker; exposes __version__ only
|      |- __main__.py           # Enables `python -m lore` invocation
|      |- py.typed              # PEP 561 marker — lore ships inline type annotations
|      |- cli.py                # Click command definitions
|      |- db.py                 # SQLite schema and operations
|      |- models.py             # Public typed API — all boundary entity dataclasses and enums
|      |- ids.py                # Hash-based ID generation
|      |- priority.py           # Ready queue logic
|      |- root.py               # Project root detection (find_project_root, ProjectNotFoundError)
|      |- init.py               # lore init implementation (database setup, file seeding, AGENTS.md write)
|      |- oracle.py             # Report generation (generate_reports, wipe-and-recreate .lore/reports/)
|      |- doctrine.py           # Doctrine YAML loading, normalisation, and validation pipeline
|      |- codex.py              # Codex document scanning, retrieval, and search (scan_codex, read_document, search_documents)
|      |- artifact.py           # Artifact file scanning and retrieval (scan_artifacts, read_artifact)
|      |- validators.py         # Input validation — validate_message, validate_entity_id, validate_mission_id, validate_priority, validate_name, validate_quest_id_loose, route_entity
|      |- paths.py              # Canonical .lore/ path helpers ... and derive_group() (lore_dir, knights_dir, doctrines_dir, codex_dir, artifacts_dir, reports_dir, db_path)
|      |- knight.py             # Knight filesystem operations (list_knights, find_knight) — mirrors doctrine.py in structure
|      |- watcher.py            # Watcher YAML filesystem operations (list_watchers, find_watcher, load_watcher, create_watcher, update_watcher, delete_watcher)
|      |- frontmatter.py        # Shared frontmatter parsing for markdown files (parse_frontmatter_doc, parse_frontmatter_doc_full, parse_frontmatter_raw)
|      |- glossary.py           # Glossary YAML loading, matching, and rendering (scan_glossary, read_glossary_item, search_glossary, match_glossary, find_deprecated_terms, _normalise_tokens, _build_lookup, _render_glossary_block, GlossaryError)
|      |- config.py             # Project config TOML loader (Config dataclass, load_config, DEFAULT_CONFIG)
|      |- schemas.py            # JSON Schema loader + validate_entity / validate_entity_file — single authoritative home for entity schemas, consumed by both create-time validators and lore health
|      |- schemas/              # Packaged authoritative JSON Schemas as YAML resources (doctrine-yaml, doctrine-design-frontmatter, knight-frontmatter, watcher-yaml, codex-frontmatter, artifact-frontmatter)
|      |  |- __init__.py        # Empty — makes the dir importlib.resources-accessible
|      |  +-- *.yaml            # One file per schema, $id lore://schemas/<kind> (kinds: doctrine-yaml, doctrine-design-frontmatter, knight, watcher, codex, artifact, glossary)
|      |- graph.py              # Graph algorithms on mission dependency sets (topological_sort_missions)
|      |- migrations/           # Schema migration functions
|      |  |- __init__.py
|      |  |- v1_to_v2.py        # Adds deleted_at columns (soft-delete)
|      |  |- v2_to_v3.py        # Adds auto_close column to quests
|      |  |- v3_to_v4.py        # Adds mission_type column to missions
|      |  |- v4_to_v5.py        # Removes mission_type enum: drops NOT NULL, CHECK, DEFAULT 'knight'
|      |  +-- v5_to_v6.py       # Adds board_messages table and idx_board_entity index
|      +-- defaults/
|          |- AGENTS.md         # Lightweight agent basics guide — directs agents to `lore --help` for the full model
|          |- gitignore         # Default .gitignore (copied as .lore/.gitignore)
|          |- schema.sql        # SQLite schema for init
|          |- doctrines/        # Default doctrines — each is a paired .yaml (id + steps) and .design.md (id, title, summary + body)
|          |  +-- update-changelog.yaml
|          |  +-- update-changelog.design.md
|          |  +-- feature-implementation/
|          |     +-- feature-implementation.yaml
|          |     +-- feature-implementation.design.md
|          |     +-- quick-feature-implementation.yaml
|          |     +-- quick-feature-implementation.design.md
|          |     +-- tdd-implementation.yaml
|          |     +-- tdd-implementation.design.md
|          |- knights/          # Default knights — the nine adversarial-spec roles (all carry YAML frontmatter with id, title, summary)
|          |  |- architect-analyst.md
|          |  |- architect-critic.md
|          |  |- architect-consolidator.md
|          |  |- ba-drafter.md
|          |  |- ba-critic.md
|          |  |- ba-consolidator.md
|          |  |- sys-analyst.md
|          |  |- tech-lead.md
|          |  +-- sys-architect.md
|          |- watchers/          # Default watcher
|          |  +-- change-log-updates.yaml
|          +-- artifacts/       # Default artifacts — the shipped development process
|             |- transient/     # Spec and story templates produced by the pipeline
|             |  |- business-spec.md   # id: transient-business-spec
|             |  |- full-spec.md       # id: transient-full-spec
|             |  +-- user-story.md     # id: transient-user-story
|             +-- codex/        # Example codex — illustrates well-formed docs at each layer
|                |- CODEX.md          # id: example-codex
|                |- INDEX.md          # id: example-index
|                |- conceptual/entities/task.md        # id: example-entity-task
|                |- conceptual/entities/user.md        # id: example-entity-user
|                |- conceptual/relationships/user--task.md  # id: example-relationship-user-task
|                |- conceptual/workflows/complete-task.md   # id: example-workflow-complete-task
|                |- technical/overview.md              # id: example-tech-overview
|                |- technical/database/schemas/tasks.md     # id: example-tech-schema-tasks
|                |- operations/git.md                  # id: example-ops-git
|                +-- decisions/001-sqlite-storage.md   # id: example-decision-001
+-- tests/                      # pytest; mirrors src/lore/ structure
    |- e2e/
    |  |- test_watcher_list.py    # NEW — E2E tests for watcher list and show
    |  +-- test_watcher_crud.py   # NEW — E2E tests for watcher new, edit, delete and init seeding
    +-- unit/
       +-- test_watcher.py        # NEW — unit tests for watcher.py functions
       # Note: test_models.py, test_lore_init.py, and test_python_api.py are also modified
```

The `lore` command is registered as a `console_scripts` entry point in `pyproject.toml`, pointing to `lore.cli:main`. The `__main__.py` module enables `python -m lore` invocation as an alternative.

## Module Descriptions

| Module | Description |
|--------|-------------|
| `cli.py` | All Click command definitions. Entry point `main`. Routes every CLI invocation. |
| `db.py` | SQLite connection setup, schema constants (`SCHEMA_VERSION`), and all database operations (CRUD for quests, missions, dependencies, and board messages — `add_board_message()`, `delete_board_message()`, `get_board_messages()`). Return types remain `sqlite3.Row` / `list[sqlite3.Row]` / `dict` — not typed model instances. Does not contain a `get_ready_missions` wrapper; use `lore.priority.get_ready_missions` directly. |
| `models.py` | The public typed API for Realm. Exports typed `@dataclass(frozen=True)` classes for all boundary entity types, status enums, and a type alias. All names are listed in `__all__`. See [lore.models Public API](#loremodels-public-api) below. |
| `ids.py` | `generate_id()` — hash-based short ID generation with collision detection. |
| `priority.py` | `get_ready_missions()` — priority queue SQL and result assembly for `lore ready`. |
| `root.py` | `find_project_root()` — upward directory traversal to locate `.lore/`. Raises `ProjectNotFoundError` when none is found. See tech-arch-project-root-detection (lore codex show tech-arch-project-root-detection). |
| `init.py` | `lore init` implementation: creates `.lore/` directory, seeds database, copies defaults (doctrines, knights, artifacts), writes `AGENTS.md`. Provides `_copy_defaults_tree(source_package, target_dir, exclude=None, label="artifacts")` — recursive tree copier with an exclude set and a `label` parameter that controls the prefix shown in status messages (e.g., `label="knights/default"` emits `Created knights/default/...`). The former `_copy_defaults` flat copier has been removed — all three seeding calls now use `_copy_defaults_tree`. |
| `oracle.py` | `generate_reports()` — wipes and recreates `.lore/reports/` on every run, generating `summary.md` and per-quest/per-mission markdown files. |
| `doctrine.py` | Two-file doctrine model (`.yaml` + `.design.md`). Public API: `list_doctrines(doctrines_dir)` — scans `*.design.md` files, pairs with `.yaml` counterparts, returns only complete pairs (orphaned/unpaired files silently skipped); `show_doctrine(id, doctrines_dir)` — loads both files, validates YAML schema, normalises steps, returns `{id, title, summary, design, raw_yaml, steps}`; `create_doctrine(name, yaml_src, design_src, doctrines_dir)` — validates both source files, writes both to `doctrines_dir`. Internal pipeline: `_validate_yaml_schema(data, name)`, `_validate_design_frontmatter(meta, name)`, `_validate_steps`, `_check_cycles`, `_normalize`. Delegates frontmatter parsing to `frontmatter.parse_frontmatter_doc`. `DoctrineError` propagated to CLI. Removed: `load_doctrine`, `validate_doctrine_content`, `scaffold_doctrine`. |
| `codex.py` | Codex document scanning (`scan_codex`), single-document retrieval by ID (`read_document`), keyword search over titles and summaries (`search_documents`), BFS graph traversal (`map_documents`), and probabilistic random-walk traversal (`chaos_documents`). `map_documents(codex_dir, start_id, depth)` performs BFS over `related` frontmatter links and returns a list of document dicts in traversal order (or `None` if the root ID is not found). `chaos_documents(codex_dir, start_id, threshold, rng=None)` performs a bidirectional-adjacency random walk and returns a non-deterministic subset of reachable documents (or `None` if the seed ID is not found). Private helper `_read_related(filepath, index)` extracts and validates `related` links from a single document's frontmatter; used by both traversal functions. No write operations. Dict contracts unchanged — typed `CodexDocument` class lives in `models.py`. Delegates frontmatter parsing to `frontmatter.parse_frontmatter_doc` (metadata-only for scan and `_read_related`) and `frontmatter.parse_frontmatter_doc_full` (includes body for show). No longer reads each file twice. |
| `artifact.py` | Artifact file scanning (`scan_artifacts`) and retrieval by ID (`read_artifact`). No write operations. Dict contracts unchanged — typed `Artifact` class lives in `models.py`. `scan_artifacts` uses `rglob("*.md")` on the `artifacts_dir` root. Delegates frontmatter parsing to `frontmatter.parse_frontmatter_doc` (metadata-only for scan) and `frontmatter.parse_frontmatter_doc_full` (includes body for show). No longer reads each file twice. |
| `validators.py` | Pure-utility input validators. No imports from any `lore.*` module. Called by both `db.py` (authoritative enforcement) and `cli.py` (UX error translation). Functions: `validate_message`, `validate_entity_id`, `validate_mission_id`, `validate_priority`, `validate_name`, `validate_quest_id_loose`, `route_entity`, `validate_chaos_threshold`. |
| `paths.py` | Canonical path helpers for the `.lore/` directory tree. Centralises the magic string `".lore"` and all sub-path arithmetic. Also provides `derive_group(filepath, base_dir)` — derives a GROUP string from intermediate directory components joined with `-`. Provides `watchers_dir(root)`, `glossary_path(root)` → `<root>/.lore/codex/glossary.yaml`, and `config_path(root)` → `<root>/.lore/config.toml`. Imported by `cli.py`, `oracle.py`, `db.py`, `knight.py`, `doctrine.py`, `artifact.py`, `watcher.py`, `glossary.py`, and `config.py`. |
| `glossary.py` | Glossary YAML filesystem operations + matcher. Public entry points: `scan_glossary(root)` (returns `[]` if file missing; raises `GlossaryError` on parse/schema fail), `read_glossary_item(root, keyword)` (case-insensitive lookup; aliases NOT lookup keys), `search_glossary(root, query)` (substring match across keyword/aliases/do_not_use/definition), `match_glossary(bodies, root=...)` (canonical-only token-run match), `find_deprecated_terms(bodies, root=...)` (do_not_use-only scan returning `(item, doc_id, term)` tuples). Internal: `_normalise_tokens(text)` (`re.compile(r"[^\w]+", re.UNICODE).split` + `casefold`), `_build_lookup(items)` (token-tuple → item with source tag), `_scan_runs(tokens, lookup)` (longest-prefix match). Renderer `_render_glossary_block(items)` produces the `## Glossary` text block for `cli.codex_show`. `GlossaryError` is the parse/schema failure exception. Imports `lore.paths`, `lore.schemas`, `lore.frontmatter`. |
| `config.py` | Project config TOML loader. `@dataclass(frozen=True) Config` with `show_glossary_on_codex_commands: bool = True` and `extras: Mapping[str, object]` (preserves unknown keys, forward-compatible). `DEFAULT_CONFIG = Config()`. `load_config(root)` reads `.lore/config.toml` via stdlib `tomllib`; returns `DEFAULT_CONFIG` on missing file (silent) or malformed TOML / wrong-type known key (one-time stderr warning). `_FROM_TOML` maps kebab-case TOML keys to snake_case dataclass fields. `Config` is internal — NOT in `lore.models.__all__` until Realm asks (FR-14, ADR-010). Imports stdlib only (`tomllib`, `dataclasses`) plus `lore.paths`. |
| `knight.py` | Filesystem operations for knight files. `list_knights(knights_dir)` returns sorted list of `{"id", "group", "title", "summary", "name", "filename"}` dicts; parses YAML frontmatter via `frontmatter.parse_frontmatter_doc` with fallback to filename stem when frontmatter is absent or incomplete. `find_knight(knights_dir, name)` returns a `Path` or `None`; raises `ValueError` for path-traversal attempts (name containing `/` or `\\`). Imports `derive_group` from `paths.py` and `parse_frontmatter_doc` from `frontmatter.py`. Mirrors `doctrine.py` in structure. Imported by `cli.py`. |
| `watcher.py` | Watcher YAML filesystem operations. `list_watchers(watchers_dir)` returns sorted list of dicts with all 8 fields. `find_watcher(watchers_dir, name)` returns `Path | None`; raises `ValueError` for path-traversal. `load_watcher(filepath)` returns full watcher dict including `group` and `filename`. `create_watcher`, `update_watcher`, `delete_watcher` — file write operations; all raise `ValueError` on bad input. Uses `yaml.safe_load` (not `frontmatter.py`) because watcher files are pure YAML, not markdown. Mirrors `knight.py` in structure. |
| `frontmatter.py` | Shared frontmatter parsing for markdown files with YAML front matter. `parse_frontmatter_doc(filepath, required_fields=("id","title","summary"), extra_fields=())` returns a metadata-only record dict or `None`. `parse_frontmatter_doc_full(filepath, required_fields=("id","title","summary"), extra_fields=())` returns the same dict including `body`, reading the file exactly once. The `required_fields` parameter specifies which frontmatter fields must be present; the default `("id","title","summary")` applies to all callers. The `extra_fields` parameter allows callers to extract additional frontmatter keys (e.g., `extra_fields=("related",)` used by `_read_related` in `codex.py`). `parse_frontmatter_raw(filepath) -> tuple[dict|None, str|None]` returns the full raw frontmatter mapping (preserving every key on disk, including unknown ones) or `(None, error)` distinguishing missing-frontmatter from yaml-parse failure — used exclusively by `schemas.validate_entity_file` because schema validation needs the full mapping, not a filtered record. Imported by `codex.py`, `artifact.py`, `knight.py`, and `schemas.py`. |
| `schemas.py` | Single authoritative home for entity JSON Schemas. Loads the packaged YAML schemas from `src/lore/schemas/` once per process via `importlib.resources`. Public functions: `load_schema(kind)` (cached), `validate_entity(kind, data)` (pure-data; returns a list of `(rule, pointer, message)` tuples using `jsonschema.Draft202012Validator.iter_errors`), and `validate_entity_file(path, kind)` (dispatches by kind: full-yaml kinds call `yaml.safe_load`; frontmatter kinds call `frontmatter.parse_frontmatter_raw`, and emits the `yaml-parse` / `missing-frontmatter` / `read-failed` special rules). Consumed by both `lore.health._check_schemas` at audit time and by `doctrine._validate_yaml_schema`, `doctrine._validate_design_frontmatter`, and the equivalent create-time validators in `knight.py`, `watcher.py`, `artifact.py` — no schema content is duplicated anywhere else in the codebase (DRY / FR-19 / FR-20). |
| `graph.py` | Graph algorithms on mission dependency sets. `topological_sort_missions(missions, edges)` takes mission dicts and intra-quest edge dicts, returns missions in topological order. Cycle-safe: unvisited missions appended in original order. Imported by `cli.py` (`_show_quest`). |

## `py.typed` — PEP 561 Marker

`src/lore/py.typed` is an empty file that signals to mypy and pyright that `lore` ships
inline type annotations. Without it, both type checkers treat `lore` as an untyped
third-party library even when `models.py` contains complete annotations.

Hatchling includes `py.typed` automatically — no `pyproject.toml` changes are needed.
The `packages = ["src/lore"]` declaration covers all files under `src/lore/`.

## `lore.models` Public API

`lore/models.py` is the stable import surface for Realm. The canonical import pattern:

```python
from lore.models import Quest, Mission, QuestStatus, MissionStatus
```

`lore/__init__.py` is **not** modified with a wildcard re-export. If `from lore import Quest`
is desired, add explicit named imports to `__init__.py` — never `from lore.models import *`.

### Exported Names (`__all__`)

| Name | Category | Description |
|------|----------|-------------|
| `QuestStatus` | StrEnum | `OPEN`, `IN_PROGRESS`, `CLOSED` |
| `MissionStatus` | StrEnum | `OPEN`, `IN_PROGRESS`, `BLOCKED`, `CLOSED` |
| `DependencyType` | Literal type alias | `Literal["blocks"]` — one legal value |
| `Quest` | DB-backed dataclass | Frozen; reflects `quests` schema exactly |
| `Mission` | DB-backed dataclass | Frozen; reflects `missions` schema exactly |
| `Dependency` | DB-backed dataclass | Frozen; reflects `dependencies` schema exactly |
| `BoardMessage` | DB-backed dataclass | Frozen; reflects read-side contract (no `deleted_at`) |
| `DoctrineStep` | File-based dataclass | Frozen; one step in a Doctrine workflow |
| `Doctrine` | File-based dataclass | Frozen; fields: `id`, `title`, `summary`, `steps: tuple[DoctrineStep, ...]`. `name` and `description` removed (breaking change). |
| `Artifact` | File-based dataclass | Frozen; `content` field maps from `read_artifact()["body"]` |
| `CodexDocument` | File-based dataclass | Frozen; four-field listing contract (no `body`) |
| `Knight` | File-based dataclass | Frozen; `name` (stem) and `content` (markdown body) |
| `Watcher` | File-based dataclass | Frozen; single dataclass for both list and full-load; `watch_target`, `interval`, `action` are `object` type (untyped) |
| `GlossaryItem` | File-based dataclass | Frozen; fields: `keyword: str`, `definition: str`, `aliases: tuple[str, ...]`, `do_not_use: tuple[str, ...]`. No `id` field — `keyword` is the natural key. `from_dict({...})` round-trips; missing optional keys default to empty tuple. |

### StrEnum Compatibility

`QuestStatus` and `MissionStatus` use a Python 3.10 compatibility shim:

```python
try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, enum.Enum):
        def __str__(self) -> str:
            return self.value
```

This ensures `str(QuestStatus.OPEN)` and `f"{mission.status}"` return `"open"`, not
`"QuestStatus.OPEN"`. Equality comparisons (`quest.status == "open"`) work without change.

### Priority Values

`priority` is a plain `int` in range 0–4. No `Priority` enum exists.

| Value | Meaning |
|-------|---------|
| 0 | Critical |
| 1 | High |
| 2 | Normal (default) |
| 3 | Low |
| 4 | Backlog |

### Hydration Pattern: `from_row()` and `from_dict()`

DB-backed types are constructed from `db.py` return values via classmethods.
`db.py` return types are **not changed** — the typed layer sits on top.

| Type | Classmethod | Source |
|------|-------------|--------|
| `Quest` | `from_row(row: sqlite3.Row)` | `db.get_quest()`, `db.list_quests()` |
| `Mission` | `from_row(row: sqlite3.Row)` | `db.get_mission()`, `db.get_missions_for_quest()`, `priority.get_ready_missions()` |
| `Dependency` | `from_row(row: sqlite3.Row)` | No current public caller — DB gap; see note below |
| `BoardMessage` | `from_dict(d: dict)` | `db.get_board_messages()` returns `list[dict]` |
| `Artifact` | `from_dict(d: dict)` | `artifact.read_artifact()` — maps `body` → `content` |
| `CodexDocument` | `from_dict(d: dict)` | `codex.scan_codex()` or `codex.read_document()` |
| `Doctrine` | `from_dict(d: dict)` | `doctrine.show_doctrine(id, doctrines_dir)` — accepts `{id, title, summary, steps}` |
| `DoctrineStep` | `from_dict(d: dict)` | Each step dict in the normalized `steps` list |
| `Knight` | Direct construction | No scanner function; supply `name` and `content` directly |
| `Watcher` | `from_dict(d: dict)` | `watcher.load_watcher(path)` or `watcher.list_watchers(dir)[i]` |

**`auto_close` coercion:** `Quest.from_row()` coerces `bool(row["auto_close"])` explicitly.
SQLite returns `auto_close` as an `int` (0 or 1); the `Quest.auto_close` field is `bool`.

**`from_dict()` uses explicit field mapping:** All `from_dict()` classmethods assign
fields by name, never `cls(**d)`. This prevents `TypeError` from unexpected keys in the
source dict (e.g., `body`, `path`, `valid` keys present in scan-module output).

**`Doctrine.from_dict()` input:** Accepts the dict from `doctrine.show_doctrine(id, doctrines_dir)` — shape `{id, title, summary, steps}`. Does **not** accept `doctrine.list_doctrines()` output (which has no `steps` key). `Doctrine` fields changed: `name` and `description` removed; `id`, `title`, `summary` added. This is a **breaking API change** — Realm code using `Doctrine.from_dict()` with the old `{name, description, steps}` shape must be updated.

**`CodexDocument` body:** The `body` field is excluded from `CodexDocument`. Realm that
needs full document content calls `codex.read_document(root, doc_id)` and reads `body`
from the returned dict directly.

**`Artifact.content`:** The `content` field maps from the `body` key in `read_artifact()`
output. The `path` key in `scan_artifacts()` output is excluded — `Path` objects are
not serialisable and expose filesystem layout.
