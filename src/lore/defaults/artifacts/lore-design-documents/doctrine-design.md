---
id: doctrine-design
title: Doctrine Design
summary: >
  Template for designing a new doctrine before implementation. Fill in the
  table and sections, then hand it to an agent with /new-doctrine to generate
  all the required files. Once created, the completed design doc is saved
  alongside its doctrine YAML as <doctrine-name>.design.md.
---

# Doctrine Design

## New Doctrine

| Phase | Step | Type | Knight | Depends On | Input | Output |
|-------|------|------|--------|------------|-------|--------|
| 0 | Step name | knight \| human \| constable | knight-slug or "new" or — | step-id or — | what the agent reads | what the agent produces |

<!--
Phase:       Steps with the same phase number can run in parallel.
Type:        knight = AI agent, human = requires user action, constable = orchestrator chore (commit, housekeeping).
Knight:      Slug of an existing or new knight. Use — for human and constable steps.
Depends On:  Step ID(s) that must complete before this step starts. Use — if none beyond phase order.
Input:       What the agent reads to do its work.
Output:      What the agent produces.
-->

## New Artifacts

<!--
List each new artifact this doctrine needs. Agents retrieve artifacts mid-mission
with `lore artifact show <id>`. Leave empty if reusing existing artifacts only.
-->

- **Artifact Name** (`artifact-slug`)
  - Purpose: what this document is and when it gets created
  - Type: template | checklist | policy | reference | decision

## New Knights

<!--
List each new knight this doctrine needs. Leave empty if reusing existing knights only.
-->

- **Knight Name** (`knight-slug`)
  - Role: one sentence on who this knight is
  - How they work: behavioral approach, methodology, domain expertise
  - Hard rules: constraints that are always true for this role, regardless of mission

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
- Reused knights or artifacts (existing slugs, no changes needed)
- Constraints on the overall workflow
- Context the orchestrator needs to understand the doctrine's intent
-->
