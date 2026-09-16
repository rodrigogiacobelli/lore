---
id: doctrine-design
title: Doctrine Design
summary: >
  Template for designing a new doctrine before implementation. Fill in the
  table and sections, then hand it to an agent with /update-doctrine to generate
  the doctrine directory. The completed design doc is the doctrine's
  <doctrine-name>.design.md, and each mission listed here becomes one file under
  missions/, written from the mission-design artifact.
---

# Doctrine Design

A doctrine is a directory: this design document, which the orchestrator reads to plan a quest, and one `missions/<mission-id>.md` of prose for each worker. This template is the design document.

The design document holds everything about the shape of the work — which missions exist, what order they run in, who runs each one, what feeds what. Each mission's own instructions live in its mission file and nowhere else. Write those from `lore artifact show mission-design`.

## New Doctrine

| Phase | Mission | Type | Depends On | Input | Output |
|-------|---------|------|------------|-------|--------|
| 0 | mission-id | agent \| constable \| human | mission-id or — | what the worker reads | what the worker produces |

<!--
Phase:       Missions with the same phase number can run in parallel.
Mission:     The mission id — lowercase, hyphenated, and the filename stem of missions/<id>.md.
Type:        agent = dispatched to a worker; human = requires user action;
             constable = orchestrator chore handled inline (commit, housekeeping).
Depends On:  Mission ID(s) that must complete before this mission starts. Use — if none beyond phase order.
Input:       What the worker reads to do its work.
Output:      What the worker produces.
-->

## Missions

<!--
One line per mission in the table above, in the same order. The one-line purpose
is what an orchestrator reads when deciding what a mission is for; the full
instructions live in missions/<id>.md.

Every mission file is written from the mission-design template:
`lore artifact show mission-design`
-->

- **mission-id** — one line on what this mission does.

## New Artifacts

<!--
List each new artifact this doctrine needs. Missions retrieve artifacts mid-run
with `lore artifact show <id>`. Leave empty if reusing existing artifacts only.
-->

- **Artifact Name** (`artifact-slug`)
  - Purpose: what this document is and when it gets created
  - Type: template | checklist | policy | reference | decision

## Escalation

<!--
Define what the orchestrator can and cannot do when something goes wrong.
This prevents improvised responses and keeps the quest from spiraling.
-->

| Scenario | Orchestrator May | Orchestrator May Not |
|----------|-----------------|----------------------|
| Describe what went wrong | Actions allowed: block mission, create a scoped investigation mission, escalate to human | Actions forbidden: what would exceed the doctrine's scope or authority |

## Notes

<!--
Anything not captured above:
- Reused artifacts (existing slugs, no changes needed)
- Constraints on the overall workflow
- Context the orchestrator needs to understand the doctrine's intent
-->
