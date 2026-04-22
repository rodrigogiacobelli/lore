---
id: example-codex
title: Codex
summary: What this documentation system is, how it is structured, and how to use it.
  Read this before reading or writing any other file in this repository.
---

# Codex

This is a documentation system designed to be the single source of truth for a software project. It is built for AI agents first and humans second. Every structural decision exists to help an agent find exactly what it needs without reading files that are not relevant.

Start with `lore codex list`. It is the only index. Everything else is reachable from there.

## The Layers

Documentation is divided into layers. Each layer has one job.

| Layer | Directory | Question it answers |
|-------|-----------|-------------------|
| Conceptual — Entities | `conceptual/entities/` | What is this thing and how does it behave? |
| Conceptual — Relationships | `conceptual/relationships/` | How do two entities connect and what rules govern that connection? |
| Conceptual — Workflows | `conceptual/workflows/` | What does the system do internally, or how does a user accomplish a goal? |
| Technical | `technical/` | How is this built, stored, and served? |
| Decisions | `decisions/` | Why was this architectural choice made and what alternatives were rejected? |
| Standards | `standards/` | How do we write code and design this system? Conventions, principles, and rules. |
| Glossary | `glossary/` | What do our terms mean? Canonical vocabulary for agents and humans. |
| Constraints | `constraints/` | What are the hard limits we must never violate? |
| Personas | `personas/` | Who uses this system and what do they need? |
| Integrations | `integrations/` | What external systems do we touch and how? |
| Security | `security/` | What is our security and trust model? |
| Operations | `operations/` | How is this developed, deployed, and maintained? |
| Transient | `transient/` | In-flight working documents for the current feature cycle. Deleted when the feature ships. |

**Conceptual docs describe the system from the outside.** No file paths, no schema columns, no API endpoints. If a business analyst can read it and understand it without knowing the tech stack, it belongs in conceptual.

**Technical docs describe the system from the inside.** Database schemas, CLI command specs, frontend structure, infrastructure. Each component of the software gets its own subdirectory.

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
| Stable   | `conceptual/`, `technical/`, `decisions/`, `standards/`, `glossary/`, `constraints/`, `personas/`, `integrations/`, `security/`, `operations/` | Deleting any file LOSES information. Never safe. |
| In-Flight | `transient/` | Safe to delete **after** the in-flight feature ships and its facts have been folded into stable docs. |
| Sources  | `sources/<system>/<id>.md` | Safe to delete **at any time**. Every fact worth keeping already lives in a stable doc. |

**Stable** describes the system as it exists today. Never future intentions, never work in progress.

**In-flight** (`transient/`) holds work being planned or developed — PRDs, tech specs, maps, reports. Deleted when the feature ships.

**Sources** (`sources/<system>/<id>.md`) hold raw upstream material — Jira tickets, meeting transcripts, chat threads, pasted documents — captured verbatim as point-in-time snapshots. They are never canonical. Every fact that matters must be propagated into a stable doc before the source becomes deletable; after that, the source is disposable.

### Sources layout

Files live at `sources/<system>/<id>.md` where `<system>` is a free-form slug (e.g. `jira`, `slack`, `meetings`) and `<id>` is unique within that system.

### Sources frontmatter rule

Source files carry exactly four frontmatter fields: `id`, `title`, `summary`, and `related`. All four are required. `related` is a non-empty array of canonical codex IDs — the canonical docs this source caused to change. `lore health` rejects any source file with missing fields, empty `related`, or any extra field.

### Verbatim rule

Source bodies are preserved verbatim from upstream. Light reformatting is permitted only when the upstream format is structurally unreadable (e.g. Atlassian ADF → markdown). Semantic content must not be altered.

### One-way linking

Sources MUST link outward. Every source's `related` list names every canonical doc it caused to change — `lore codex map <source-id> --depth 1` returns exactly those docs. Canonical docs MUST NOT link back: no canonical doc may include a source ID in its `related` list. `lore health` enforces both directions — empty/missing `related` on a source is a schema error; a source ID appearing in any canonical doc's `related` is a `canonical_links_to_source` error.

### Refresh rule

Re-ingestion of an existing source (via `/refresh-source`) **overwrites** the snapshot file. There is no history file. Previous content is retained only in git history.

## Decisions

`decisions/` contains Architecture Decision Records. Write an ADR when a significant architectural choice is made — one that future contributors should not unknowingly reverse. Each ADR records context, the decision, why it was made, and what alternatives were rejected. The alternatives section is particularly valuable: it tells an AI agent what not to suggest.

## Standards

`standards/` contains the project's coding conventions, design principles, and framework usage rules. Standards are ongoing, enforced guidelines — not one-time decisions. A decision in `decisions/` may produce a standard in `standards/`. Decisions explain *why*; standards explain *how to comply*.

## What NOT to Put in the Codex

- Git history, commit messages, or who changed what — use `git log`
- Debugging notes or fix recipes — put the fix in code, context in the commit message
- PR summaries or activity logs — these are ephemeral
- In-progress task state or mission notes — use the task manager
- Anything already captured in `AGENTS.md` or `CLAUDE.md`
- Duplicate facts — if a fact exists in one file, link to it; do not repeat it

## Cross-References

Cross-references between documents belong exclusively in the `related` frontmatter field. Do not add "Related Documentation" sections to document bodies. One mechanism, one place.

Use `lore codex map <id> --depth 1` to traverse the graph of related documents starting from any document.

## The Development Pipeline

New features follow this sequence:

1. **Scouts map the codex** — two Scout agents run in parallel, producing a business context map and a technical context map in `transient/`. These maps are the mandatory input for all planning agents.
2. **PRD** (`transient/`) — written in business language. What is broken or missing, what success looks like, user workflows, functional and non-functional requirements.
3. **Architecture review** — the stable documentation is updated to reflect the new design. Entities, schemas, CLI command specs, ADRs — all updated before any code is written.
4. **Tech Spec** (`transient/`) — technical design. Files to modify, schema changes, edge cases, error handling. Every user workflow in the PRD maps to an E2E test scenario.
5. **User stories** (`transient/`) — written after the docs are updated. Each story references stable documentation as the source of truth and adds acceptance criteria and test stubs.
6. **Development** — agents implement against user stories, consulting stable documentation for context.
7. **Cleanup** — transient files are deleted. Stable docs already reflect the new reality.

## Naming Conventions

- Relationship files: both entities in alphabetical order separated by double-dash: `user--task.md`, not `task--user.md`.
- Technical subdirectories: named after the actual software component: `backend/`, `frontend/`, `database/`. If a project has two backends, use `backend-api/` and `backend-worker/`. If there is no frontend, there is no `frontend/` directory.
- ADRs: numbered sequentially: `001-title.md`, `002-title.md`.

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
| `related` | YAML array of related codex IDs. Traversed by `lore codex map`. Omit or use `[]` if none. |

No other frontmatter fields are permitted. `lore health` enforces this — any extra field fails validation.
