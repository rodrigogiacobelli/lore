---
id: conceptual-relationships-artifact--doctrine
title: "Artifact to Doctrine"
related:
  - conceptual-entities-artifact
  - conceptual-entities-doctrine
  - tech-doctrine-internals
stability: stable
summary: >
  Artifact IDs may appear in Doctrine step notes as free-text references.
  There is no FK and no validation. Orchestrators and workers read the step notes
  and retrieve the Artifact via `lore artifact show <id>` when needed.
---

# Artifact to Doctrine

An Artifact is a reusable template file. A Doctrine step's `notes` field may reference an Artifact by its stable ID to guide the orchestrator or the worker agent executing the resulting Mission. This reference is advisory: it is human- and agent-readable plain text, not a machine-enforced link. Lore does not parse step notes, validate Artifact IDs mentioned in them, or retrieve Artifacts automatically.

## Named Roles

### Referenced Artifact (passive, advisory)

The Artifact whose ID appears in a Doctrine step's `notes` field. The Artifact plays no active role at doctrine load, validation, or display time. It is retrieved explicitly by whoever reads the step notes.

### Referring Doctrine Step (author of guidance)

The step that names an Artifact ID in its `notes`. Step notes are free-form text; an Artifact ID is just one kind of content that may appear there. Multiple Artifact IDs can appear in one set of notes.

## Data on the Connection

There is no database column, FK, or join table.

| Location | Field | Mutable |
|----------|-------|---------|
| Doctrine YAML step | `notes` (free-text) | Yes (edit the Doctrine file) |

The Artifact ID in the notes is a plain string embedded in prose. Lore treats it as opaque text.

## Business Rules

- **No validation:** Lore does not parse `notes` fields to find or validate Artifact IDs. A step note referencing a deleted or non-existent Artifact ID causes no error at doctrine load time.
- **Orchestrator retrieval:** When an orchestrator reads a Doctrine step to create a Mission, it may extract Artifact IDs from the notes and call `lore artifact show <id>` to retrieve the template content. This is a convention, not an enforced pattern.
- **Worker retrieval:** The Mission description (written by the orchestrator from `step.notes`) may include Artifact ID references. The worker agent executing the Mission follows the same pattern: reads the description, extracts the Artifact ID, and calls `lore artifact show <id>`.
- **Advisory relationship:** The purpose of referencing an Artifact in step notes is to point the reader at a template or document without embedding its full content in the Doctrine. The relationship is guidance, not enforcement.
- **Artifact changes are not tracked:** If an Artifact is updated or deleted after a Doctrine is written, the Doctrine is unaffected. The stale reference persists in the step notes until manually updated.

## Concrete Examples

### Artifact ID in step notes

```yaml
steps:
  - id: tech-spec
    type: knight
    knight: architect
    notes: |
      Read the PRD first. Retrieve the template with:
        lore artifact show fi-tech-spec-draft
      Output to .lore/codex/transient/<slug>-tech-spec-draft.md
```

→ Lore stores this as-is. No lookup of `fi-tech-spec-draft` occurs.

### Orchestrator extracting and retrieving the Artifact

```
# Orchestrator reads step notes and creates Mission:
$ lore mission new --quest q-9001 --knight architect \
    "Tech Spec: Build auth module — use lore artifact show fi-tech-spec-draft"
Mission q-9001/m-001 created.
```

### Worker retrieving the Artifact during execution

```
# Worker (architect knight) reads mission description and acts:
$ lore artifact show fi-tech-spec-draft
---
id: fi-tech-spec-draft
...
# Template content follows
```

→ The worker uses the template to produce the required output document.
