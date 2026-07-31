---
id: codex
title: Codex
summary: What this documentation system is, how it is structured, and how to use it.
  Read this before reading or writing any other file in this repository.
related:
- conceptual-entities-glossary
- conceptual-workflows-glossary
- conceptual-entities-rite
- decisions-014-link-direction
- decisions-020-codex-voice-is-enforced
---

# Codex

This is a documentation system designed to be the single source of truth for a software project. It is built for AI agents first and humans second. Every structural decision exists to help an agent find exactly what it needs without reading files that are not relevant.

Start with `lore codex list`. It is the only index. Everything else is reachable from there.

## The Layers

Documentation is divided into layers. Each layer has one job.

| Layer | Directory | Question it answers |
|-------|-----------|-------------------|
| Vision | `vision/` | Product and executive documents — what the system is, why it exists, and how it fits into the broader landscape. |
| Conceptual — Entities | `conceptual/entities/` | What is this thing and how does it behave? |
| Conceptual — Relationships | `conceptual/relationships/` | How do two entities connect and what rules govern that connection? |
| Conceptual — Workflows | `conceptual/workflows/` | What does the system do internally, or how does a user accomplish a goal? |
| Technical | `technical/` | How is this built, stored, and served? |
| API | `api/` | The public Python API surface — `api-guide` for narrative, `api-reference` for exhaustive lookup. Lore-specific layer covering `lore.api.__all__`. |
| Decisions | `decisions/` | Why was this architectural choice made and what alternatives were rejected? |
| Standards | `standards/` | How do we write code and design this system? Conventions, principles, and rules. |
| Operations | `operations/` | How is this developed, deployed, and maintained? |
| Transient | `transient/` | In-flight working documents for the current feature cycle. Deleted when the feature ships. |

The glossary lives as a single YAML file at `.lore/codex/glossary.yaml` — see conceptual-entities-glossary.

**Conceptual docs describe the system from the outside.** No file paths, no schema columns, no API endpoints. If a business analyst can read it and understand it without knowing the tech stack, it belongs in conceptual.

**Technical docs describe the system from the inside.** Database schemas, CLI command specs, source layout, infrastructure. Each component of the software gets its own subdirectory. For concrete artifacts (DB tables, API endpoints, models, events, jobs), prefer **Reference Docs** under `<technical-domain>/ref/` over schema dumps — see "Reference Docs" below.

These two trees link to each other but never duplicate. If a fact exists in a schema file, the entity file links to it — it does not repeat it. One fact, one file.

## Workflows

Workflows describe processes. The subject determines the framing:

- **System workflow** — the system is the subject. What the system does when triggered. Steps through internal logic, validations, and state changes.
- **User-facing workflow** — a user is the subject. What a person does to accomplish a goal. Indicate the role performing it in the document body.

A background job has a system workflow. A settings command may have a user-facing workflow. Creating and assigning a record has both.

## The Three Content Classes

Every file in the codex belongs to exactly one of three classes, defined by its top-level directory and by one question: **what happens when you delete it?**

| Class    | Directory                  | Deletion test |
|----------|----------------------------|---------------|
| Stable   | `vision/`, `conceptual/`, `technical/`, `api/`, `decisions/`, `standards/`, `operations/` | Deleting any file LOSES information. Never safe. |
| In-Flight | `transient/` | Safe to delete **after** the in-flight feature ships and its facts have been folded into stable docs. Validated against the packaged schema only — exempt from custom-schema overlays. |
| Sources  | `sources/<system>/<id>.md` | Safe to delete **at any time**. Every fact worth keeping already lives in a stable doc. |

**Stable** describes the system as it exists today. Never future intentions, never work in progress.

**In-flight** (`transient/`) holds work being planned or developed — PRDs, tech specs, maps, reports. Deleted when the feature ships. These docs validate against the packaged `codex-frontmatter` schema only and are exempt from project custom-schema overlays — see "Project-local custom fields" below.

**Sources** (`sources/<system>/<id>.md`) hold raw upstream material — Jira tickets, meeting transcripts, chat threads, pasted documents — captured verbatim as point-in-time snapshots. They are never canonical. Every fact that matters must be propagated into a stable doc before the source becomes deletable; after that, the source is disposable.

### Sources layout

Files live at `sources/<system>/<id>.md` where `<system>` is a free-form slug (e.g. `jira`, `slack`, `meetings`) and `<id>` is unique within that system.

### Sources frontmatter rule

Source files carry exactly four frontmatter fields: `id`, `title`, `summary`, and `related`. All four are required. `related` is a non-empty array of canonical codex IDs — the canonical docs this source caused to change. `lore health` rejects any source file with missing fields, empty `related`, or any extra field.

### Verbatim rule
  
Source bodies are preserved verbatim from upstream. Light reformatting is permitted only when the upstream format is structurally unreadable (e.g. Atlassian ADF → markdown). Semantic content must not be altered.

### One-way linking

Sources MUST link outward. Every source's `related` list names every canonical doc it caused to change — `lore codex map <source-id> --depth-out 1` returns exactly those docs. Canonical docs MUST NOT link back: no canonical doc may include a source ID in its `related` list. `lore health` enforces both directions — empty/missing `related` on a source is a schema error; a source ID appearing in any canonical doc's `related` is a `canonical_links_to_source` error.

### Refresh rule

Re-ingestion of an existing source (via `/refresh-source`) **overwrites** the snapshot file. There is no history file. Previous content is retained only in git history.

## Reference Docs

Reference docs capture **intent around** concrete technical artifacts — DB tables, API endpoints, models, events, jobs — without mirroring schema. Schema lives in the source of truth (DDL, OpenAPI, ORM); the codex never owns it. Reference docs explain what the schema cannot say: history, non-enforced constraints, gotchas, ownership, lifecycle.

**Location.** `<technical-domain>/ref/` — e.g. `technical/database/ref/`, `technical/api/ref/`, `technical/events/ref/`. The `ref/` subdirectory is the convention; do not invent siblings.

**ID convention.** `ref-<system>-<concept>` — pure naming, not a frontmatter field. Examples:

- `ref-orders_db-checkout` — covers `orders`, `line_items`, `shipments`
- `ref-billing_db-ledger` — covers `entries`, `accounts`, `postings`
- `ref-orders_db-line_items` — single-entity doc when one entity carries intent its cluster does not

**Granularity.** One doc per logical cluster, not per entity. Intent is usually a cluster property — splitting it across siblings duplicates or fragments the why. Go finer only when one entity carries intent that does not belong to its cluster (noisy gotcha, deprecation timeline, different owner). A boring CRUD entity with no surprising history needs no reference doc at all.

**Body content.** Intent-only: history, non-enforced constraints, gotchas, ownership, lifecycle, and a pointer to the source of truth. No schema dump — the reader who wants column types reads the migration. The reader who wants to know *why `order_id` has no FK constraint* reads this. Browse existing `ref-*` docs in the codex (`lore codex search ref-`) for shape examples.

**Discoverability rule (enforced).** Cluster docs MUST name every covered entity verbatim in the body — the `**Covers:**` line is the canonical place — so `lore codex search <table_name>` lands on the cluster doc. Without this, granularity flexibility breaks search.

**No new frontmatter.** Reference docs use the standard codex frontmatter — no `kind`, no `system`, no `source_of_truth` field. The source-of-truth pointer lives in the body.

## Decisions

`decisions/` contains Architecture Decision Records. Write an ADR when a significant architectural choice is made — one that future contributors should not unknowingly reverse. Each ADR records context, the decision, why it was made, and what alternatives were rejected. The alternatives section is particularly valuable: it tells an AI agent what not to suggest.

## Standards

`standards/` contains the project's coding conventions, design principles, and framework usage rules. Standards are ongoing, enforced guidelines — not one-time decisions. A decision in `decisions/` may produce a standard in `standards/`. Decisions explain *why*; standards explain *how to comply*.

## Voice

Every canonical codex document speaks with one voice: present tense about current state, written for a reader who arrives cold with no conversation behind them. The rules live in one file. Run `lore artifact show codex-voice` before writing or editing anything under `.lore/codex/` — it holds the rule table, the two tests that settle a borderline sentence, and the per-layer table naming which rules bind which layer (`decisions/` and `transient/` get different tense budgets; `sources/` is exempt).

`lore health --scope voice` checks the mechanical rules and reports each hit as a warning; it never affects the exit code (`decisions-020-codex-voice-is-enforced`). Four of the ten rules need judgment no pattern match supplies, so a clean run is not a pass — read those four yourself before you close a document.

## What NOT to Put in the Codex

- Git history, commit messages, or who changed what — use `git log`
- Debugging notes or fix recipes — put the fix in code, context in the commit message
- PR summaries or activity logs — these are ephemeral
- In-progress task state or mission notes — use the task manager
- Anything already captured in `AGENTS.md` or `CLAUDE.md`
- Duplicate facts — if a fact exists in one file, link to it; do not repeat it
- Changelog narration — what a document said before, or what a release altered; a stable doc states what is true now, and `CHANGELOG.md` plus `git log` hold the rest
- Promises of work not yet built — those belong in `transient/` or in a quest, never in a stable layer

## Cross-References

Cross-references between documents belong exclusively in the `related` frontmatter field. Do not add "Related Documentation" sections to document bodies. One mechanism, one place.

Use `lore codex map <id>` to list neighbours of any document. Default output is a list table — same columns as `lore codex list` — and traversal is bidirectional at depth 1 (outbound `related` plus inbound backlinks). Use `--depth N` for symmetric deeper walks, `--depth-out N` / `--depth-in N` for one-direction-only walks, and `--full` to print bodies instead of the list.

## Naming Conventions

- Relationship files are named with both entities in alphabetical order separated by double-dash: `attendee--event.md`, not `event--attendee.md`.
- Technical subdirectories are named after the actual software component: `backend/`, `frontend/`, `database/`. If a project has two backends, use `backend-api/` and `backend-worker/`. If there is no frontend, there is no `frontend/` directory.
- ADRs are numbered sequentially: `001-title.md`, `002-title.md`.

## Frontmatter

Every file has frontmatter with the fields below. The `summary` field is written for scanning — an AI agent reads summaries to decide whether a file is relevant before reading the body.

### Required Fields (all files)

| Field | Description |
|-------|-------------|
| `id` | Unique identifier. Must be globally unique across the codex. |
| `title` | Human-readable document title. |
| `summary` | 1-3 sentences written for scanning. Answers: would someone looking for X find what they need here? |

### Optional Fields

| Field | Description |
|-------|-------------|
| `related` | YAML array of related codex IDs. Followed outbound by `lore codex map` and surfaced inbound as backlinks. Omit or use `[]` if none. |
| `binds` | YAML array of repo-root-relative paths or globs naming the code files this doc governs. The codex↔code edge described below. Omit or use `[]` if none. |
| `rites` | YAML array of rite IDs (in `.lore/rites/main/`) that this codex entry governs. The codex→rite edge — links live on the codex side only; rites never link back. Omit or use `[]` if none. |

The `binds` field is an **optional** list of repo-root-relative paths or globs
naming the code files this codex entry governs. Each entry is either a literal
path or a glob (recursive `**` supported). Missing field and empty list
(`binds: []`) behave identically — both mean "this document governs no specific
code files." Absolute paths, paths containing `..`, and empty strings are
rejected by the schema and surfaced by `lore health --scope schemas`. The
`binds` graph is queried with `lore impacts <token>`: pass a codex id to list
the bound paths; pass a file path to list the codex entries whose `binds`
match it (exact-or-glob). See `conceptual-workflows-impacts`.

The `rites` field is an **optional** list of rite ids. A **rite** is procedural
memory — how to do or diagnose a recurring task (see `conceptual-entities-rite`).
It is the **codex→rite edge**: a codex
doc names the rites it governs; rites never link back (no `related`, no `binds`
on the rite side). The direction is fixed by ADR-014 (`decisions-014-link-direction`):
the stable/authoritative side (the codex) owns the link, because a change to a
codex doc can force a change to the rites built on it, so the codex entry owns
the pointer. Each entry is a plain rite id slug (no path patterns — unlike
`binds`). Missing field and empty list (`rites: []`) behave identically. `rites:`
is a **secondary discovery path, not retrieval** — a main rite with no codex
pointer is still found via `lore rite list`, so a missing inbound link is never a
failure to find a rite (this is why an orphan *main* rite is not a health error,
while a `rites:` id with no matching rite IS — see `conceptual-workflows-health`).
The field is queryable indirectly: `lore health --scope rites` (or `--scope
codex`) validates every `rites:` id resolves to an existing rite.

**Schema requirement.** `lore://schemas/codex-frontmatter`
(`src/lore/schemas/codex-frontmatter.yaml`) is `additionalProperties: false`, so
`rites:` MUST be added explicitly to the schema's `properties` — beside `binds`,
as an array of unique non-empty strings (no path-pattern rules; rite ids are
plain slugs) — or `lore health --scope schemas` rejects any doc carrying it. See
`tech-arch-schemas`.

No other frontmatter fields are permitted by default. `lore health` enforces this — any extra field fails validation.

**Project-local custom fields.** A project may add its own frontmatter keys (e.g. `owner`, `reviewed`) by declaring them once in an add-only overlay at `.lore/custom-schemas/codex-frontmatter.yaml` (or `codex-source-frontmatter.yaml` for source docs). The overlay extends the packaged schema: declared custom keys then pass `lore health` and `lore codex` create/edit, while undeclared keys (and typos) still fail — `additionalProperties` stays `false`. Overlays are add-only: they cannot redefine, relax, or drop a packaged field. They also apply to **canonical docs and sources only** — in-flight docs under `transient/` validate against the packaged schema alone, so a transient doc that carries a custom key is rejected as an unknown property and an overlay `required` field never fires on one (`decisions-019-overlay-scope-stops-at-transient`). Use the `new-custom-schema` skill to scaffold one; the resolver and merge rules live in `tech-arch-schemas`.