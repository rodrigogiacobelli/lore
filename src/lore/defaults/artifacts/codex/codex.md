---
id: example-codex
title: Codex
summary: What the codex is and how it is organised — its directories, content
  classes, frontmatter, links between documents, the sources layer, reference
  documents and the glossary. A conceptual introduction; how an agent reads or
  writes it is set by the project's agent instructions and skills.
---

# Codex

The **codex** is the project's documentation, kept as a graph of typed markdown documents under `.lore/codex/`. It holds
what the project knows and decided: why choices were made, how the system is built, what it looks like from the outside.

This file explains the structure. It does not say how to read or write the codex; the agent instructions and skills of
the project do that, and they differ by how the project chose to work with Lore.

## A document

Every document is a markdown file with frontmatter and a body. The frontmatter carries `id`, `title`, `summary`, and
optionally `related`, `binds` and `rites`. Nothing else is accepted unless the project declares extra fields in an
add-only overlay at `.lore/custom-schemas/<kind>.yaml`. Overlays cover canonical documents and `sources/`; `transient/`
always follows the packaged schema.

- `id` is the stable name other documents and tools use.
- `summary` is what a reader sees before deciding to open the body. It states what the document answers.
- `related` lists documents that are about the same thing. The link is followed in both directions.
- `binds` lists the repo paths or globs (`**` is recursive) the document governs, so a change to a file leads back to the
  documents that govern it, and a document leads to the files it governs. Paths are repo-root-relative; absolute paths
  and `..` are invalid.
- `rites` lists the ids of the rites the document governs (see Rites).

## Directories

Directories scope a document's intent. The set below is what a fresh project is expected to use; others
(`constraints/`, `personas/`, `integrations/`, `security/`) are created on first use.

| Directory     | Purpose                                                                       |
|---------------|-------------------------------------------------------------------------------|
| `decisions/`  | ADRs — why a choice was made and what alternatives were rejected              |
| `standards/`  | how to comply: rules for code, design, conventions                            |
| `technical/`  | how the system is built, stored and served (incl. `technical/<domain>/ref/`)  |
| `conceptual/` | what the system looks like from the outside — entities, relationships, flows  |
| `vision/`     | product direction, long-arc goals                                             |
| `operations/` | development, deploy, run, runbooks                                            |
| `sources/`    | verbatim upstream snapshots (tickets, transcripts)                            |
| `transient/`  | in-flight work products, packaged schema only                                 |

`codex.md` and `glossary.yaml` sit at the root of `.lore/codex/`, not in a subdirectory.

## The Three Content Classes

Every document belongs to exactly one class, set by its top-level directory and by one question: **what happens when you
delete it?**

| Class     | Directory                                                                         | Deleting it                                                                   |
|-----------|-----------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| Stable    | `decisions/`, `standards/`, `technical/`, `conceptual/`, `vision/`, `operations/` | loses information; never safe                                                 |
| In-Flight | `transient/`                                                                      | safe once the feature ships and its facts are folded into stable documents    |
| Sources   | `sources/<system>/<id>.md`                                                        | safe at any time; every fact worth keeping already lives in a stable document |

## Voice

Canonical documents speak in one voice: present tense about the current state, written for a reader who arrives cold
with no conversation behind them. The rules, the tests that settle a borderline sentence and the per-layer table of which
rules bind which layer live in the `codex-voice` artifact. `decisions/` and `transient/` get different tense budgets,
`sources/` is exempt and `vision/` is skipped.

## The glossary

`glossary.yaml` is the project's controlled vocabulary: small, project-specific terms only. Entities and named workflows
do not belong in it; they live in their own documents. The `glossary-design` artifact holds the three-question gate that
keeps it lean.

## Rites

A **rite** is procedural memory — how to do or diagnose a recurring task — stored as YAML under `.lore/rites/main/`,
beside the codex. A document may name the rites it governs in `rites:`. This is the codex→rite edge: the link lives only
on the codex side and rites never link back. The stable document owns the pointer because a change to it can force a
change to the rites built on it (ADR-014, `decisions-014-link-direction`). Each entry is a plain rite id.

## Sources

Files at `sources/<system>/<id>.md` hold raw upstream material — tickets, meeting transcripts, chat threads, pasted
documents — captured verbatim as point-in-time snapshots. Sources are never canonical: every fact worth keeping is
propagated into a stable document before the source is deletable.

### Sources layout

`<system>` is a free-form slug (`jira`, `slack`, `meetings`); `<id>` is unique within it, for example
`sources/jira/KONE-23335.md`.

### Sources frontmatter rule

Four fields, all required: `id`, `title`, `summary`, `related`. `related` is non-empty and lists every canonical document
the source caused to change.

### Verbatim rule

Source bodies are preserved verbatim. Light reformatting is allowed only when the upstream format is structurally
unreadable, such as Atlassian ADF converted to markdown.

### One-way linking

Sources link outward. A canonical document never lists a source id in `related`.

### Refresh rule

Re-ingesting replaces the snapshot; no history file is kept. Earlier content lives in git.

## Reference documents (`ref-*`)

Reference documents capture the **intent around** concrete technical artifacts — tables, endpoints, models, events,
jobs — without mirroring their schema. The schema lives in its source of truth (DDL, OpenAPI, ORM); the codex never owns
it.

- **Location:** `<technical-domain>/ref/`, such as `technical/database/ref/` or `technical/api/ref/`.
- **Id:** `ref-<system>-<concept>`, such as `ref-orders_db-checkout` (covers `orders`, `line_items`, `shipments`) or
  `ref-orders_db-line_items` (a single entity whose intent its cluster does not carry).
- **Granularity:** one document per logical cluster, not per entity. Go finer only when one entity carries intent that
  does not belong to its cluster.
- **Discoverability:** a cluster document names every covered entity verbatim in the body, conventionally on a
  `**Covers:**` line, so a search for an entity name lands on the cluster document.

## What does not belong

- Git history, commit messages, or who changed what — that is `git log`.
- Debugging notes or fix recipes — the fix goes in code and the context in the commit message.
- PR summaries or activity logs — they are ephemeral.
- In-progress task state or mission notes — those belong to the task entities.
- Anything already captured in `AGENTS.md` or `CLAUDE.md`.
- Duplicate facts — a fact lives in one file; others link to it through `related`.
- Changelog narration — what a document said before or what a release altered. A stable document states what is true
  now; `CHANGELOG.md` and `git log` hold the rest.
- Promises of work not yet built — those belong in `transient/` or in a task entity, never in a stable layer.

## Naming

- ADRs are numbered in sequence: `001-title.md`, `002-title.md`.
- Relationship files name both entities in alphabetical order with a double dash: `user--task.md`, not `task--user.md`.
