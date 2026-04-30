---
id: codex
title: Codex
summary: 'What this documentation system is, how it is structured, and how to use
  it. Read this before reading or writing any other file in this repository.

  '
related:
  - conceptual-entities-glossary
  - conceptual-workflows-glossary
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
| Decisions | `decisions/` | Why was this architectural choice made and what alternatives were rejected? |
| Standards | `standards/` | How do we write code and design this system? Conventions, principles, and rules. |
| Operations | `operations/` | How is this developed, deployed, and maintained? |

**Conceptual docs describe the system from the outside.** No file paths, no schema columns, no API endpoints. If a business analyst can read it and understand it without knowing the tech stack, it belongs in conceptual.

**Technical docs describe the system from the inside.** Database schemas, CLI command specs, source layout, infrastructure. Each component of the software gets its own subdirectory.

These two trees link to each other but never duplicate. If a fact exists in a schema file, the entity file links to it — it does not repeat it. One fact, one file.

## Workflows

Workflows describe processes. The subject determines the framing:

- **System workflow** — the system is the subject. What the system does when triggered. Steps through internal logic, validations, and state changes. No `persona` field.
- **User-facing workflow** — a user is the subject. What a person does to accomplish a goal. Set the `persona` frontmatter field to identify the role performing it.

A background job has a system workflow. A CLI command may have a user-facing workflow. A command that the user runs while the system validates and persists state may warrant both perspectives in the same document.

## Stable vs In-Flight

Documentation is either stable or in-flight.

**Stable** — `conceptual/`, `technical/`, `decisions/`, `standards/`, `operations/`. Describes the system as it exists today. The single source of truth. Never contains future intentions or work in progress.

**In-flight** — `specs/`, `user-stories/`, `transient/`. Describes work being planned or developed. These files are deleted when the feature ships.

**The deletion test:** when a feature ships, its spec and user stories can be deleted. If deleting them causes any information to be lost, the stable documentation was not properly updated. A complete documentation update is part of the definition of done.

## Decisions

`decisions/` contains Architecture Decision Records. Write an ADR when a significant architectural choice is made — one that future contributors should not unknowingly reverse. Each ADR records context, the decision, why it was made, and what alternatives were rejected. The alternatives section is particularly valuable: it tells an AI agent what not to suggest.

## The Development Pipeline

New features follow this sequence:

1. **Business spec** (`specs/`) — written in business language. What is broken or missing, what success looks like, proposed solutions. No implementation details.
2. **Architecture review** — the stable documentation is updated to reflect the new design. Entities, schemas, API endpoints, ADRs — all updated before any code is written.
3. **Full spec** (`specs/`) — technical design added to the business spec. Files to modify, schema changes, edge cases, error handling.
4. **User stories** (`user-stories/`) — written after the docs are updated. Each story references stable documentation as the source of truth and adds acceptance criteria and tech notes.
5. **Development** — agents implement against the user stories, consulting stable documentation for the source of truth.
6. **Cleanup** — specs and user stories are deleted. Stable docs already reflect the new reality.

## Naming Conventions

- Relationship files are named with both entities in alphabetical order separated by double-dash: `attendee--event.md`, not `event--attendee.md`.
- Technical subdirectories are named after the actual software component: `backend/`, `frontend/`, `database/`. If a project has two backends, use `backend-api/` and `backend-worker/`. If there is no frontend, there is no `frontend/` directory.
- ADRs are numbered sequentially: `001-title.md`, `002-title.md`.

## Frontmatter

Every file has YAML frontmatter with at minimum: `id`, `title`, `summary`, `related`, and `stability`.

The `summary` field is written for scanning — an AI agent reads summaries to decide whether a file is relevant before reading the body. Write summaries that answer: *would someone looking for X find what they need here?*

The `related` field is a list of codex IDs that this document links to. Cross-references belong exclusively here — do not add "Related Documentation" sections to document bodies.

`related` links are **directed**: declaring B in document A's `related` field means A
references B, but it does not mean B references A. There is no automatic bidirectional
linking. Cycles are possible (A → B → A) and are handled safely by `lore codex map`
via a visited set — each document appears at most once in any traversal output.

`lore codex map <id> --depth <n>` traverses this field automatically, performing
deterministic BFS from a root document up to the requested depth.
`lore codex chaos <id> --threshold <int>` is the non-deterministic sibling: a random
walk that terminates when the fraction of the reachable subgraph discovered exceeds
the threshold percentage.

The `stability` field is either `stable` (production documentation) or `experimental` (provisional, subject to change).
