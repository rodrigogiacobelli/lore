---
id: tech-arch-source-layout
title: Source Layout
summary: The src/lore/ source tree with one-line descriptions per module, including init.py, root.py, oracle.py, doctrine.py, codex.py (including map_documents, chaos_documents, and _read_related), artifact.py, validators.py (including validate_chaos_threshold), paths.py, knight.py, frontmatter.py (including extra_fields parameter), and graph.py. Covers package entry points, defaults directory (including doctrines, knights, and artifacts/transient/), migrations directory (v1_to_v2 through v5_to_v6), py.typed PEP 561 marker, and the tests layout. Documents the lore.models public API (frozen dataclasses, from_row/from_dict pattern, __all__).
related: ["tech-overview", "standards-dry", "standards-single-responsibility"]
stability: stable
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
|      |- frontmatter.py        # Shared frontmatter parsing for markdown files (parse_frontmatter_doc, parse_frontmatter_doc_full)
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
|          |- doctrines/        # Default doctrine — the adversarial-spec pipeline (all carry top-level id, title, summary keys)
|          |  +-- adversarial-spec.yaml
|          |  +-- update-changelog.yaml
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
| `doctrine.py` | Doctrine YAML loading, normalisation pipeline (`_normalize`), validation pipeline (`_validate`, `_validate_required_fields`, `_validate_steps`, `_check_cycles`), `DoctrineError` propagation, and `validate_doctrine_content()` entry point. `list_doctrines` returns enriched dicts with `id`, `group`, `title`, `summary`, `valid` (and optionally `errors`). `_normalize` passes through `id`, `title`, `summary` if present. `validate_doctrine_content` validates that `id` matches `expected_name` when present. Dict contracts unchanged — typed `Doctrine` and `DoctrineStep` classes live in `models.py`, not here. Exports `scaffold_doctrine(name: str) -> str` — generates a placeholder YAML skeleton for `doctrine_new` when no content is supplied via stdin or `--from`. |
| `codex.py` | Codex document scanning (`scan_codex`), single-document retrieval by ID (`read_document`), keyword search over titles and summaries (`search_documents`), BFS graph traversal (`map_documents`), and probabilistic random-walk traversal (`chaos_documents`). `map_documents(codex_dir, start_id, depth)` performs BFS over `related` frontmatter links and returns a list of document dicts in traversal order (or `None` if the root ID is not found). `chaos_documents(codex_dir, start_id, threshold, rng=None)` performs a bidirectional-adjacency random walk and returns a non-deterministic subset of reachable documents (or `None` if the seed ID is not found). Private helper `_read_related(filepath, index)` extracts and validates `related` links from a single document's frontmatter; used by both traversal functions. No write operations. Dict contracts unchanged — typed `CodexDocument` class lives in `models.py`. Delegates frontmatter parsing to `frontmatter.parse_frontmatter_doc` (metadata-only for scan and `_read_related`) and `frontmatter.parse_frontmatter_doc_full` (includes body for show). No longer reads each file twice. |
| `artifact.py` | Artifact file scanning (`scan_artifacts`) and retrieval by ID (`read_artifact`). No write operations. Dict contracts unchanged — typed `Artifact` class lives in `models.py`. `scan_artifacts` uses `rglob("*.md")` on the `artifacts_dir` root. Delegates frontmatter parsing to `frontmatter.parse_frontmatter_doc` (metadata-only for scan) and `frontmatter.parse_frontmatter_doc_full` (includes body for show). No longer reads each file twice. |
| `validators.py` | Pure-utility input validators. No imports from any `lore.*` module. Called by both `db.py` (authoritative enforcement) and `cli.py` (UX error translation). Functions: `validate_message`, `validate_entity_id`, `validate_mission_id`, `validate_priority`, `validate_name`, `validate_quest_id_loose`, `route_entity`, `validate_chaos_threshold`. |
| `paths.py` | Canonical path helpers for the `.lore/` directory tree. Centralises the magic string `".lore"` and all sub-path arithmetic. Also provides `derive_group(filepath, base_dir)` — derives a GROUP string from intermediate directory components joined with `-`. Provides `watchers_dir(root)` path helper. Imported by `cli.py`, `oracle.py`, `db.py`, `knight.py`, `doctrine.py`, `artifact.py`, and `watcher.py`. |
| `knight.py` | Filesystem operations for knight files. `list_knights(knights_dir)` returns sorted list of `{"id", "group", "title", "summary", "name", "filename"}` dicts; parses YAML frontmatter via `frontmatter.parse_frontmatter_doc` with fallback to filename stem when frontmatter is absent or incomplete. `find_knight(knights_dir, name)` returns a `Path` or `None`; raises `ValueError` for path-traversal attempts (name containing `/` or `\\`). Imports `derive_group` from `paths.py` and `parse_frontmatter_doc` from `frontmatter.py`. Mirrors `doctrine.py` in structure. Imported by `cli.py`. |
| `watcher.py` | Watcher YAML filesystem operations. `list_watchers(watchers_dir)` returns sorted list of dicts with all 8 fields. `find_watcher(watchers_dir, name)` returns `Path | None`; raises `ValueError` for path-traversal. `load_watcher(filepath)` returns full watcher dict including `group` and `filename`. `create_watcher`, `update_watcher`, `delete_watcher` — file write operations; all raise `ValueError` on bad input. Uses `yaml.safe_load` (not `frontmatter.py`) because watcher files are pure YAML, not markdown. Mirrors `knight.py` in structure. |
| `frontmatter.py` | Shared frontmatter parsing for markdown files with YAML front matter. `parse_frontmatter_doc(filepath, required_fields=("id","title","summary"), extra_fields=())` returns a metadata-only record dict or `None`. `parse_frontmatter_doc_full(filepath, required_fields=("id","title","summary"), extra_fields=())` returns the same dict including `body`, reading the file exactly once. The `required_fields` parameter specifies which frontmatter fields must be present; the default `("id","title","summary")` applies to all callers. The `extra_fields` parameter allows callers to extract additional frontmatter keys (e.g., `extra_fields=("related",)` used by `_read_related` in `codex.py`). Imported by `codex.py`, `artifact.py`, and `knight.py`. |
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
| `Doctrine` | File-based dataclass | Frozen; full doctrine with `tuple[DoctrineStep, ...]` |
| `Artifact` | File-based dataclass | Frozen; `content` field maps from `read_artifact()["body"]` |
| `CodexDocument` | File-based dataclass | Frozen; four-field listing contract (no `body`) |
| `Knight` | File-based dataclass | Frozen; `name` (stem) and `content` (markdown body) |
| `Watcher` | File-based dataclass | Frozen; single dataclass for both list and full-load; `watch_target`, `interval`, `action` are `object` type (untyped) |

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
| `Doctrine` | `from_dict(d: dict)` | `doctrine.load_doctrine(path)` — the `_normalize()` output |
| `DoctrineStep` | `from_dict(d: dict)` | Each step dict in the normalized `steps` list |
| `Knight` | Direct construction | No scanner function; supply `name` and `content` directly |
| `Watcher` | `from_dict(d: dict)` | `watcher.load_watcher(path)` or `watcher.list_watchers(dir)[i]` |

**`auto_close` coercion:** `Quest.from_row()` coerces `bool(row["auto_close"])` explicitly.
SQLite returns `auto_close` as an `int` (0 or 1); the `Quest.auto_close` field is `bool`.

**`from_dict()` uses explicit field mapping:** All `from_dict()` classmethods assign
fields by name, never `cls(**d)`. This prevents `TypeError` from unexpected keys in the
source dict (e.g., `body`, `path`, `valid` keys present in scan-module output).

**`Doctrine.from_dict()` input:** Accepts the normalized dict from `doctrine.load_doctrine()`,
not from `doctrine.list_doctrines()`. The list function output includes `valid`, `errors`,
and `filename` — not valid `Doctrine.from_dict()` input.

**`CodexDocument` body:** The `body` field is excluded from `CodexDocument`. Realm that
needs full document content calls `codex.read_document(root, doc_id)` and reads `body`
from the returned dict directly.

**`Artifact.content`:** The `content` field maps from the `body` key in `read_artifact()`
output. The `path` key in `scan_artifacts()` output is excluded — `Path` objects are
not serialisable and expose filesystem layout.
