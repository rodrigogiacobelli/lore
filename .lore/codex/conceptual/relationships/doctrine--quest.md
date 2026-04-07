---
id: conceptual-relationships-doctrine--quest
title: "Doctrine to Quest"
related:
  - conceptual-entities-doctrine
  - conceptual-entities-quest
  - tech-doctrine-internals
stability: stable
summary: >
  A Doctrine is a reusable workflow template; a Quest is a single execution of
  a body of work. There is no FK between them. An orchestrator reads a Doctrine
  and manually creates a Quest; the link is process-level, not database-level.
---

# Doctrine to Quest

A Doctrine describes the shape of a repeatable body of work. A Quest represents one live instance of that work. The relationship between them is an orchestration-time process: a human or automated orchestrator reads a Doctrine and manually creates a Quest and its Missions according to the Doctrine's steps. No foreign key is stored; Lore does not record which Doctrine a Quest was derived from.

## Named Roles

### Source Doctrine (passive, reusable)

The Doctrine that served as the template for creating a Quest. The Doctrine is read by the orchestrator; it plays no active role in Quest execution. A single Doctrine can be used to create many Quests across time, in series or in parallel.

### Derived Quest (independent after creation)

The Quest created by the orchestrator following a Doctrine. Once created, the Quest is fully independent of the Doctrine. Changes to the Doctrine after Quest creation have no effect on existing Quests or their Missions.

## Data on the Connection

There is no database column or join table recording this relationship.

| Storage | Detail |
|---------|--------|
| No FK on `quests` | Lore does not store which Doctrine was used |
| No FK on `missions` | Same — see doctrine--mission relationship |
| Process record only | The link exists only in the orchestrator's execution log or conversation history |

## Business Rules

- **Doctrine is passive:** A Doctrine has no execution engine. It cannot trigger, create, or modify Quests on its own. See the Doctrine entity doc for the full passive model.
- **One-to-many reuse:** A Doctrine can be used to create any number of Quests. There is no limit and no tracking by Lore.
- **No enforcement:** Lore does not verify that a Quest was built from a Doctrine, nor that it follows the Doctrine's step ordering. The Doctrine is advisory guidance for the orchestrator.
- **Doctrine changes do not affect live Quests:** Editing or deleting a Doctrine has no effect on Quests that were already created from it. Those Quests are standalone records.
- **Orchestrator responsibility:** The orchestrator (Realm, human, or CI pipeline) is responsible for reading the Doctrine, creating the Quest, and creating Missions that match the Doctrine's steps. Lore plays no coordinating role.

## Concrete Examples

### Creating a Quest from a Doctrine

```
$ lore doctrine show feature-build-workflow
Steps:
  1. tech-spec  (knight: architect)
  2. ba-stories (knight: ba)
  3. implement  (knight: tech-lead)

# Orchestrator manually creates the Quest and Missions:
$ lore quest new "Build auth module"
Quest q-9001 created.

$ lore mission new --quest q-9001 --knight architect "Tech Spec"
$ lore mission new --quest q-9001 --knight ba "BA Stories"
$ lore mission new --quest q-9001 --knight tech-lead "Implementation"
```

→ No FK is written. The Quest and its Missions exist independently of the Doctrine.

### Doctrine reused for a second Quest

```
$ lore quest new "Build notifications module"
Quest q-9002 created.

# Same doctrine, new Quest — Lore has no record of the relationship
$ lore mission new --quest q-9002 --knight architect "Tech Spec"
...
```
