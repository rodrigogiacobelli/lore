---
id: api-reference
title: lore.api — Reference
summary: Exhaustive per-symbol reference for lore.api — signatures, return shapes, raised exceptions, and one-line examples for every name in lore.api.__all__.
related:
  - api-guide
  - decisions-010-public-api-stability
  - tech-arch-schemas
---

# lore.api — Reference

Every symbol in `lore.api.__all__`. Signatures are copied from the source. For narrative and end-to-end examples, see [`api-guide`](api-guide).

Throughout this doc, `pr` stands for `project_root: Path` — the directory containing `.lore/`.

## 1. Quest CRUD

### `create_quest`

Create a new quest.

```python
create_quest(project_root: Path, title: str, description: str = "", priority: int = 2, auto_close: int = 0) -> dict
```

Returns `{"id": quest_id, "filename": None, "group": None}`.

Raises: `ValueError` if priority is out of range `[0, 4]`.

```python
create_quest(pr, "Ship API guide", priority=1)
```

### `read_quest`

Fetch a single quest by ID; excludes soft-deleted.

```python
read_quest(project_root: Path, quest_id: str) -> dict | None
```

Returns a quest dict (full row) or `None` on miss. Renamed from `get_quest`.

Raises: none — miss returns `None`.

```python
q = read_quest(pr, "q-7a3f")
```

### `update_quest`

Edit a quest. Only non-`None` fields are updated.

```python
update_quest(project_root: Path, quest_id: str, title: str | None = None, description: str | None = None, priority: int | None = None, auto_close: int | None = None) -> dict
```

Returns `{"id": quest_id, "filename": None}`.

Raises: `ValueError` on miss, soft-deleted target, or invalid priority.

```python
update_quest(pr, "q-7a3f", priority=0)
```

### `update_quest_full`

Edit a quest and return the full post-edit envelope (same shape as `get_quest_detail`).

```python
update_quest_full(project_root: Path, quest_id: str, *, title=None, description=None, priority=None, auto_close=None) -> dict
```

Returns the full quest-detail envelope (id, title, status, priority, missions, …).

Raises: `ValueError` on miss / soft-deleted / invalid priority.

```python
update_quest_full(pr, "q-7a3f", title="New title")
```

### `delete_quest`

Soft-delete a quest, optionally cascading to its missions.

```python
delete_quest(project_root: Path, quest_id: str, cascade: bool = False) -> dict
```

Returns `{"id", "deleted": True, "deleted_at", "cascade": list[str] | None}`. Idempotent — re-delete returns the same envelope with the prior `deleted_at`.

Raises: `ValueError` if the quest does not exist.

```python
delete_quest(pr, "q-7a3f", cascade=True)
```

### `list_quests`

List quests sorted by priority asc, then `created_at` asc.

```python
list_quests(project_root: Path, include_closed: bool = False) -> list[dict]
```

Returns a list of quest dicts.

Raises: none.

```python
for q in list_quests(pr): ...
```

### `close_quest`

Close a quest by ID.

```python
close_quest(project_root: Path, quest_id: str) -> dict
```

Returns `{"ok": bool, "status": str, "closed_at": str | None, "already_closed": bool, "error": str | None}`.

Raises: none — failures surface via `ok=False` / `error`.

```python
close_quest(pr, "q-7a3f")
```

## 2. Mission CRUD and lifecycle

### `create_mission`

Create a new mission. If `quest_id` is `None` and exactly one non-closed quest exists, that quest is inferred.

```python
create_mission(project_root: Path, title: str, quest_id: str | None = None, description: str = "", priority: int = 2, knight: str | None = None, mission_type: str | None = None) -> dict
```

Returns `{"id": mission_id, "filename": None, "group": None}`.

Raises: `ValueError` if the named quest does not exist or priority is invalid.

```python
create_mission(pr, "Draft guide", quest_id="q-7a3f", knight="tech-writer")
```

### `read_mission`

Fetch a single mission by ID; excludes soft-deleted.

```python
read_mission(project_root: Path, mission_id: str) -> dict | None
```

Returns a mission dict or `None` on miss. Renamed from `get_mission`.

Raises: none.

```python
m = read_mission(pr, "q-7a3f/m-001")
```

### `update_mission`

Edit a mission. Only non-`None` fields are updated. Pass `remove_knight=True` to drop the knight assignment.

```python
update_mission(project_root: Path, mission_id: str, title=None, description=None, priority=None, knight=None, remove_knight: bool = False, mission_type=None) -> dict
```

Returns `{"id": mission_id, "filename": None}`.

Raises: `ValueError` on miss / soft-deleted / invalid priority.

```python
update_mission(pr, "q-7a3f/m-001", priority=1)
```

### `update_mission_full`

Edit a mission and return the full post-edit envelope.

```python
update_mission_full(project_root: Path, mission_id: str, *, title=None, description=None, priority=None, knight=None, remove_knight=False, mission_type=None) -> dict
```

Returns the full mission-detail envelope including `dependencies: {needs, blocks}` as `list[str]` of mission IDs.

Raises: `ValueError` on miss / soft-deleted / invalid priority.

```python
update_mission_full(pr, "q-7a3f/m-001", title="New title")
```

### `delete_mission`

Soft-delete a mission, drop its dependencies, re-derive parent quest status.

```python
delete_mission(project_root: Path, mission_id: str) -> dict
```

Returns `{"id", "deleted": True, "deleted_at"}`. Idempotent.

Raises: `ValueError` if the mission does not exist.

```python
delete_mission(pr, "q-7a3f/m-001")
```

### `list_missions`

List missions grouped by `quest_id`. `None` key holds standalone missions.

```python
list_missions(project_root: Path, quest_id: str | None = None, include_closed: bool = False) -> dict[str | None, list[dict]]
```

Returns `{quest_id_or_None: [mission_dict, ...]}` sorted by priority then `created_at` within each group.

Raises: none.

```python
groups = list_missions(pr)
```

### `list_missions_grouped`

List missions grouped by quest with the quest title and `deleted_at` annotated. Dashboard-shaped.

```python
list_missions_grouped(project_root: Path, *, quest_id: str | None = None, include_closed: bool = False) -> dict
```

Returns `{"groups": [{"quest_id", "quest_title", "quest_deleted_at", "missions": [...]}]}`. Each mission has exact keys `id, quest_id, title, status, priority, mission_type, knight, created_at`.

Raises: none.

```python
list_missions_grouped(pr, include_closed=True)
```

### `claim_mission`

Transition a mission from `open` to `in_progress`. Recomputes parent quest status.

```python
claim_mission(project_root: Path, mission_id: str) -> dict
```

Returns `{"ok": bool, "status": str | None, "error": str | None, "quest_id": str | None, "quest_status_changed": bool, "quest_status": str | None}`.

Raises: none.

```python
claim_mission(pr, "q-7a3f/m-001")
```

### `claim_missions`

Bulk-claim. Per-mission `BEGIN IMMEDIATE` — one failure does not roll back earlier successes.

```python
claim_missions(project_root: Path, mission_ids: list[str]) -> dict
```

Returns `{"updated": [...], "quest_status_changed": [...], "errors": [...]}`.

Raises: none.

```python
claim_missions(pr, ["q-7a3f/m-001", "q-7a3f/m-002"])
```

### `close_mission`

Close a mission, cascade-unblock dependents, recompute quest status.

```python
close_mission(project_root: Path, mission_id: str) -> dict
```

Returns `{"ok": bool, "status": str, "error": str | None, "quest_closed": bool}`.

Raises: none.

```python
close_mission(pr, "q-7a3f/m-001")
```

### `close_entities`

Close a mixed list of mission and quest IDs. Quests dispatch via `close_quest`; missions inline with coalesced quest-status recompute.

```python
close_entities(project_root: Path, entity_ids: list[str]) -> dict
```

Returns `{"updated": [...], "quest_closed": [...], "errors": [...]}`. Already-closed entities are no-op successes counted in `updated`.

Raises: none.

```python
close_entities(pr, ["q-7a3f", "q-7a3f/m-001"])
```

### `block_mission`

Block a mission with a reason. Valid: `open`/`in_progress` → `blocked`.

```python
block_mission(project_root: Path, mission_id: str, reason: str) -> dict
```

Returns `{"ok": bool, "status": str, "error": str | None}`.

Raises: `ValueError` on empty reason or invalid ID.

```python
block_mission(pr, "q-7a3f/m-001", "waiting on review")
```

### `unblock_mission`

Return a blocked mission to `open`.

```python
unblock_mission(project_root: Path, mission_id: str) -> dict
```

Returns `{"ok": bool, "status": str, "error": str | None}`.

Raises: none.

```python
unblock_mission(pr, "q-7a3f/m-001")
```

### `get_ready_missions`

Return unblocked open missions sorted by priority then `created_at`. Backs `lore ready`.

```python
get_ready_missions(project_root: Path, count: int = 1) -> list[sqlite3.Row]
```

Returns up to `count` ready missions as `sqlite3.Row` objects (column-indexable like a dict).

Raises: none.

```python
for row in get_ready_missions(pr, count=5):
    print(row["id"], row["title"])
```

## 3. Knight CRUD

### `create_knight`

Create a knight markdown file under `.lore/knights/[group/]<name>.md`.

```python
create_knight(project_root: Path, name: str, content: str, *, group: str | None = None) -> dict
```

Returns `{"id", "filename", "group"}`. Validates name format, group, content, frontmatter schema, and subtree-wide duplicate.

Raises: `ValueError` on any validation failure.

```python
create_knight(pr, "tech-writer", content_with_frontmatter)
```

### `read_knight`

Return the full knight record dict, or `None` on miss.

```python
read_knight(project_root: Path, name: str) -> dict | None
```

Returns `{"id", "group", "title", "summary", "filename", "body"}`.

Raises: `ValueError` on path-traversal names (`/` or `\` in name).

```python
read_knight(pr, "tech-writer")
```

### `update_knight`

Overwrite an existing knight markdown file in place. Validates frontmatter before any disk write.

```python
update_knight(project_root: Path, name: str, content: str) -> dict
```

Returns `{"id": name, "filename": str}`.

Raises: `ValueError` on path-traversal, miss, empty content, or invalid frontmatter.

```python
update_knight(pr, "tech-writer", new_content)
```

### `delete_knight`

Soft-delete by renaming `{name}.md` to `{name}.md.deleted`. Idempotent.

```python
delete_knight(project_root: Path, name: str) -> dict
```

Returns `{"id": name, "deleted": True, "deleted_at": None}`.

Raises: `ValueError` on path-traversal names or if neither live file nor `.deleted` sibling exists.

```python
delete_knight(pr, "tech-writer")
```

### `list_knights`

Return a sorted list of knight records under `.lore/knights/`. Missing-metadata records get sensible fallbacks.

```python
list_knights(project_root: Path, filter_groups: list[str] | None = None) -> list[dict]
```

Returns `[{"id", "group", "title", "summary", "name", "filename"}, ...]` sorted by id. Empty list if the directory is absent.

Raises: none.

```python
list_knights(pr)
```

## 4. Doctrine CRUD

### `create_doctrine`

Register both YAML + design source files atomically under `.lore/doctrines/`.

```python
create_doctrine(project_root: Path, name: str, yaml_source_path: Path, design_source_path: Path, *, group: str | None = None) -> dict
```

Returns `{"id", "filename", "group", "design_filename"}`.

Raises: `ValueError` on name/group format, duplicate, or missing/invalid source files.

```python
create_doctrine(pr, "tdd-feature", Path("d.yaml"), Path("d.design.md"))
```

### `read_doctrine`

Load a doctrine by ID for display.

```python
read_doctrine(project_root: Path, doctrine_id: str) -> dict | None
```

Returns `{"id", "title", "summary", "design", "raw_yaml", "steps"}` or `None` if either partner file is missing.

Raises: none.

```python
read_doctrine(pr, "tdd-feature")
```

### `update_doctrine`

Overwrite an existing doctrine YAML file with merged content. The design file is not touched here — that requires direct file edits.

```python
update_doctrine(project_root: Path, name: str, content: str) -> dict
```

Returns `{"id": name, "filename": f"{name}.yaml"}`.

Raises: `ValueError` on miss, missing dir, name-format failure, or schema/name-match failure.

```python
update_doctrine(pr, "tdd-feature", new_yaml)
```

### `delete_doctrine`

Soft-delete both partner files atomically.

```python
delete_doctrine(project_root: Path, name: str) -> dict
```

Returns `{"id": name, "deleted": True, "deleted_at": None}`. Renames `{name}.yaml` and `{name}.design.md` to `.deleted` siblings.

Raises: `ValueError` on missing target.

```python
delete_doctrine(pr, "tdd-feature")
```

### `list_doctrines`

List all valid doctrine pairs. Orphaned files are silently skipped.

```python
list_doctrines(project_root: Path, filter_groups: list[str] | None = None) -> list[dict]
```

Returns `[{"id", "group", "title", "summary", "valid", "filename"}, ...]`.

Raises: none.

```python
list_doctrines(pr)
```

## 5. Artifact CRUD

### `create_artifact`

Create a new artifact markdown file under `.lore/artifacts/[group/]<name>.md`. Auto-creates the target directory.

```python
create_artifact(project_root: Path, name: str, content: str, *, group: str | None = None) -> dict
```

Returns `{"id", "filename", "group"}`. Validates name, group, content, frontmatter required fields, and subtree-wide duplicate.

Raises: `ValueError` on any validation failure.

```python
create_artifact(pr, "pr-template", content_with_frontmatter)
```

### `read_artifact`

Return the artifact record dict or `None` on miss.

```python
read_artifact(project_root: Path, artifact_id: str) -> dict | None
```

Returns `{"id", "title", "summary", "body", "filename", "group"}`.

Raises: none.

```python
read_artifact(pr, "pr-template")
```

### `update_artifact`

Overwrite an existing artifact in place.

```python
update_artifact(project_root: Path, name: str, content: str) -> dict
```

Returns `{"id": name, "filename": str}`.

Raises: `ValueError` on validation failure.

```python
update_artifact(pr, "pr-template", new_content)
```

### `delete_artifact`

Soft-delete via `.deleted` rename. Idempotent.

```python
delete_artifact(project_root: Path, name: str) -> dict
```

Returns `{"id": name, "deleted": True, "deleted_at": None}`.

Raises: `ValueError` if neither live file nor `.deleted` sibling exists.

```python
delete_artifact(pr, "pr-template")
```

### `list_artifacts`

Walk `.lore/artifacts/` recursively.

```python
list_artifacts(project_root: Path, filter_groups: list[str] | None = None) -> list[dict]
```

Returns `[{"id", "title", "summary", "group", "path"}, ...]` sorted alphabetically by id. Files without valid frontmatter are silently skipped.

Raises: none.

```python
list_artifacts(pr)
```

## 6. Watcher CRUD

### `create_watcher`

Create a watcher YAML file under `.lore/watchers/`.

```python
create_watcher(project_root: Path, name: str, content: str, *, group: str | None = None) -> dict
```

Returns `{"id", "filename", "group"}`.

Raises: `ValueError` for invalid name/group, duplicate, empty content, or invalid YAML.

```python
create_watcher(pr, "nightly-audit", yaml_content)
```

### `read_watcher`

Return the full watcher record dict, or `None` on miss.

```python
read_watcher(project_root: Path, name: str) -> dict | None
```

Returns `{"id", "group", "title", "summary", "filename", "watch_target", "interval", "action"}`.

Raises: none.

```python
read_watcher(pr, "nightly-audit")
```

### `update_watcher`

Overwrite an existing watcher YAML.

```python
update_watcher(project_root: Path, name: str, content: str) -> dict
```

Returns `{"id": name, "filename": str}`.

Raises: `ValueError` for invalid name, not-found, empty content, or invalid YAML.

```python
update_watcher(pr, "nightly-audit", new_yaml)
```

### `delete_watcher`

Soft-delete by renaming `{name}.yaml` to `{name}.yaml.deleted`.

```python
delete_watcher(project_root: Path, name: str) -> dict
```

Returns `{"id": name, "deleted": True, "deleted_at": None}`.

Raises: `ValueError` for path-traversal names or missing target.

```python
delete_watcher(pr, "nightly-audit")
```

### `list_watchers`

Walk `.lore/watchers/` recursively.

```python
list_watchers(project_root: Path, filter_groups: list[str] | None = None) -> list[dict]
```

Returns `[{"id", "group", "title", "summary", "watch_target?", "interval?", "action?"}, ...]` sorted by id.

Raises: none.

```python
list_watchers(pr)
```

## 7. Codex CRUD and read ops

### `create_document`

Create a new codex markdown file under `.lore/codex/[group/]<name>.md`.

```python
create_document(project_root: Path, name: str, content: str, *, group: str | None = None, doc_type: str | None = None) -> dict
```

Returns `{"id", "filename", "group", "doc_type"}`.

Frontmatter is validated against the **overlay-merged** codex schema (it passes `project_root` to `validate_entity`), so a custom key declared in `.lore/custom-schemas/<kind>.yaml` is accepted at write time and an undeclared key is still rejected. Exception: a doc created under `group="transient"` (anything landing in `.lore/codex/transient/`) validates against the **packaged** schema alone — overlays do not reach the transient subtree, so a declared custom key is rejected there as an unknown property (ADR-019).

Raises: `ValueError` on validation, duplicate, or schema failure — including `OverlayError` (a `ValueError`) when the project overlay is malformed.

```python
create_document(pr, "014-use-sqlite", content, group="decisions")
```

### `read_document`

Return a full document record by ID.

```python
read_document(project_root: Path, doc_id: str) -> dict | None
```

Returns `{"id", "title", "summary", "body"}`. Leading newlines stripped from body.

Raises: none.

```python
read_document(pr, "api-guide")
```

### `update_document`

Overwrite an existing codex doc with new content (frontmatter + body).

```python
update_document(project_root: Path, name: str, content: str) -> dict
```

Returns `{"id", "filename", "group", "doc_type", "updated_at"}`.

Frontmatter is re-validated against the overlay-merged codex schema (same `project_root` path as `create_document`), including the same transient carve-out — a doc under `.lore/codex/transient/` is re-validated against the packaged schema alone.

Raises: `ValueError` on not-found / schema / parse failure — including `OverlayError` (a `ValueError`) when the project overlay is malformed.

```python
update_document(pr, "api-guide", new_content)
```

### `delete_document`

Hard-delete via `.deleted` rename. Refuses reserved seeded doc IDs.

```python
delete_document(project_root: Path, name: str) -> dict
```

Returns `{"id", "deleted", "deleted_at", "group", "doc_type"}`. Idempotent on already-deleted docs.

Raises: `ValueError` on not-found or reserved seed ID.

```python
delete_document(pr, "old-doc")
```

### `list_codex`

Walk `.lore/codex/` recursively. Filter-aware.

```python
list_codex(project_root: Path, filter_groups: list[str] | None = None) -> list[dict]
```

Returns `[{"id", "title", "summary", "path"}, ...]` sorted alphabetically by id. Files missing required frontmatter are silently skipped.

Raises: none.

```python
list_codex(pr, filter_groups=["decisions"])
```

### `search_documents`

Substring search across title and summary, case-insensitive.

```python
search_documents(project_root: Path, keyword: str) -> list[dict]
```

Returns `[{"id", "title", "summary"}, ...]` sorted alphabetically by id.

Raises: none.

```python
search_documents(pr, "sqlite")
```

### `map_documents`

BFS the codex graph from `start_id` along the `related` field. Separate inbound/outbound depth budgets.

```python
map_documents(project_root: Path, start_id: str, *, depth: int | None = None, depth_out: int | None = None, depth_in: int | None = None, full: bool = False) -> list[dict] | None
```

Returns a list of neighbour records (seed excluded, dedup by id, sorted alphabetically). Default shape `{"id", "group", "title", "summary"}`; `full=True` adds `related` and `body`. `None` iff `start_id` is not in the index.

Raises: `ConflictingDepthFlags` if `depth` is combined with `depth_out`/`depth_in`.

```python
map_documents(pr, "api-guide", depth=2)
```

### `chaos_documents`

Random-walk traversal from `start_id`. Terminates when discovered/reachable ratio crosses the threshold.

```python
chaos_documents(project_root: Path, start_id: str, threshold: int, *, rng: random.Random | None = None) -> list[dict] | None
```

Returns a list of records starting with the seed. `None` iff `start_id` is missing.

Raises: `ValueError` if threshold is outside `[30, 100]`.

```python
chaos_documents(pr, "api-guide", threshold=60)
```

### `read_documents_with_glossary`

Compose a `{documents, glossary}` envelope. Used by `lore codex show`.

```python
read_documents_with_glossary(project_root: Path, doc_ids: list[str], *, skip_glossary: bool = False) -> dict
```

Returns `{"documents": [...], "glossary": [...]}`. Missing doc ids appear in place as `{"id": "<id>", "not_found": True}`.

Raises: none — missing docs fail soft.

```python
read_documents_with_glossary(pr, ["api-guide", "api-reference"])
```

## 8. Glossary

### `create_glossary_item`

Append a new item to `.lore/codex/glossary.yaml`. Top-of-file comments are preserved; inline item-level comments are dropped.

```python
create_glossary_item(project_root: Path, keyword: str, definition: str, *, aliases: list[str] | None = None, do_not_use: list[str] | None = None) -> dict
```

Returns `{"keyword": str, "filename": "glossary.yaml"}`.

Raises: `ValueError` on empty keyword/definition, schema violation, duplicate keyword (case-insensitive), or missing glossary file.

```python
create_glossary_item(pr, "Quest", "A live grouping of Missions.")
```

### `read_glossary_item`

Look up an item by exact keyword (case-insensitive). Aliases are NOT consulted (FR-7).

```python
read_glossary_item(root: Path, keyword: str) -> GlossaryItem | None
```

Returns a `GlossaryItem` dataclass or `None`.

Raises: `GlossaryError` on malformed glossary file.

```python
read_glossary_item(pr, "quest")
```

### `update_glossary_item`

Mutate the matched item in-place. `None` means "leave unchanged"; `aliases=[]` explicitly clears.

```python
update_glossary_item(project_root: Path, keyword: str, *, definition: str | None = None, aliases: list[str] | None = None, do_not_use: list[str] | None = None) -> dict
```

Returns `{"keyword": str, "filename": "glossary.yaml"}`.

Raises: `ValueError` on missing file, item not found, schema violation, or no-op call (every kwarg `None`).

```python
update_glossary_item(pr, "Quest", definition="New definition.")
```

### `delete_glossary_item`

Hard-delete the matched item. Idempotent — missing keyword is not an error.

```python
delete_glossary_item(project_root: Path, keyword: str) -> dict
```

Returns `{"keyword": str, "deleted": True, "deleted_at": str}`.

Raises: `ValueError` only when the glossary file is missing or invalid.

```python
delete_glossary_item(pr, "Quest")
```

### `scan_glossary`

Return all items in source order. Empty list if file missing.

```python
scan_glossary(root: Path) -> list[GlossaryItem]
```

Returns a list of `GlossaryItem` dataclasses.

Raises: `GlossaryError` on read error, malformed YAML, or schema violation.

```python
scan_glossary(pr)
```

### `search_glossary`

Case-insensitive substring search across keyword, aliases, do_not_use, and definition.

```python
search_glossary(root: Path, query: str) -> list[GlossaryItem]
```

Returns a list of items alphabetised by casefolded keyword.

Raises: `GlossaryError` on read/parse failure.

```python
search_glossary(pr, "task")
```

### `match_glossary`

Return canonical items whose keyword/aliases appear in the supplied bodies. `do_not_use` does NOT auto-surface.

```python
match_glossary(bodies: list[str], *, items: list[GlossaryItem] | None = None, root: Path | None = None) -> list[GlossaryItem]
```

Returns deduped items alphabetised by casefolded keyword. Missing glossary file → `[]`.

Raises: `GlossaryError` on malformed glossary.

```python
match_glossary(["Quest and mission and knight"], root=pr)
```

## 9. Field-level frontmatter editing

### `update_frontmatter_fields`

Mutate one or more frontmatter fields of a file-backed entity without rewriting the body. Body bytes are passed through verbatim.

```python
update_frontmatter_fields(project_root: Path, kind: str, name: str, *, set_fields: dict | None = None, unset_fields: list | None = None, add_to_list: dict | None = None, remove_from_list: dict | None = None) -> dict
```

`kind` ∈ `{"knight", "doctrine", "artifact", "watcher", "codex"}`. Schema validation runs against the mutated frontmatter BEFORE any disk write — invalid edits leave the file untouched. Write is atomic via tempfile + `os.replace`.

For `kind="codex"` validation is **overlay-merged**: the function resolves its overlay root through `codex._overlay_root`, so a canonical or `sources/` doc validates against the merged schema and a doc under `.lore/codex/transient/` validates against the packaged schema alone (ADR-019). This is what makes the CLI backfill of a newly `required` custom field possible — `set_fields={"owner": "alice"}` on a declared custom key now passes instead of failing `Unknown property 'owner'`.

Returns `{"id": name, "filename": str, "updated_at": None}`.

Raises: `ValueError` on validation / lookup / schema failure — including `OverlayError` (a `ValueError`) when the project overlay is malformed.

```python
update_frontmatter_fields(pr, kind="codex", name="api-guide", set_fields={"summary": "New."})
```

## 10. Board messages

### `add_board_message`

Insert a board message for the given entity (quest or mission).

```python
add_board_message(project_root: Path, entity_id: str, message: str, sender: str | None = None) -> dict
```

Returns `{"id", "entity_id", "sender", "created_at"}`.

Raises: `ValueError` on invalid entity ID, empty message, unknown entity, or soft-deleted entity.

```python
add_board_message(pr, "q-7a3f", "kickoff", sender="rodrigo")
```

### `list_board_messages`

Return all non-deleted board messages for an entity, oldest first.

```python
list_board_messages(project_root: Path, entity_id: str) -> list[dict]
```

Returns a list of message dicts.

Raises: none.

```python
list_board_messages(pr, "q-7a3f")
```

### `delete_board_message`

Soft-delete by global integer ID, scoped to `entity_id` to prevent cross-entity collision.

```python
delete_board_message(project_root: Path, entity_id: str, message_id: int) -> dict
```

Returns `{"id", "deleted": True, "deleted_at"}`.

Raises: `ValueError` if the message does not exist (or is already soft-deleted) or if `entity_id` does not match the stored value.

```python
delete_board_message(pr, "q-7a3f", message_id=42)
```

## 11. Dependencies

### `add_dependency`

Create a single dependency edge (`from_id` depends on `to_id`).

```python
add_dependency(project_root: Path, from_id: str, to_id: str) -> dict
```

Returns `{"from": from_id, "to": to_id, "created": True}`.

Raises: `ValueError` on missing mission, duplicate edge, or cycle.

```python
add_dependency(pr, "q-7a3f/m-002", "q-7a3f/m-001")
```

### `remove_dependency`

Soft-delete a single edge. Missing dependency is not an error.

```python
remove_dependency(project_root: Path, from_id: str, to_id: str) -> dict
```

Returns `{"from", "to", "removed": bool}`. `removed=False` when the edge did not exist.

Raises: none.

```python
remove_dependency(pr, "q-7a3f/m-002", "q-7a3f/m-001")
```

### `add_dependencies`

Bulk-add via single-shot dispatch. Per-pair `BEGIN IMMEDIATE`.

```python
add_dependencies(project_root: Path, pairs: list[tuple[str, str]]) -> dict
```

Returns `{"created": [...], "existing": [...], "errors": [...]}`. Each entry is `{"from", "to"}` (NEVER `from_id`/`to_id`).

Raises: none — per-pair failures roll into `errors`.

```python
add_dependencies(pr, [("m-002", "m-001"), ("m-003", "m-001")])
```

### `remove_dependencies`

Bulk-remove via single-shot dispatch.

```python
remove_dependencies(project_root: Path, pairs: list[tuple[str, str]]) -> dict
```

Returns `{"removed": [...], "not_found": [...], "errors": [...]}`.

Raises: none.

```python
remove_dependencies(pr, [("m-002", "m-001")])
```

### `list_mission_depends_on`

Missions that `mission_id` depends on.

```python
list_mission_depends_on(project_root: Path, mission_id: str) -> list[dict]
```

Returns `[{"id", "title", "status"}, ...]`. Renamed from `get_mission_depends_on_details`.

Raises: none.

```python
list_mission_depends_on(pr, "q-7a3f/m-002")
```

### `list_mission_blocks`

Missions that depend on `mission_id`.

```python
list_mission_blocks(project_root: Path, mission_id: str) -> list[dict]
```

Returns `[{"id", "title", "status"}, ...]`.

Raises: none.

```python
list_mission_blocks(pr, "q-7a3f/m-001")
```

### `get_all_dependencies_for_quest`

All active dependency edges where `from_id` belongs to the quest. Cross-quest upstream nodes are included.

```python
get_all_dependencies_for_quest(project_root: Path, quest_id: str) -> list[dict]
```

Returns `[{"from_id": ..., "to_id": ...}, ...]`.

Raises: none.

```python
get_all_dependencies_for_quest(pr, "q-7a3f")
```

## 12. Impacts engine

### `impacts`

Surface codex↔code bindings for *token*. Token classification (codex-seed vs code-seed) determines the return mode.

```python
impacts(token: str, *, project_root: Path, direct_links: bool = False) -> ImpactsResult
```

Codex-seed: returns `ImpactsResult(kind="codex", codex_items=tuple[CodexBinding, ...])` preserving declaration order.

Code-seed: returns `ImpactsResult(kind="code", code_items=tuple[CodeBinding, ...])` sorted by codex id, deduped per id with exact-precedence over glob. `direct_links=True` drops glob rows.

Raises: `ImpactsError` on unknown codex id, outside-repo path, or `..` traversal.

```python
impacts("api-guide", project_root=pr)
```

### `classify_token`

Pure classifier: `"path"` if token contains `/` or `.`, else `"codex"`.

```python
classify_token(token: str) -> Literal["codex", "path"]
```

Returns the literal `"codex"` or `"path"`.

Raises: none.

```python
classify_token("src/lore/api.py")  # -> "path"
```

## 13. Health and schemas

### `health_check`

Audit all six file-based entity types and return a `HealthReport`. Pure read-only by default — `write_report=True` writes a markdown report into `.lore/codex/transient/`.

```python
health_check(project_root: Path | None = None, scope: list[str] | None = None, scopes: list[str] | None = None, *, write_report: bool = False, timestamp: str | None = None) -> HealthReport
```

Returns a `HealthReport(errors, warnings, report_path, schemas_ran)`. Never prints.

Raises: `ValueError` when `scope`/`scopes` contains an unknown token.

```python
report = health_check(pr, scope=["codex"])
```

### `validate_entity`

Validate an in-memory dict against a named schema.

```python
validate_entity(kind: str, data: Any, *, project_root: Path | None = None) -> list[SchemaIssue]
```

Returns a list of `SchemaIssue(rule, pointer, message)`. Never raises on validation failure.

When `project_root` is passed and `kind` is overlay-eligible (`codex-frontmatter`, `codex-source-frontmatter`), validation uses the merged validator from `project_validator_for(kind, project_root)` (packaged default + the project overlay at `.lore/custom-schemas/<kind>.yaml`). When `project_root=None` (default) or the kind is not overlay-eligible, behaviour is identical to the packaged-only path. The keyword is additive (minor bump, ADR-010).

Raises: `FileNotFoundError` if `kind` is not a known schema; `OverlayError` (a `ValueError`) if the project overlay is malformed.

```python
issues = validate_entity("knight-frontmatter", {"id": "x", "title": "X", "summary": "..."})
issues = validate_entity("codex-frontmatter", meta, project_root=pr)  # overlay-aware
```

### `resolve_merged_schema`

Resolve the effective schema for a codex kind, merging the project overlay onto the packaged default.

```python
resolve_merged_schema(kind: str, project_root: Path) -> dict[str, Any]
```

Returns the packaged schema unchanged when no `.lore/custom-schemas/<kind>.yaml` overlay exists; otherwise a deep copy with the overlay's `properties` injected and `required` appended, `additionalProperties` pinned `false`. Add-only — packaged fields are never redefined.

Raises: `OverlayError` (a `ValueError`) on unparseable YAML, non-mapping top-level, a property colliding with a packaged field, or a `required` entry not declared in the overlay.

```python
resolve_merged_schema("codex-frontmatter", pr)
```

### `project_validator_for`

Build (and cache) the project-aware merged validator for a codex kind.

```python
project_validator_for(kind: str, project_root: Path) -> Draft202012Validator
```

Cached on `(kind, project_root, overlay_mtime_ns)` — an edited overlay yields a fresh validator within a long-running process. Wraps `resolve_merged_schema`.

Raises: `OverlayError` (a `ValueError`) when the overlay is malformed.

```python
project_validator_for("codex-source-frontmatter", pr)
```

### `validate_entity_file`

Validate a file on disk against a named schema. Dispatches on `-yaml` suffix vs frontmatter parser.

```python
validate_entity_file(path: str, kind: str) -> list[SchemaIssue]
```

Returns a list of `SchemaIssue`. Never raises on read/parse failure.

Raises: none.

```python
validate_entity_file(".lore/knights/foo.md", "knight-frontmatter")
```

### `load_schema`

Load a packaged JSON Schema YAML resource by kind. Cached.

```python
load_schema(kind: str) -> dict[str, Any]
```

Returns the parsed schema dict (same object on repeat calls).

Raises: `FileNotFoundError` with message `"Unknown schema kind: '<kind>'"` when the kind does not exist.

```python
load_schema("knight-frontmatter")
```

## 14. Stats and dashboard

### `get_aggregate_stats`

Aggregate counts of quests and missions by status.

```python
get_aggregate_stats(project_root: Path) -> dict
```

Returns a dict with quest and mission count breakdowns.

Raises: none.

```python
get_aggregate_stats(pr)
```

### `get_dashboard_quests`

Non-closed quests with mission count breakdowns. Sorted by priority asc, then `created_at` asc.

```python
get_dashboard_quests(project_root: Path) -> list[dict]
```

Returns `[{"id", "title", "status", "priority", "missions": {"open", "in_progress", "blocked", "closed"}}, ...]`.

Raises: none.

```python
get_dashboard_quests(pr)
```

### `get_mission_detail`

Full mission-detail envelope (byte-for-byte matches `lore show` JSON output).

```python
get_mission_detail(project_root: Path, mission_id: str, *, include_knight: bool = True) -> dict | None
```

Returns the full envelope including `dependencies` and resolved `knight`. `None` on miss.

Raises: none.

```python
get_mission_detail(pr, "q-7a3f/m-001")
```

### `get_quest_detail`

Full quest-detail envelope. Missions in insertion order — no topological sort.

```python
get_quest_detail(project_root: Path, quest_id: str) -> dict | None
```

Returns the full envelope. `None` on miss.

Raises: none.

```python
get_quest_detail(pr, "q-7a3f")
```

### `get_missions_for_quest`

Missions for a quest sorted by status group (open/in_progress, blocked, closed), priority, then `created_at`.

```python
get_missions_for_quest(project_root: Path, quest_id: str) -> list[dict]
```

Returns a list of mission dicts.

Raises: none.

```python
get_missions_for_quest(pr, "q-7a3f")
```

### `get_deleted_at`

Return the `deleted_at` timestamp of a quest or mission, else `None`. Routes by ID format.

```python
get_deleted_at(project_root: Path, entity_id: str) -> str | None
```

Returns an ISO timestamp string or `None`.

Raises: none.

```python
get_deleted_at(pr, "q-7a3f")
```

### `delete_entity`

Polymorphic soft-delete dispatching by ID format via `route_entity`.

```python
delete_entity(project_root: Path, entity_id: str, *, cascade: bool = False) -> dict
```

Returns the underlying `delete_quest` / `delete_mission` envelope verbatim.

Raises: `ValueError` on unknown entity ID.

```python
delete_entity(pr, "q-7a3f", cascade=True)
```

## 15. Reports

### `generate_reports`

Generate markdown reports in `.lore/reports/`. Side-effect-only — no return value.

```python
generate_reports(project_root: Path) -> None
```

Returns `None`.

Raises: none.

```python
generate_reports(pr)
```

### `run_init`

Run the full `lore init` sequence in the current working directory. Creates `.lore/`, seeds defaults, initialises the database.

```python
run_init() -> list[str]
```

Returns a list of human-readable status messages describing each step.

Raises: none under normal use; filesystem errors propagate.

```python
run_init()
```

### `load_config`

Load `<root>/.lore/config.toml` into a `Config`. Fail-soft: missing file or malformed TOML returns defaults with a one-time stderr line; unknown keys are preserved in `Config.extras`.

```python
load_config(root: Path) -> Config
```

Returns a `Config(show_glossary_on_codex_commands, extras)`.

Raises: none — all failure modes fall back to defaults.

```python
load_config(pr)
```

## 16. Project root and paths

### `find_project_root`

Walk upward from `start` looking for a `.lore/` directory.

```python
find_project_root(start: Path | None = None) -> Path
```

Returns the directory containing `.lore/`.

Raises: `ProjectNotFoundError` if no `.lore/` is found up to the filesystem root.

```python
project_root = find_project_root()
```

### `entity_location`

Return the on-disk location for a file-backed entity. Does NOT create any directory.

```python
entity_location(project_root: Path, kind: str, name: str | None = None, *, group: str | None = None, suffix: str | None = None) -> Path
```

`kind` ∈ `{"knight", "doctrine", "artifact", "watcher", "codex"}`. With `name=None` and `suffix=None`, returns the (group-scoped) directory. With both, returns the full file path.

Raises: `ValueError` on unknown kind.

```python
entity_location(pr, kind="codex", group="api")
```

### `get_connection`

Open a connection to the project database with standard pragmas (WAL, busy timeout, FK enforcement). Runs pending migrations before returning.

```python
get_connection(project_root: Path) -> sqlite3.Connection
```

Returns a `sqlite3.Connection`.

Raises: standard SQLite errors on db failure.

```python
conn = get_connection(pr)
```

### `init_database`

Initialize the SQLite database with the full schema.

```python
init_database(db_path: Path) -> str
```

Returns a status string: `"created"`, `"existing"`, or `"reinitialized"`.

Raises: standard SQLite errors.

```python
init_database(pr / ".lore" / "lore.db")
```

## 17. Validators

Pure functions for input validation. Each returns `None` on success or a human-readable error string. None raise.

### `validate_message`

```python
validate_message(message: str) -> str | None
```

Returns an error string if `message` is empty/whitespace, else `None`.

### `validate_entity_id`

```python
validate_entity_id(eid: str) -> str | None
```

Returns an error string if `eid` is not a valid quest or mission ID.

### `validate_mission_id`

```python
validate_mission_id(mid: str) -> str | None
```

Returns an error string if `mid` is not a valid mission ID.

### `validate_priority`

```python
validate_priority(priority: int | None) -> str | None
```

Returns an error string if `priority` is out of `[0, 4]`.

### `validate_name`

```python
validate_name(name: str) -> str | None
```

Returns an error string if `name` is not a valid knight/doctrine name.

### `validate_group`

```python
validate_group(group: str | None) -> str | None
```

Returns an error string if `group` is not a safe group path.

### `validate_quest_id_loose`

```python
validate_quest_id_loose(quest_id: str) -> str | None
```

Returns an error string if `quest_id` does not match the loose quest ID pattern.

### `validate_chaos_threshold`

```python
validate_chaos_threshold(value: int) -> tuple[bool, str | None]
```

Returns `(True, None)` if value is within `[30, 100]`, else `(False, error_message)`.

### `validate_binds_entry`

```python
validate_binds_entry(s: object) -> str | None
```

Returns an error string if `s` is not a valid `binds:` entry.

### `is_glob_pattern`

```python
is_glob_pattern(s: str) -> bool
```

Returns `True` iff `s` contains any of `*`, `?`, `[`.

### `route_entity`

```python
route_entity(eid: str) -> tuple[str, str]
```

Returns `(table, id_col)` for a valid entity ID.

Raises: `ValueError` on unrecognised entity IDs.

## 18. Types and enums

All exported types are frozen `@dataclass` classes or `StrEnum` subclasses.

### Enums

- **`QuestStatus`** — `OPEN`, `IN_PROGRESS`, `CLOSED`.
- **`MissionStatus`** — `OPEN`, `IN_PROGRESS`, `BLOCKED`, `CLOSED`.
- **`DependencyType`** — one value: `"blocks"`.

### Domain dataclasses

- **`Quest(id, title, description, status, priority, auto_close, created_at, updated_at, closed_at, deleted_at)`** — full quest row.
- **`Mission(id, quest_id, title, description, status, mission_type, priority, knight, block_reason, created_at, updated_at, closed_at, deleted_at)`** — full mission row.
- **`Dependency(id, from_id, to_id, type, deleted_at)`** — `type` is `Literal["blocks"]`.
- **`BoardMessage(id, entity_id, sender, message, created_at)`** — single board message.
- **`Artifact(id, title, summary, content)`** — minimal artifact projection.
- **`CodexDocument(id, title, summary)`** — minimal codex doc projection.
- **`DoctrineStep(id, title, priority, type, knight, notes, needs)`** — one step of a doctrine.
- **`Doctrine(id, title, summary, steps)`** — `steps` is `tuple[DoctrineStep, ...]`.
- **`Knight(name, content)`** — name + raw markdown body.
- **`DoctrineListEntry(id, group, title, summary, valid, filename)`** — `lore doctrine list` row shape.
- **`GlossaryItem(keyword, definition, aliases, do_not_use)`** — `aliases` and `do_not_use` are `tuple[str, ...]`.
- **`Watcher(id, group, title, summary, watch_target, interval, action, filename)`** — full watcher record.

### Health and validation dataclasses

- **`HealthReport(errors, warnings, report_path, schemas_ran)`** — `errors` and `warnings` are `tuple[HealthIssue, ...]`.
- **`HealthIssue(severity, entity_type, id, check, detail, schema_id, rule, pointer)`** — one issue row.
- **`SchemaIssue(rule, pointer, message)`** — one schema validation failure.

### Impacts dataclasses

- **`ImpactsResult(kind, codex_items, code_items)`** — `kind` is `Literal["codex", "code"]`; the two `_items` fields are tuples of bindings, one populated based on `kind`.
- **`CodexBinding(path, kind)`** — `kind` is `Literal["exact", "glob"]`.
- **`CodeBinding(id, match, pattern)`** — `match` is `Literal["exact", "glob"]`; `pattern` is the glob pattern when `match="glob"`, else `None`.

### Config

- **`Config(show_glossary_on_codex_commands, extras)`** — `extras` is a `Mapping[str, object]` holding any unknown TOML keys.

### Exceptions

- **`ProjectNotFoundError`** — raised by `find_project_root` when no `.lore/` is found.
- **`ImpactsError`** — raised by `impacts(...)` on bad input.
- **`GlossaryError`** — raised by glossary reads on malformed YAML.
- **`OverlayError`** — subclass of `ValueError`; raised by `resolve_merged_schema` / `project_validator_for` / `validate_entity(project_root=...)` when a `.lore/custom-schemas/<kind>.yaml` overlay is malformed (bad YAML, packaged-field collision, undeclared `required`). Propagates unchanged through `create_document` / `update_document` (their existing `ValueError` contract).
- **`ConflictingDepthFlags`** — raised by `map_documents` on bad depth-flag combos.
