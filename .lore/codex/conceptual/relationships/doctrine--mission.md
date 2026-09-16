---
id: conceptual-relationships-doctrine--mission
title: Doctrine to Mission
related:
- conceptual-entities-doctrine
- conceptual-entities-mission
- conceptual-workflows-show
- ref-lore_doctrine-module
- decisions-033-unresolvable-reference-is-silent-on-read
summary: 'Each doctrine mission file maps to one Lore Mission that an orchestrator
  creates. The Mission stores the reference <doctrine-id>/<mission-id> verbatim in
  missions.doctrine_mission and Lore resolves it at read time; there is no FK and no
  write-time validation.'
---

# Doctrine to Mission

A doctrine mission file is the blueprint for a single Lore Mission. When an orchestrator plans a quest from a doctrine, it reads the design document and creates one Mission per row of its table. The Mission records which doctrine mission it runs, as the reference `<doctrine-id>/<mission-id>` in `missions.doctrine_mission`.

The reference is a string, not a foreign key. Lore stores it verbatim, never interprets it at write time, and resolves it only when a read asks for it.

## Named Roles

### Doctrine mission file (blueprint, passive)

One `missions/<mission-id>.md` file in a doctrine directory. Its body is the worker's whole brief: the role it adopts, how it works, its hard rules, its inputs, its steps, its done criteria, and what it hands on. Its id is its filename stem. It has no lifecycle of its own; it is part of the doctrine directory.

### Created Mission (independent after creation)

The Lore Mission an orchestrator creates. Its description carries what is specific to this run — which feature, which file, which acceptance criteria — while the doctrine mission carries what is reusable. `lore show <mission-id>` hands a worker both in one call.

## Data on the Connection

`missions.doctrine_mission` is a `TEXT` column holding the reference `<doctrine-id>/<mission-id>`, or `NULL`.

| Storage | Detail |
|---------|--------|
| `missions.doctrine_mission` | The reference, stored verbatim. No FK, no `CHECK`, no write-time resolution. |
| Design table | Read by the orchestrator at creation time only; not copied into any column. |

### Design row to Mission field mapping

| Design table column | Mission counterpart | Notes |
|---------------------|---------------------|-------|
| Mission id | `mission.doctrine_mission` | Stored as `<doctrine-id>/<mission-id>` via `-D` |
| Mission id | Mission title context | Informs the title; not copied as-is |
| Type | `mission.mission_type` | Copied directly (`agent`, `constable`, `human`) |
| Phase | `mission.priority` | The phase number becomes the priority |
| Depends On | Mission dependencies | Mission ids are resolved to Lore Mission IDs after creation |
| Input / Output | Mission description | The orchestrator writes the run-specific description |

## Resolution at Read Time

`get_mission_detail` resolves the stored reference through `doctrine._resolve_doctrine_mission` and returns `doctrine_mission_contents` — the mission file's body, frontmatter stripped. `lore show` prints it under `--- Mission Instructions ---`. Nothing else in the read path looks the reference up.

Resolution is permissive about the one separator the reference carries and strict about everything else: an absolute path, any `..` segment, and any shape that is not exactly two segments resolve to nothing rather than escaping `.lore/doctrines/`.

**An unresolvable reference is silent on read.** `lore show` prints the stored reference, omits the `--- Mission Instructions ---` section, exits 0 and prints nothing else; `--json` carries the reference and `"doctrine_mission_contents": null`. `lore health --scope doctrines` is the single reporter, at ERROR severity, for active missions only (lore codex show decisions-033-unresolvable-reference-is-silent-on-read).

## Business Rules

- **Stored verbatim, never validated at write time:** `lore new mission -D <ref>` accepts any string. A reference naming no doctrine and no mission is stored exactly as typed.
- **Mission body drives the worker; the description drives the run:** an orchestrator that restates the doctrine mission body in the description creates a second copy of it. The description carries only what is specific to this run.
- **Dependency resolution:** the design table's Depends On column names doctrine mission ids. After the orchestrator creates all Missions for a Quest, it declares each dependency with the real Lore Mission IDs.
- **Doctrine changes reach live Missions:** because resolution happens at read time, editing a doctrine mission file changes what every Mission pointing at it reads next. Renaming or removing one breaks those references, and `lore health --scope doctrines` reports each one.
- **One doctrine mission, one Lore Mission per quest:** the convention is one Mission per design-table row. An orchestrator may deviate, but that is outside Lore's model.

## Concrete Examples

### Orchestrator reading a design row and creating a Mission

```
| Phase | Mission | Type | Depends On | Input | Output |
|-------|---------|------|------------|-------|--------|
| 2 | tech-spec | agent | prd-gate | PRD, technical map | Final Tech Spec |
```

```
$ lore new mission -q q-9001 \
    -T agent \
    -p 2 \
    -D quick-feature-implementation/tech-spec \
    -d "Build the auth module spec. PRD: <codex-id>." \
    "Tech Spec: Build auth module"
Mission q-9001/m-001 created.
```

The worker then runs `lore show q-9001/m-001` and receives the description and the `tech-spec` mission body together.

### Dependency resolution after batch creation

```
# The design table says tech-spec depends on prd-gate.
# After creating all missions:
$ lore needs q-9001/m-001:q-9001/m-000
```

The orchestrator maps doctrine mission ids to real Lore Mission IDs itself.
