---
id: api-guide
title: lore.api — Public API guide
summary: Narrative walkthrough of the lore.api facade — how a Python caller (Realm, custom orchestrator, scripts) drives Lore directly without shelling out to the CLI. Covers imports, per-entity CRUD, frontmatter edits, errors, and stability.
related:
  - api-reference
  - decisions-010-public-api-stability
  - decisions-011-api-parity-with-cli
  - conceptual-workflows-lore-init
  - conceptual-workflows-init-reconcile
---

# lore.api — Public API guide

## What lore.api is

`lore.api` is the single stable import surface for Lore. ADR-010 fixes the contract at `lore.api.__all__`, which spans types, validators, and operational callables. The authoritative list lives in `src/lore/api.py`. Every CLI command routes through this same facade (ADR-011), so a Python caller gets identical behaviour: same validation, same return shape, same state effects.

Internal modules (`lore.db`, `lore.codex`, `lore.knight`, …) may be renamed, split, or merged between releases. Consumers that import from them are broken by design. Import from `lore.api` only.

Two consumer profiles use this:

- **Realm and custom orchestrators** — long-lived Python processes that drive Lore as a task engine, never spawning subprocesses.
- **Scripts and migrations** — one-off Python that reads state, bulk-mutates entities, or seeds projects without the CLI's human formatting.

For exhaustive per-symbol detail, see [`api-reference`](api-reference). This doc is the narrative entry point.

## Installing and importing

Lore ships as `lore-agent-task-manager` on PyPI. Pin against the public API contract:

```python
# requirements.txt
lore-agent-task-manager>=0.x.0,<1.0
```

Every example below uses these two imports:

```python
from pathlib import Path
from lore.api import find_project_root
```

`find_project_root()` walks upward from the cwd looking for a `.lore/` directory. Every operational call takes a `project_root: Path` as its first argument — pass the result of `find_project_root()` or an explicit `Path`. Functions never read the cwd; the root is always explicit.

```python
project_root = find_project_root()  # raises ProjectNotFoundError if not in a lore project
```

## Initialising a project

Initialisation is the one operation that runs where `.lore/` may not exist, so it does not take a project root from `find_project_root()`. It splits in two: `plan_init` computes, `apply_init` writes.

```python
from lore.api import plan_init, apply_init

plan = plan_init(Path("/srv/acme"), agents=["claude"], access_mode="native")

plan.has_changes        # False means the project is already correct
plan.counts()           # {"create": 13, "section": 2, "overwrite": 0, "remove": 0, "conflict": 0}
for f in plan.conflicts:
    print(f.path, f.detail)

result = apply_init(plan)
result.messages         # the same list run_init() returns
result.skipped          # conflicts left alone under on_conflict="skip"
```

A caller that only wants to know what would happen calls `plan_init` and stops. Nothing is written until `apply_init`.

`run_init()` is the zero-argument shorthand — `apply_init(plan_init()).messages`, as a list — and its signature is pinned. An orchestrator that upgraded Lore and calls `run_init()` gets the same files it always did.

Each keyword on `plan_init` that defaults to `None` resolves argument → `.lore/config.toml` → built-in default, inside `plan_init`. There is no second reader of those keys, so a Python caller passing nothing gets exactly what a person passing no flag gets.

`plan_init` raises `ValueError` for a token the CLI would reject at exit 2 — an unknown agent id, an unknown access mode or skill family, or `agents=["none", "claude"]`. The four validators behind those checks (`validate_agent_id`, `validate_agent_selection`, `validate_access_mode`, `validate_skill_family`) are exported too, for a caller that wants to check before calling.

No prompt ever fires from `plan_init` or `apply_init`. Prompting lives in the CLI, and every prompt's effect is a keyword on `plan_init` (ADR-011).

## Per-entity walkthroughs

### Quest

A Quest is a body of work (feature, fix, refactor). The facade exposes full CRUD plus lifecycle.

```python
from lore.api import create_quest, list_quests, read_quest, close_quest

result = create_quest(project_root, title="Ship API guide", priority=1)
quest_id = result["id"]  # e.g. "q-7a3f"

for q in list_quests(project_root, include_closed=False):
    print(q["id"], q["title"], q["status"])

close_quest(project_root, quest_id)
```

Creation returns `{"id", "filename", "group"}`. `filename` and `group` are `None` for db-backed entities (Quest, Mission). Soft-delete via `delete_quest(..., cascade=True)` to also remove child missions.

### Mission

A Mission is a single executable task. It optionally belongs to a Quest (hierarchical ID `q-7a3f/m-001`) and optionally names a Knight persona.

```python
from lore.api import create_mission, claim_mission, close_mission, block_mission

m = create_mission(
    project_root,
    title="Draft api-guide.md",
    quest_id="q-7a3f",
    priority=2,
    knight="tech-writer",
    mission_type="knight",
)
mission_id = m["id"]

claim_mission(project_root, mission_id)        # open -> in_progress
block_mission(project_root, mission_id, "waiting on glossary review")
close_mission(project_root, mission_id)        # cascade-unblocks dependents
```

For UI dashboards, `list_missions_grouped` returns missions bucketed by quest with the quest title attached. For the orchestrator's "what next" loop, `get_ready_missions(project_root, count=N)` returns unblocked open missions ordered by priority.

### Knight

A Knight is a reusable agent persona — a markdown file under `.lore/knights/`.

```python
from lore.api import create_knight, read_knight, list_knights

content = """---
id: tech-writer
title: Tech Writer
summary: Drafts narrative docs and references.
---
You are a technical writer for Lore...
"""
create_knight(project_root, name="tech-writer", content=content, group=None)

knight = read_knight(project_root, "tech-writer")
print(knight["body"])
```

Returns include `{"id", "filename", "group"}` — `filename` is the relative path under `.lore/knights/`. Updates overwrite the file in place; deletes rename to `.md.deleted` for soft-delete.

### Doctrine

A Doctrine is a passive workflow template — a paired `<name>.yaml` + `<name>.design.md` under `.lore/doctrines/`.

```python
from lore.api import create_doctrine, read_doctrine

create_doctrine(
    project_root,
    name="tdd-feature",
    yaml_source_path=Path("/tmp/tdd-feature.yaml"),
    design_source_path=Path("/tmp/tdd-feature.design.md"),
)

d = read_doctrine(project_root, "tdd-feature")
for step in d["steps"]:
    print(step["title"], step.get("knight"))
```

Both source files are required and validated atomically — no partial writes.

### Artifact

An Artifact is a reusable template file under `.lore/artifacts/` with stable ID.

```python
from lore.api import create_artifact, read_artifact, list_artifacts

content = """---
id: pr-template
title: PR template
summary: Default PR description scaffold.
---
## Summary
...
"""
create_artifact(project_root, name="pr-template", content=content)
art = read_artifact(project_root, "pr-template")
print(art["body"])
```

### Watcher

A Watcher is a YAML-configured trigger definition under `.lore/watchers/`. Lore stores it but does not execute; the consuming layer (Realm, CI) runs it.

```python
from lore.api import create_watcher, list_watchers

content = """id: nightly-health
title: Nightly health audit
summary: Run lore health every night and post failures to the board.
watch_target: cron
interval: "0 2 * * *"
action: doctrine:health-audit
"""
create_watcher(project_root, name="nightly-health", content=content)
```

### Codex document

A Codex doc is a typed markdown file under `.lore/codex/<group>/`. The group derives from path.

```python
from lore.api import create_document, read_document, search_documents

content = """---
id: my-decision
title: Use SQLite for storage
summary: Why we picked SQLite over Postgres.
---
## Context
...
"""
create_document(project_root, name="014-use-sqlite", content=content, group="decisions")

hits = search_documents(project_root, "sqlite")
for h in hits:
    print(h["id"], h["title"])
```

Graph queries are first-class: `map_documents` does bidirectional BFS over the `related` field; `chaos_documents` is a random-walk traversal.

`create_document` / `update_document` validate frontmatter against the **overlay-merged** codex schema (they pass a path-scoped `project_root` through to `validate_entity`). A project that declares custom frontmatter keys in `.lore/custom-schemas/<kind>.yaml` (add-only overlay; see `tech-arch-schemas`) gets those keys accepted at write time, while undeclared keys still raise `ValueError`. The overlay reaches canonical docs and the `sources/` layer only: a doc under `.lore/codex/transient/` is validated against the packaged schema alone, so a declared custom key is rejected there (`decisions-019-overlay-scope-stops-at-transient`). A malformed overlay raises `OverlayError` (a `ValueError`). Build the merged validator directly with `project_validator_for(kind, project_root)` or validate in-memory data with `validate_entity(kind, data, project_root=pr)`.

### Glossary item

The glossary is a single YAML file at `.lore/codex/glossary.yaml`. Items are addressed by keyword (case-insensitive).

```python
from lore.api import create_glossary_item, read_glossary_item, search_glossary

create_glossary_item(
    project_root,
    keyword="Quest",
    definition="A live grouping of Missions representing a body of work.",
    aliases=["body of work"],
)

item = read_glossary_item(project_root, "quest")
print(item.definition)
```

### Board message

Board messages are short notes pinned to a quest or mission ID.

```python
from lore.api import add_board_message, list_board_messages

add_board_message(project_root, entity_id="q-7a3f", message="kickoff", sender="rodrigo")
for msg in list_board_messages(project_root, "q-7a3f"):
    print(msg["created_at"], msg["sender"], msg["message"])
```

### Dependency

Mission-to-mission dependencies form a DAG. A mission with unmet dependencies is blocked from `ready_missions`.

```python
from lore.api import add_dependency, add_dependencies, list_mission_depends_on

add_dependency(project_root, from_id="q-7a3f/m-002", to_id="q-7a3f/m-001")

# Bulk form returns {"created": [...], "existing": [...], "errors": [...]}
add_dependencies(project_root, pairs=[("q-7a3f/m-003", "q-7a3f/m-001")])

for dep in list_mission_depends_on(project_root, "q-7a3f/m-002"):
    print(dep["id"], dep["status"])
```

`add_dependency` raises on cycles and on duplicates; the bulk form rolls those into the `existing`/`errors` buckets per-pair.

## Field-level frontmatter editing

For file-backed entities (knight, doctrine, artifact, watcher, codex doc) you do not have to round-trip the whole markdown body. `update_frontmatter_fields` mutates one or more frontmatter keys in place:

```python
from lore.api import update_frontmatter_fields

update_frontmatter_fields(
    project_root,
    kind="codex",
    name="api-guide",
    set_fields={"summary": "Updated summary"},
    add_to_list={"related": ["api-reference"]},
)
```

`set_fields` overwrites scalar values; `unset_fields` drops keys; `add_to_list` and `remove_from_list` mutate list-valued keys idempotently. Schema validation runs against the mutated frontmatter before any disk write — invalid edits leave the file untouched. For `kind="codex"` that validation is **overlay-merged**, so setting a custom key declared in `.lore/custom-schemas/<kind>.yaml` succeeds — this is the backfill path when a project newly marks a custom field `required`. Docs under `.lore/codex/transient/` are validated against the packaged schema alone (`decisions-019-overlay-scope-stops-at-transient`).

## Errors and validation

Every facade function validates inputs via `lore.validators` (ADR-011, Decision 1). Failure modes:

- `ValueError` — invalid ID format, out-of-range priority, unknown entity, schema violation, empty required field. This is the default failure for CRUD.
- `ImpactsError` — `impacts(...)` only: unknown codex id, outside-repo path, or `..` traversal.
- `GlossaryError` — `scan_glossary`, `match_glossary`: malformed glossary YAML or read error.
- `OverlayError` — a `ValueError` subclass: `resolve_merged_schema`, `project_validator_for`, `validate_entity(project_root=...)`, `create_document`/`update_document`, and `update_frontmatter_fields(kind="codex", ...)` when a `.lore/custom-schemas/<kind>.yaml` overlay is malformed (bad YAML, packaged-field collision, undeclared `required`).
- `ProjectNotFoundError` — `find_project_root` could not locate `.lore/` on the upward walk.
- `ConflictingDepthFlags` — `map_documents` called with both `depth` and `depth_out`/`depth_in`.

Lookup functions (`read_quest`, `read_mission`, `read_knight`, …) return `None` on miss — they do not raise. Reserve `try/except` for the mutation surface.

```python
from lore.api import create_mission, ProjectNotFoundError

try:
    project_root = find_project_root()
except ProjectNotFoundError:
    raise SystemExit("not inside a lore project")

try:
    create_mission(project_root, title="", priority=99)
except ValueError as exc:
    print(f"bad input: {exc}")
```

For pre-flight checks without mutation, call the validators directly: `validate_mission_id`, `validate_priority`, `validate_name`, `validate_group`. Each returns `None` on success or a human-readable error string.

## Stability and versioning

`lore.api.__all__` is the public surface. ADR-010 pins the semver policy:

- Adding a name → minor bump.
- Adding a field to an exported dataclass → minor bump.
- Adding a keyword arg with a default → minor bump.
- Removing or renaming a name → major bump or explicit breaking-change notice.
- Changing positional params or return shape → major bump or explicit breaking-change notice.

Pin `lore-agent-task-manager>=0.x.0,<1.0` and trust that minor bumps are additive against `lore.api`. Anything imported from `lore.<module>` directly is outside the contract and may break on any release.

## Where to look next

- [`api-reference`](api-reference) — exhaustive per-symbol reference: signature, return shape, raises, one-line example.
- [`decisions-010-public-api-stability`](decisions-010-public-api-stability) — why the facade exists and what the semver policy guarantees.
- [`decisions-011-api-parity-with-cli`](decisions-011-api-parity-with-cli) — why every CLI command must be backed by a self-contained Python function.
