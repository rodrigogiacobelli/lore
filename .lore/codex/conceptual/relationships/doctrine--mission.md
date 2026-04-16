---
id: conceptual-relationships-doctrine--mission
title: Doctrine to Mission
related:
- conceptual-entities-doctrine
- conceptual-entities-mission
- tech-doctrine-internals
summary: 'Each Doctrine step maps to one Mission that an orchestrator creates. There
  is no FK. The mapping is a process convention: step fields provide the orchestrator
  with everything needed to write a well-formed Mission.'
---

# Doctrine to Mission

A Doctrine step is the blueprint for a single Mission. When an orchestrator executes a Doctrine, it reads each step and creates a corresponding Mission. There is no foreign key stored in Lore; the relationship exists only during the orchestration act.

## Named Roles

### Doctrine Step (blueprint, passive)

One entry in the Doctrine's ordered step list. It carries the fields the orchestrator needs to create a Mission: `id`, `type`, `knight`, `needs`, and `notes`. A step has no lifecycle of its own; it is part of the Doctrine document.

### Created Mission (independent after creation)

The Mission that the orchestrator creates by reading a Doctrine step. Once created, the Mission is a standalone record in Lore with no runtime link to the step that produced it.

## Data on the Connection

There is no database column or join table recording this relationship.

| Storage | Detail |
|---------|--------|
| No FK on `missions` | Lore does not record which Doctrine step produced a Mission |
| Step fields | Used by orchestrator at creation time only; not copied verbatim |

### Step field to Mission field mapping

| Step field | Mission counterpart | Notes |
|------------|---------------------|-------|
| `step.id` | Mission title context | Step ID informs the mission title; not copied as-is |
| `step.type` | `mission.mission_type` | Copied directly (e.g. `knight`, `constable`, `human`) |
| `step.knight` | `mission.knight` | Knight filename stem; set at creation |
| `step.needs` | Mission dependencies | Step IDs are resolved to Mission IDs after creation |
| `step.notes` | Mission description | Orchestrator uses notes to write the mission description |

## Business Rules

- **No FK, no validation:** Lore does not verify a Mission was created from a Doctrine step. There is no linkage record.
- **Step notes drive description:** The `notes` field of a step is the orchestrator's primary input for writing a meaningful Mission description. Step notes may reference Artifact IDs; see the artifact--doctrine relationship doc.
- **Dependency resolution:** Step `needs` lists sibling step IDs. After the orchestrator creates all Missions for a Quest, it must update each Mission's dependencies to reference the real Mission IDs (not the step IDs).
- **Doctrine changes do not affect live Missions:** Editing a Doctrine step has no effect on Missions already created from it.
- **One step, one Mission:** The convention is one Mission per step. An orchestrator may deviate, but that is outside Lore's model.

## Concrete Examples

### Orchestrator reading a step and creating a Mission

```yaml
# Doctrine step
- id: tech-spec
  type: knight
  knight: architect
  needs: []
  notes: |
    Read the PRD (lore artifact show fi-prd-template) and produce
    a Tech Spec Draft. See lore artifact show fi-tech-spec-draft.
```

```
$ lore mission new \
    --quest q-9001 \
    --type knight \
    --knight architect \
    "Tech Spec: Build auth module"
Mission q-9001/m-001 created.
```

→ The `notes` field guided the description; no FK is written.

### Dependency resolution after batch creation

```
# Step 'implement' needs step 'tech-spec'
# After creating all missions:
$ lore mission edit q-9001/m-003 --needs q-9001/m-001
```

→ The orchestrator maps step IDs to real Mission IDs manually.
