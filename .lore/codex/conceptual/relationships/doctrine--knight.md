---
id: conceptual-relationships-doctrine--knight
title: "Doctrine to Knight"
related:
  - conceptual-entities-doctrine
  - conceptual-entities-knight
  - tech-doctrine-internals
stability: stable
summary: >
  A Doctrine step may name a Knight by filename stem. There is no FK. The
  reference is resolved at orchestration time when the orchestrator assigns the
  Knight to the created Mission. No validation is performed at doctrine load time.
---

# Doctrine to Knight

A Doctrine step's `knight` field is an optional reference to a Knight persona by its filename stem. This reference is not enforced by Lore: a Doctrine can name a Knight that does not exist and still be stored and shown without error. The reference is resolved into a concrete assignment only when the orchestrator creates the Mission from the step.

## Named Roles

### Referenced Knight (optional, passive)

The Knight whose filename stem appears in the `knight` field of a Doctrine step. The Knight plays no active role at doctrine load or validation time. The reference is resolved at orchestration time.

### Referring Doctrine Step (mutable)

The step within a Doctrine that names the Knight. The `knight` field is optional; a step with no `knight` field is valid. Changing the `knight` field in the Doctrine has no effect on Missions already created from that step.

## Data on the Connection

The reference is stored as a text value inside the Doctrine's YAML.

| Location | Field | Mutable |
|----------|-------|---------|
| Doctrine YAML step | `step.knight` | Yes (edit the Doctrine file) |

There is no FK, no join table, and no database column on the `doctrines` table for this relationship.

## Business Rules

- **No validation at doctrine time:** Lore does not check whether the named Knight exists when storing or displaying a Doctrine. A Doctrine referencing `wizard` is valid even if `.lore/knights/wizard.md` does not exist.
- **One Knight per step:** Each step can name at most one Knight. The field is a single string, not a list.
- **Resolved at orchestration time:** When the orchestrator creates a Mission from a step, it copies `step.knight` into `mission.knight`. From that point on, the knight--mission relationship governs resolution.
- **Doctrine changes do not backfill missions:** Updating `step.knight` in a Doctrine does not update the `knight` field on Missions already created from that step.
- **Optional field:** A step with no `knight` field produces a Mission with no Knight assigned. The Mission is still valid.

## Concrete Examples

### Doctrine step with a knight reference

```yaml
steps:
  - id: tech-spec
    type: knight
    knight: architect
    needs: []
    notes: "Produce the Tech Spec Draft."
```

→ Lore stores and shows this without checking whether `architect.md` exists.

### Knight reference resolved at Mission creation

```
# Orchestrator creates mission from step:
$ lore mission new --quest q-9001 --knight architect "Tech Spec"
Mission q-9001/m-001 created. Knight: architect
```

→ `architect` is now stored on the Mission. Resolution switches to the knight--mission model.

### Non-existent Knight in doctrine — no error

```
$ lore doctrine show my-doctrine
Steps:
  1. tech-spec (knight: wizard)   # wizard.md does not exist — no warning shown here
```

→ The warning only appears when `lore show <mission-id>` tries to resolve `wizard.md` at show-time.
