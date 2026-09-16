---
id: tech-arch-projects-module
title: Projects Module — topology, export resolution and ID qualification
summary: 'Technical reference for src/lore/projects.py and its companion src/lore/scoped.py.
  Covers ProjectRef and ExportCandidate, the ID algebra (qualify, split_qualified,
  index_key, matches_export), the two topology walks (resolve_ancestors, discover_descendants),
  export resolution (exported_ids, exports_glossary), the collect() merge contract
  every entity module calls into, and scoped.select / scoped.locate.

  '
binds:
- src/lore/projects.py
- src/lore/scoped.py
- tests/unit/test_projects.py
related:
- conceptual-workflows-nested-projects
- tech-arch-project-root-detection
- tech-arch-source-layout
- standards-dry
- standards-single-responsibility
- standards-dependency-inversion
- standards-facade
- decisions-006-id-references
- decisions-013-toml-for-config-yaml-for-glossary
- decisions-023-export-boundary-excludes-transient-and-sources
- decisions-024-default-group-is-seeded-boundary
- decisions-025-cross-boundary-reads-are-read-only
- decisions-026-project-naming-and-addressing
- decisions-028-inheritance-unconditional-federation-opt-in
- ref-lore_api-core
---

# Projects Module — topology, export resolution and ID qualification

**Source modules:** `src/lore/projects.py` (topology, export resolution, the ID algebra) and `src/lore/scoped.py` (the two questions every entity module asks of a merged listing).

`projects.py` is the single home for three questions a tree of Lore projects raises: where are the other projects, may this entity cross a boundary, and what is this entity called from here. It imports `lore.paths`, `lore.config`, `lore.root` and `lore.validators`, plus stdlib, and imports **no** entity module — every entity module imports `projects`, never the reverse, so the dependency arrow points one way (`standards-dependency-inversion`).

## Types

```python
@dataclass(frozen=True)
class ProjectRef:
    name: str
    root: Path
    relation: str          # "self" | "ancestor" | "descendant"


@dataclass(frozen=True)
class ExportCandidate:
    entity_id: str
    group: str | None = None
    path: Path | None = None


class UnknownProjectError(Exception): ...
class ForeignEntityError(Exception): ...
```

`ExportCandidate.group` is `None` for a reader whose records carry no group (codex) — no seeded-default filter applies to those. `ExportCandidate.path` is read only to answer the codex-layer question (whether the candidate sits under `transient/` or `sources/`); it is never read for any other kind.

## The ID algebra

| Function | Behaviour |
|---|---|
| `qualify(origin, entity_id)` | `entity_id` unchanged when `origin == "self"`, else `f"{origin}:{entity_id}"`. |
| `split_qualified(token)` | Splits on the **first** `:` only. Returns `(None, token)` for a bare token. Performs no resolution — whether the left half names a real project is the caller's question. |
| `is_qualified(token)` | `split_qualified(token)[0] is not None`. |
| `index_key(entry, *, self_name)` | Normalises a `related` entry for a scoped index: an entry whose origin equals `self_name` reduces to its bare id (that document is one this project owns, named from the other side of a boundary); every other entry keeps its form. |
| `matches_export(entity_id, pattern)` | `entity_id == pattern` when `validators.is_glob_pattern(pattern)` is `False`, else `fnmatch.fnmatchcase(entity_id, pattern)` — case-sensitive on every platform, unlike bare `fnmatch.fnmatch`. |
| `is_seeded_default(group)` | `group == "default" or group.startswith("default/")`. |
| `reject_foreign(entity_id)` | Raises `ForeignEntityError('Cannot write "{id}": an entity from another project is read-only.')` when `is_qualified(entity_id)`, else returns `None`. |

Splitting on the first colon only is deliberate: codex ids are free-form non-empty strings with no pattern constraint, so a local id may itself contain a `:`. `project-name` is constrained to `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` and can never contain one, so the left half of a split is unambiguous whenever it resolves to a real project name.

## Topology

`project_name(project_root)` returns the project's own `project-name` config value when non-empty, else `project_root.name`. Never raises.

`resolve_ancestors(project_root)` walks from `project_root.parent` to the filesystem root. At each directory it probes `lore_dir(current).is_dir()` — one filesystem check — and loads that directory's config only when the probe succeeds. A directory whose config declares neither `[shared]` (non-empty `exports` or `glossary = true`) nor a `[[descendants]]` block resolving to `project_root` is walked past silently: a stray `.lore/` above a project that exports nothing is inert. Returns nearest ancestor first. Never raises — an unreadable ancestor config yields no ref for that directory, not an exception.

`discover_descendants(project_root)` walks downward with `os.walk(project_root, followlinks=False)`, pruning `.git`, `node_modules`, `.venv`, `__pycache__` and the project's own `.lore/` directory name from `dirnames` in place. A directory holding `.lore/` is a project, and the walk continues into it — a project nested inside a project is still found. A descendant whose own config is unreadable is still returned, named by its directory: a malformed config removes that project's exports, never the project itself from the tree. Sorted by name.

`list_projects(project_root)` is `resolve_scope(project_root, "all")` — self, then ancestors, then discovered descendants, in that order — rather than a second assembly of the same three parts.

`resolve_project(project_root, name)` matches a project's own resolved name (never a `[[descendants]]` block's `name` label) and raises `UnknownProjectError` with the exact CLI-facing message (naming the other projects in scope, or stating that none exists) when nothing matches.

`resolve_scope(project_root, scope)` is what every read command calls: `None` reads `default-project-scope`; `"self"` or `"all"` return `self_ref` plus `resolve_ancestors(...)`, with `discover_descendants(...)` appended under `"all"`; any other value resolves and returns exactly the one named project. The upward half is in every answer — resolving a scope never omits inheritance, because federation and inheritance are independent axes (`conceptual-workflows-nested-projects`).

Every public function resolves the topology fresh at its own entry and threads it down; there is no module-level cache. A cache keyed on a path would have to be invalidated in tests and would make the zero-scan cost guarantee for an untreed project order-dependent on test execution — the cost instead is one upward probe per call, which is the whole of the walk's budget.

## Export resolution

`exported_ids(ancestor_root, descendant_root, *, candidates)` takes the ancestor's own `(entity_id, group, path)` triples and returns the subset that (a) is not a seeded default and (b) is not an unexportable codex layer (`transient/` or `sources/`, decided via `paths.is_transient_codex_path` and `paths.derive_group` — the two existing single homes for those questions) and (c) matches at least one pattern in the union of `[shared].exports` and the one `[[descendants]]` block whose `path` resolves to `descendant_root`. A `[[descendants]]` block's identity is its `path`, resolved beneath the ancestor's root with `paths.resolve_beneath` — never its `name`, which is a label with no resolving power.

`exports_glossary(ancestor_root, descendant_root)` is `load_config(ancestor_root).shared.glossary` — the glossary exports whole or not at all, so the descendant argument exists only for symmetry with `exported_ids` and is not itself consulted.

## The merge — `collect()`

```python
def collect(
    project_root: Path,
    scope: str | None,
    *,
    read: Callable[[Path], list[dict]],
    id_key: str = "id",
    group_key: str | None = "group",
    exportable: bool = True,
) -> list[dict]: ...
```

One merge loop for every entity kind. Each entity module hands `collect` its own single-project reader; `collect` never opens an entity file itself, which is what keeps the dependency arrow pointing from every entity module toward `projects.py` and never back.

For each `ProjectRef` in `resolve_scope(project_root, scope)`, `collect` calls `read(ref.root)`. A reader that raises `OSError` contributes no rows and one stderr line (`lore: project "<name>" is unreadable: <reason>; skipped`) — the command never fails because one project in scope is unreadable. Rows from the `self` relation are tagged `origin="self"` and returned unqualified. Rows from an **ancestor** are filtered through `exported_ids` before being kept; rows from a **descendant** are never filtered — an ancestor asking for one named descendant wants that project's material, not its own exports reflected back. Every kept foreign row has its `id_key` qualified with `qualify(ref.name, ...)` and gains `"origin": ref.name`.

`group_key=None` means these records carry no group at all — `collect` never fabricates one, and no seeded-default filter runs for that reader (the codex reader is the one caller that passes this, because `list_codex`'s own records carry no `group` key). `exportable=False` suppresses the export filter entirely, for a caller (the glossary reader) that resolves its own export set before calling `collect`.

`collect` preserves each reader's own row order within a project; it does **not** sort the merged result. Sorting by the qualified id is every caller's own responsibility, applied after `collect` returns — this is what keeps result ordering a property of each entity module's documented sort key (`id`, or `(group, id)` for rites) rather than a second sort rule living in `projects.py`.

## `scoped.py` — resolving one id, and finding the file behind a row

`scoped.py` sits between `projects.py` and the entity modules: it imports the former and none of the latter, and it answers the two questions every entity module asks once `collect` has produced a merged listing.

```python
def select(records, entity_id, *, alias=None) -> dict | None: ...
def locate(project_root, scope, record) -> tuple[Path, str]: ...
```

`select` walks `records` (a merged listing, own rows first) looking for `record["id"] == entity_id`. A **qualified** `entity_id` is refused a match against any `origin == "self"` row outright, even one whose literal id text matches — a local document is never addressed by a foreign-looking id (D-8). When every exact match misses and `entity_id` is bare, `select` retries against `alias(record)` for this project's own rows only — the second local address some entity kinds have always accepted (a doctrine's directory name, which its design frontmatter `id` is free to disagree with). A foreign entity is never reachable by alias, only by its qualified id.

`locate(project_root, scope, record)` turns a row back into the project root that owns it and the bare id its owner knows it by: `(project_root, record["id"])` for a `self` row, else it re-resolves `resolve_scope` and looks the row's `origin` up by name. The topology is resolved again here rather than threaded through — the same D-26 trade `projects.py` itself makes, so a cache does not have to be invalidated in tests and call counts stay order-independent.

`scoped.SELF` (`"self"`) and `scoped.ANCESTOR` (`"ancestor"`) are the two relation/origin tokens entity modules compare against; they mirror `projects._SELF` / `projects._ANCESTOR`, which stay private to `projects.py`.
