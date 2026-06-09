---
id: decisions-015-rites-writable-file-entity
title: "ADR-015: Rites are a writable file entity with full CRUD, unlike the read-only codex"
summary: >
  ADR recording that Rite — Lore's procedural-memory entity — ships with a full
  CLI write path (new/edit/delete) over its own .lore/rites/ store, diverging
  from the codex's deliberate read-only-via-CLI posture and instead adopting the
  watcher/doctrine/knight/artifact file-entity write model.
binds:
  - src/lore/rite.py
  - src/lore/cli.py
related:
  - conceptual-entities-rite
  - conceptual-workflows-rite-crud
  - decisions-006-id-references
  - decisions-011-api-parity-with-cli
  - decisions-014-link-direction
  - tech-cli-entity-crud-matrix
---

# ADR-015: Rites are a writable file entity with full CRUD, unlike the read-only codex

## Context

Rite is Lore's procedural-memory entity — the how-to counterpart of the
semantic/factual codex (see conceptual-entities-rite). It is stored as files in
its own `.lore/rites/` directory, a sibling of `.lore/codex/`. When adding the
`lore rite` command surface a posture had to be chosen: does Lore expose a CLI
write path (`new`/`edit`/`delete`), or — like the codex — is authoring done on
disk only?

The codex is deliberately read-only via the CLI (tech-cli-entity-crud-matrix
"Gaps"): `lore codex` offers list/show/search/map/chaos but no create/update/
delete. Codex authoring happens on disk, by humans and tech-writer agents,
through the doctrine pipeline. Rites are a new entity and inherit no posture by
default, so the choice is genuinely open.

Key forces:

- **Rites are rewritten often, by any agent.** The design doc frames rites as
  procedural knowledge that gets distilled and redistilled. A CLI write path is
  the natural authoring surface for high-churn content.
- **Other file entities already have full CRUD.** Watchers, knights, doctrines,
  and artifacts are file-based and all expose `new`/`edit`/`delete` (or close to
  it). A writable file entity is the established Lore pattern; the codex is the
  outlier, not the rule.
- **The codex's read-only stance is intentional and specific to it.** The codex
  is the human/agent record layer authored through a review pipeline; making it
  CLI-writable would bypass that. That rationale does not transfer to rites.

## Decision

Rites are a **writable** file entity. The `lore rite` surface ships with a full
write path — `lore rite new`, `lore rite edit`, `lore rite delete` — alongside
the read commands (`list`, `show`, `search`). This diverges from the codex's
read-only-via-CLI posture and instead follows the
watcher/doctrine/knight/artifact file-entity write model: validate-then-write,
subtree-wide duplicate detection, and soft-delete by `.yaml.deleted` rename.

> Codex stays disk-only for writes. Rites do not.

## Rationale

- **Matches the dominant file-entity pattern.** Watcher/knight/doctrine/artifact
  are all CLI-writable file entities; rites join them. The codex is the
  documented exception, and its exception does not generalise.
- **Authoring churn wants a first-class write path.** Rites are expected to be
  edited and replaced frequently; a CLI/API write path keeps that in-tool and
  ADR-011-parity-safe instead of pushing agents to hand-edit YAML on disk.
- **No review-pipeline coupling.** Unlike the codex, rites are not gated by the
  feature-implementation review pipeline, so there is no reason to force
  on-disk-only authoring to protect a process.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Read-only rites (mirror the codex exactly)** | Codex read-only-ness protects its review-pipeline authoring; rites have no such pipeline. It would also force high-churn procedural content to be hand-edited on disk, the opposite of what the design wants. |
| **Read + create only (no edit/delete)** | Leaves rite maintenance half-done — agents could add but not fix or retire a rite via the tool, breaking parity with every other writable file entity and ADR-011's "any gap is a bug" rule. |
| **Store rites inside the codex as a new doc type** | Rejected at the design level (design doc §Settled): rites are a distinct entity, not a codex layer; the codex is cemented as semantic/factual. |

## Consequences

**Easier:**
- Any agent can author, fix, and retire rites entirely through `lore rite` /
  `lore.api`, with the same validate-then-write safety the other file entities
  have.
- Rite tooling reuses the watcher/artifact write machinery (name validation,
  duplicate detection, soft-delete), so there is little new surface.

**Harder:**
- Rites now carry the full write-path test and maintenance burden the codex
  avoids (create/edit/delete error tables, soft-delete semantics, idempotency).
- The CLI surface diverges between two superficially similar "documentation-ish"
  entities (codex read-only, rite read-write); this ADR exists so that
  divergence is intentional and traceable.

## Constraints Imposed

1. **`lore rite` ships `new`, `edit`, and `delete`** (plus `list`/`show`/`search`).
   Each write command is a thin CLI wrapper over a self-contained `lore.api`
   function (ADR-011): `create_rite`, `update_rite`, `delete_rite`.
2. **Soft-delete by `.yaml.deleted` rename** (ADR-003 file-entity rule); deleted
   rites are invisible to scan/list/show/search/health.
3. **The codex remains read-only via CLI.** This ADR changes nothing about the
   codex; it records why rites diverge.
4. **Writes go through validation before disk** — name rule
   (`validate_rite_id`) and JSON-Schema shape check (`main-rite`/`shared-step`),
   same validate-then-write contract as watcher/artifact create.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-06-02 | accepted | Initial decision — recorded during Rites codex-apply; flagged by the ADR & Standards Audit as an unrecorded entity-posture choice |
