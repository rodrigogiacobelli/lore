---
id: conceptual-entities-rite
title: Rite
summary: "What a Rite is — Lore's procedural-memory entity, the how-to counterpart of the semantic/factual codex. A main rite is a pure-YAML node-graph of steps ending in typed conclusions; a shared step is a reusable pure procedure pulled in with use. Rites live in their own .lore/rites/ store, are found by AI-as-matcher via lore rite list, and are linked to only from the codex side via the rites frontmatter field."
related: ["conceptual-entities-doctrine", "conceptual-entities-glossary", "conceptual-workflows-rite-list", "conceptual-workflows-rite-show", "conceptual-workflows-rite-search", "conceptual-workflows-rite-crud", "conceptual-workflows-health", "decisions-014-link-direction", "decisions-015-rites-writable-file-entity", "ref-lore_cli-commands", "tech-arch-schemas"]
---

# Rite

A Rite is Lore's **procedural memory** — the "how to do or diagnose recurring
task X" entity. It is the how-to counterpart of the codex (lore codex show
conceptual-entities-glossary for the related vocabulary layer; the codex itself
is described in `codex`). The codex is cemented as **semantic/factual** knowledge
("what is true"); a Rite holds **procedural** knowledge ("what to do, step by
step"). A Rite is a distinct entity, not a codex layer or document type.

Rites live in their own store, `.lore/rites/`, a sibling of `.lore/codex/`. The
store has two subfolders: `main/` holds full rites and `shared/` holds reusable
shared steps. Each subfolder is scanned **recursively** — a rite may live in any
nested subdirectory, and its path relative to `main/`/`shared/` derives a
**`group`** used for display and filtering only. Like the codex, a rite's
**identity is its `id:` field**, globally unique across the entire `main/` +
`shared/` tree; the subfolder path is **cosmetic** and never participates in
identity (decisions-016-rite-json-envelope-omits-group).

## Core Concepts

| Term | Definition |
|------|------------|
| **Main rite** | A full procedure stored at `.lore/rites/main/<id>.yaml`. Internally a node-graph: a list of `nodes` connected by `then`/`goto` edges, terminating in typed `conclusions`. Carries the retrieval cues `summary` and `trigger`. |
| **Shared step** | A reusable pure procedure stored at `.lore/rites/shared/<id>.yaml`. Has exactly four fields — `id`, `title`, `summary`, `do` — a single exit, no branching, no conclusions. Carries `summary` (the one-line "what it does") but no `trigger`. A main rite pulls it in with `use:`. A shared step is a *step*, NOT a small rite: no own nodes, no recursion. |
| **Node** | One step inside a main rite. Either a `do`-node (prose action) or a `use`-node (runs a shared step) — never both. Routes onward via `then`. |
| **`then` / `goto`** | The edge between nodes. `then` is a straight edge (a node id or a conclusion key) or a fork (a list of `if`/`goto` branches). |
| **Conclusion** | A typed terminal outcome of a main rite: a key under `conclusions:` with `audience` and `response`. A node reaches it via `then`/`goto`. |
| **Trigger** | Prose retrieval cue on a main rite ("Customer requests a refund…"). Browsed by an agent during AI-as-matcher retrieval; never matched by Python. |
| **AI-as-matcher** | The only retrieval model. An agent reads the list of triggers/summaries from `lore rite list` and picks the match itself. Lore never matches a "situation". |

## How It Works

### A main rite is an in-rite node-graph

Each main rite is internally a directed graph. `nodes` are the steps; the `then`
field (or `goto` inside a fork branch) is the edge. The graph starts at the one
node with no inbound edge (the entry) and every path terminates in a
`conclusions:` key. Judgment — the branching decisions — lives **in the rite's
own nodes**, never in a shared step. Forks are expressed as a list of `if`/`goto`
pairs under `then`.

The node-graph lives *inside* one rite, as content. The **collection** of rites
is NOT a graph — there is no cross-rite traversal, no `map`/`chaos`/`impacts`
over rites. That is why the command surface is trimmed (see
conceptual-workflows-rite-list and siblings).

### Main rite vs shared step

| | Main rite (`main/`) | Shared step (`shared/`) |
|---|---|---|
| Purpose | A complete procedure | A reusable sub-procedure |
| Shape | node-graph + conclusions | `id`, `title`, `summary`, `do` (four fields) |
| `summary` (what it does) | yes | **yes** |
| `trigger` (when to use) | yes | **no** — MAIN-rite-only |
| Nodes | yes — its node-graph | none |
| Branching / judgment | yes — in its nodes | **never** — single exit |
| Conclusions | required | none |
| `use:` others | yes (a node may `use:` a shared step) | **no** — shared steps don't `use:` (no recursion) |
| Found via | `lore rite list` (AI-as-matcher) | reached via a main rite's `use:`; rarely browsed (`lore rite list --shared`) |

Both main rites and shared steps carry `summary` — the one-line "what it does",
the universal cross-entity summary convention (tech-arch-frontmatter). Only main
rites add `trigger` (the retrieval cue, "when to use"), plus nodes and
conclusions. Adopting `summary` does NOT blur the main-vs-shared boundary: a
shared step stays a pure single-exit procedure with no nodes, no branching, no
conclusions, and no `trigger`.

A shared step exists only to be consumed. Its judgment-free, single-exit shape is
enforced by schema (required keys are exactly `id`, `title`, `summary`, `do`, and
any `nodes`/`then`/`conclusions`/`use`/`goto`/`trigger` key is rejected by
`additionalProperties: false`). The consuming rite supplies the judgment around
the step.

### Retrieval — AI-as-matcher only

An agent finds a rite by reading `lore rite list` (which shows each main rite's
`trigger` and `summary`) and picking the one that fits the situation. Python
never matches a situation. `lore rite search` is a keyword browse over
`id`/`title`/`summary`/`trigger`, **not** a situational matcher. Situational
scoring (ACT-R activation / utility-outcome) is **deferred** — it is not in this
version, has no field, and must not be documented as shipping behaviour.

### Relationship to the codex

The codex is the source of truth — documentation. A Rite is not documentation;
it is an organised how-to derived from it. Links live on the **codex side only**:
a codex doc names the rites it governs via its `rites:` frontmatter field
(codex → rite). Rites carry no outbound links — no `related`, no `binds`. See
decisions-014-link-direction (lore codex show decisions-014-link-direction) for
the full edge model. `rites:` is a **secondary discovery path**, not retrieval —
a main rite with no codex pointer is still found via `lore rite list`.

### Rite vs Doctrine

A Rite is easy to confuse with a Doctrine (lore codex show
conceptual-entities-doctrine), but they sit at different layers:

| | Doctrine | Rite |
|---|---|---|
| What it is | A template that **spawns** quests and missions | Procedural knowledge for executing/diagnosing a task |
| When it acts | Upstream **planning** — an orchestrator reads it to create work | At **execution** time — any agent reads it to do the task |
| Audience | Orchestrators (planning) | Any agent (knight or not) doing the work |
| Authoring | Authored workflow template | Procedural how-to, often distilled and rewritten |

A Doctrine says "to build feature X, create these missions in this order". A Rite
says "to issue a refund, follow these steps and branch on these conditions".

## Lifecycle

Rites are a **writable** file entity with full CRUD — unlike the read-only codex
(see decisions-015-rites-writable-file-entity). They are authored, edited,
deleted, and read through `lore rite` (and the parity `lore.api` functions):

```
new ──→ edit ──→ (delete: soft-delete to <id>.yaml.deleted)
```

- **Create** — `lore rite new <name> [--shared] [--group <path>] --from <path>`
  (or stdin). Places the file at `main/<group>/<name>.yaml` (or `shared/...`);
  `--group` is optional (root if omitted). Validates the name, the `--group`
  path, and the YAML body against the schema before write; enforces id
  uniqueness across the ENTIRE `main/` + `shared/` tree (every subfolder).
- **Edit** — `lore rite edit <id> [--shared]`. Locates the rite by its bare id
  via a recursive scan, replaces its body in place, re-validates, refuses
  create-via-edit. `--shared` selects the schema, not the lookup.
- **Delete** — `lore rite delete <id>`. Locates by bare id recursively;
  soft-delete by renaming to `<id>.yaml.deleted`; deleted rites are invisible to
  scan/list/show/search/health.

See conceptual-workflows-rite-crud (lore codex show conceptual-workflows-rite-crud).

## Python API

The rite types and functions are re-exported through `lore.api.__all__` (the
public surface, ADR-010). Functions live in the `lore.rite` operational module
and take `rites_dir: Path`:

```python
from lore.api import (
    scan_rites, read_rite, search_rites,
    create_rite, update_rite, delete_rite,
    Rite, RiteNode, RiteBranch, RiteConclusion, SharedStep, RiteError,
    validate_rite_id,
)
```

`Rite`, `RiteNode`, `RiteBranch`, `RiteConclusion`, and `SharedStep` are frozen
dataclasses; `Rite.from_dict()` round-trips `read_rite`/`scan_rites` output.
`RiteBranch.if_` maps from the YAML `if` key (`if` is a Python keyword).
`RiteError` (a `ValueError` subclass) is raised for not-found / dangling `use:` /
invalid input.

## Edge Cases

- **Recursive + grouped.** Rites support `--group` nesting on `new` and a GROUP
  column + `--filter` on `list`, like every other entity. The subfolder path
  derives a cosmetic `group` (root → empty/`null`); JSON envelopes CARRY the
  `group` key (decisions-016-rite-json-envelope-omits-group).
- **Globally-unique ids (codex model).** A rite id is unique across the ENTIRE
  `main/` + `shared/` tree — the same id in two files anywhere (two subfolders,
  or `main/` vs `shared/`) is a collision (a `use: x` would be ambiguous).
  Enforced by create-time duplicate detection and a `duplicate_rite_id` health
  check. `use:`, `show`, `edit`, and `delete` all resolve by bare id across the
  whole tree.
- **Shared steps don't recurse.** A shared step has no `use:`; `lore rite show`
  inlines `use:`-referenced steps flat, with no recursion.
- **Orphan asymmetry.** An orphan **shared step** (no main rite `use:`es it) is a
  health **warning** — shared exists only to be used. An orphan **main rite** (no
  codex `rites:` points to it) is **NOT** flagged — it is found via `lore rite
  list`, the same posture as inbound-orphan sources.
- **Required fields.** Main rite: `id, title, summary, trigger, nodes,
  conclusions`. Shared step: `id, title, summary, do` (four fields, each
  `minLength: 1`). Missing any is a schema error (tech-arch-schemas).
- **No outbound links.** A rite carrying `related` or `binds` is a schema error —
  the schemas are `additionalProperties: false` (decisions-014-link-direction).
- **Deferred, not present.** Scoring/activation and `authored | distilled`
  provenance tiers are explicitly out of scope for this version — no field, no
  behaviour. Do not treat them as shipping.

## Related

- Doctrine (lore codex show conceptual-entities-doctrine) — the planning-template entity a Rite is often confused with
- conceptual-workflows-rite-list (lore codex show conceptual-workflows-rite-list) — `lore rite list` behaviour
- conceptual-workflows-rite-show (lore codex show conceptual-workflows-rite-show) — `lore rite show` with shared-step inlining
- conceptual-workflows-rite-search (lore codex show conceptual-workflows-rite-search) — `lore rite search` keyword browse
- conceptual-workflows-rite-crud (lore codex show conceptual-workflows-rite-crud) — `lore rite new/edit/delete`
- decisions-014-link-direction (lore codex show decisions-014-link-direction) — codex → rite link direction
- decisions-015-rites-writable-file-entity (lore codex show decisions-015-rites-writable-file-entity) — why rites have full CRUD
- conceptual-workflows-health (lore codex show conceptual-workflows-health) — the rite health-check set
