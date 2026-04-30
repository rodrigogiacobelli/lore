---
id: glossary-design
title: Glossary Design Checklist
summary: >
  Gate every glossary entry through this checklist before adding it to
  `.lore/codex/glossary.yaml`. Most candidate terms do NOT belong in the
  glossary — they belong in an entity doc, a workflow doc, or nowhere
  (well-known industry concepts). Run this whenever you, or any agent
  acting on your behalf, are about to add or expand glossary content.
---

# Glossary Design Checklist

The Glossary is for **small, project-specific terms** that are too tiny to deserve their own Codex document but important enough that a fresh agent reading another document needs the definition inline. It is NOT a dump of every named thing in the system.

This file is a checklist. Run it before every glossary edit.

## The Three-Question Gate

A candidate term `<X>` belongs in the glossary only when ALL three answers are YES:

1. **Is it project-specific?** Would an outsider reading the codebase guess the wrong meaning if no glossary entry existed? Generic IT vocabulary (ADR, soft-delete, E2E, mock, fixture, retry-with-backoff, idempotent, RBAC, JWT, …) does NOT qualify — assume your reader knows IT. Only terms that this project gives a project-specific meaning, or invents outright, pass this gate.

2. **Is it NOT an entity?** Entities are the big nouns the system is built around (Quest, Mission, Knight, Doctrine, Codex, Artifact, Watcher, Glossary itself). Each entity already has a `conceptual-entities-<name>` document. **Entities never go in the glossary.** If you find yourself wanting to summarise an entity in the glossary, you are duplicating the entity doc — link to it instead.

3. **Is it NOT a named workflow, command, or feature?** Anything with a `conceptual-workflows-<name>` doc, a CLI command, a config key, or a feature surface (auto-surface, ready queue, board, oracle, health, codex show, …) already has a definition surface. Glossary entries that describe these are duplication. Link to the workflow doc instead.

If any answer is NO, the term does NOT go in the glossary. The "Where to put it instead" table below tells you where it does go.

## Worked Examples

### Goes in the glossary

| Keyword | Why it qualifies |
|---|---|
| **Constable** | Project-invented label for a Mission type the orchestrator handles inline. Not an entity (no `conceptual-entities-constable`), not a generic IT term, not a workflow. The canonical glossary example. |

### Does NOT go in the glossary

| Candidate | Why it fails | Goes here instead |
|---|---|---|
| Quest, Mission, Knight, Doctrine, Codex, Artifact, Watcher, Glossary | Entities — fail Q2 | Their `conceptual-entities-<name>` doc already exists. Link to it. |
| Camelot, Lore, Realm, Citadel | System-level entities — fail Q2 | Vision docs (`vision-camelot-system`). Link to them. |
| Health, Oracle, Board, Auto-surface, Ready queue, Codex show | Named workflows or feature surfaces — fail Q3 | Their `conceptual-workflows-<name>` doc. Link to it. |
| ADR | Generic IT term — fails Q1 | Nowhere. Outside readers know what an ADR is. The codex `decisions/` folder is named after the format. |
| Soft-delete | Generic IT term — fails Q1 | If the project has *non-standard* soft-delete semantics, that goes in `decisions-003-soft-delete-semantics`, NOT the glossary. |
| E2E, Unit test, mock, fixture | Generic testing vocabulary — fails Q1 | Nowhere. Cite test-strategy or standards docs in your tech spec instead. |
| Weapon | Doesn't exist yet (future scope) — fails on existence | Nowhere. Glossary describes today's vocabulary, not roadmap. |

## Where to Put It Instead

| If the term is… | Put it in… |
|---|---|
| A new entity (large noun, has lifecycle, multiple surfaces) | A new `conceptual-entities-<name>.md` document. |
| A new workflow / command / user-facing flow | A new `conceptual-workflows-<name>.md` document. |
| A named architectural decision | A new ADR under `decisions/<NNN>-<slug>.md`. |
| A coding convention or standard | A new `standards-<name>.md` document. |
| A generic IT term, even one used heavily | Nowhere. Outsiders already know it. |
| A future-scope idea | Nowhere yet. Add it when it ships. |

## YAML Stanza Template

When the gate passes for term `<X>`, append this to `.lore/codex/glossary.yaml`:

```yaml
- keyword: <X>
  definition: >-
    One or two sentences. State the project-specific meaning. Reference
    related codex IDs by ID (not file path) where relevant.
  aliases:
    - <other surface form 1>
    - <other surface form 2>
  do_not_use:
    - <deprecated form 1>
    - <deprecated form 2>
```

Required fields: `keyword`, `definition`. `aliases` and `do_not_use` are optional — omit when empty.

After editing, run `lore health --scope glossary` to validate the file and surface any deprecated-term hits across the existing codex.

## When in Doubt

Default to NOT adding the entry. A glossary that grows unchecked stops being useful — agents skim past it, and the auto-surface noise dilutes the signal. The right glossary is short.

If the term feels borderline, write the entity / workflow / ADR / standards doc instead. A linkable Codex document is always more valuable than a one-line glossary stub.
