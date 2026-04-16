---
id: conceptual-workflows-typical-workflow
title: Typical Workflow
summary: What a complete Lore-driven workflow looks like when driven by an orchestrator
  — from project initialisation through quest and mission creation, dependency declaration,
  worker dispatch, and closure. This is a conceptual sequence, not a step-by-step
  user guide.
related:
- conceptual-workflows-lore-init
- conceptual-workflows-quest-crud
- conceptual-workflows-mission-crud
- conceptual-workflows-claim
- conceptual-workflows-done
- conceptual-entities-doctrine
---

# Typical Workflow

A complete Lore workflow follows this sequence when an orchestrator manages work through Lore.

## Sequence

1. **Project initialisation.** `lore init` creates the project structure — the `.lore/` directory, the database, default doctrines, default knights, and `AGENTS.md`. See conceptual-workflows-lore-init (lore codex show conceptual-workflows-lore-init) for the full behaviour.

2. **Workflow review (optional).** The orchestrator optionally reads a Doctrine (lore codex show conceptual-entities-doctrine) for workflow guidance. A Doctrine describes the typical steps, ordering, and suggested Knights for a body of work. The orchestrator uses it as a reference — there is no automated expansion.

3. **Quest creation.** The orchestrator creates a Quest (lore codex show conceptual-entities-quest) representing the body of work.

4. **Mission creation.** The orchestrator creates Missions (lore codex show conceptual-entities-mission) within the Quest, assigning Knights (lore codex show conceptual-entities-knight) and setting priorities. Missions carry the full description of what the worker needs to do.

5. **Dependency declaration.** Dependencies between Missions are declared so that the ready queue surfaces work in the right order. Dependencies are advisory for ordering; the system does not prevent a worker from claiming a Mission out of sequence, but the ready queue will prefer unblocked Missions.

6. **Claim and dispatch.** The orchestrator claims Missions and dispatches worker agents. Each worker receives a Mission ID and fetches its full context — Mission description and Knight instructions — in a single call.

7. **Execution and closure.** Workers execute their Missions and mark them done. Closing a Mission automatically unblocks any Missions that were waiting on it.

8. **Monitoring.** The orchestrator monitors progress via the dashboard (`lore`) and generates human-readable reports via `lore oracle`. To inspect the dependency structure of a quest, `lore show <quest-id>` renders all missions as a flat topologically-sorted list, making the execution order and current status immediately visible in one call. To inspect the full context of a specific mission — including its dependencies, board messages, and knight instructions — `lore show <mission-id>` is the single command needed.

9. **Quest closure.** Once all Missions are closed, a Quest with `auto_close` enabled closes automatically. A Quest with `auto_close` disabled (the default) must be closed explicitly.

## Dispatch Cycle Detail

Step 6 (claim and dispatch) follows this sequence for each mission:

1. **Check the ready queue** — `lore ready` returns the highest-priority unblocked mission(s). If the queue is empty, all missions are either blocked, in-progress, or closed. Run `lore` for a dashboard view.

2. **Review the mission** — `lore show <mission-id>` shows the description, assigned knight, dependencies, and any board messages from previous agents. Confirm the mission is self-contained before claiming.

3. **Claim before dispatching** — `lore claim <mission-id>` transitions the mission to `in_progress`. Always claim first. If you dispatch without claiming, another orchestrator could claim and dispatch the same mission concurrently.

4. **Dispatch with the mission ID only** — Pass only the mission ID to the worker. The worker fetches all context with `lore show <mission-id>`. Do not repeat the description in the dispatch message.

5. **Verify completion** — After the worker finishes, check `lore show <mission-id>` for board messages. Workers must post every codex document they created, updated, or deleted by ID. An empty board on a documentation-touching mission is a signal something was missed.

6. **Re-check the ready queue** — After closing a mission, its dependents that were waiting on it may become unblocked. Run `lore ready` again to continue the cycle.

**Quest closure:** A quest with `auto_close` enabled closes automatically when the last mission closes. A quest with `auto_close` disabled (the default) must be closed explicitly with `lore done <quest-id>`.

## Design Notes

Lore does not enforce this sequence. Agents can claim and work on Missions in any order regardless of dependencies. The dependency system is advisory — it influences the ready queue and enforces structural integrity (no circular dependencies), but does not block claims.

> **Context-aware quest inference:** When exactly one non-closed Quest exists, mission creation commands automatically infer it as the target Quest, removing the need to specify the `-q` flag explicitly. If zero or multiple active Quests exist, the behavior falls back to creating a standalone mission.

## Related

- conceptual-workflows-lore-init (lore codex show conceptual-workflows-lore-init) — what `lore init` does internally
- conceptual-entities-quest (lore codex show conceptual-entities-quest) — Quest concepts and status rules
- conceptual-entities-mission (lore codex show conceptual-entities-mission) — Mission concepts, types, and status machine
- conceptual-entities-doctrine (lore codex show conceptual-entities-doctrine) — Doctrine concepts
- conceptual-entities-knight (lore codex show conceptual-entities-knight) — Knight concepts
- tech-cli-commands (lore codex show tech-cli-commands) — CLI command reference
