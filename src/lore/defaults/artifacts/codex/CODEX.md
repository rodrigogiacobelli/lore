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
- **User-facing workflow** — a user is the subject. What a person does to accomplish a goal. Set the `persona` frontmatter field to identify the role performing it.

A background job has a system workflow. A settings command may have a user-facing workflow. Creating and assigning a record has both — the user runs commands (`persona` set) while the system validates input and persists state (no `persona`).

## Stable vs In-Flight

Documentation is either stable or in-flight.

**Stable** — `conceptual/`, `technical/`, `decisions/`, `standards/`, `glossary/`, `constraints/`, `personas/`, `integrations/`, `security/`, `operations/`. Describes the system as it exists today. Never contains future intentions or work in progress.

**In-flight** — `transient/`. Describes work being planned or developed. These files are deleted when the feature ships.

**The deletion test:** when a feature ships, its transient files can be deleted. If deleting them causes any information to be lost, the stable documentation was not properly updated. A complete documentation update is part of the definition of done.

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
| `id` | Unique identifier. In defaults, prefixed with `example-` as a convention signal. |
| `title` | Human-readable document title |
| `type` | One of the valid types listed below |
| `summary` | 1-3 sentences written for scanning. Answers: would someone looking for X find what they need here? |
| `related` | List of related codex IDs. Use `[]` if none. Traversed by `lore codex map`. |
| `stability` | `stable` or `experimental` |

### Optional Fields (by type)

| Field | Applies to | Description |
|-------|-----------|-------------|
| `persona` | workflows | User role if this is a user-facing workflow (e.g. `team lead`, `admin`) |
| `entities_involved` | workflows | List of entity IDs this workflow involves |

### Valid Types

| Type | Used for |
|------|---------|
| `meta` | The CODEX.md index file itself |
| `entity` | A domain entity (thing with identity and behaviour) |
| `relationship` | The connection between two entities |
| `workflow` | A system process or user-facing workflow |
| `technical` | Technical implementation documentation |
| `decision` | Architecture Decision Record |
| `standards` | Coding conventions, design principles, framework rules |
| `glossary` | Vocabulary definitions |
| `constraints` | Hard limits and non-negotiable rules |
| `persona` | A user role and their goals |
| `integration` | An external system the project touches |
| `security` | Security and trust model |
| `operations` | Deployment, development setup, and operational runbooks |
| `context-map` | Scout output: a map of relevant codex documents for a feature |
| `transient-marker` | Marks a directory as in-flight/transient |
