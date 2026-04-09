---
id: quick-feature-implementation
title: Quick Feature Implementation
summary: Streamlined spec-driven pipeline from raw user input to implementation-ready user stories. Single scout, no crazy phases, single commit at the end.
---

# Quick Feature Implementation

## Doctrine

| Phase | Step | Type | Knight | Depends On | Input | Output |
|-------|------|------|--------|------------|-------|--------|
| 0 | Scout | knight | scout | — | Feature request | Business map + technical map |
| 1 | PRD | knight | pm | scout | Feature request, both maps | Final PRD |
| 1 | PRD Gate | human | — | prd | Final PRD | PRD + pre-architecture notes |
| 2 | Tech Spec | knight | architect | prd-gate | PRD, technical map | Final Tech Spec |
| 2 | Tech Spec Gate | human | — | tech-spec | Final Tech Spec | Annotated Tech Spec |
| 3 | BA Stories | knight | ba | tech-spec-gate | PRD, Tech Spec, business map | Finalized user stories + index |
| 3 | Codex Apply | knight | tech-writer | tech-spec-gate | PRD, Tech Spec, context maps | Updated codex documents |
| 3 | Tech Notes | knight | tech-lead | ba-stories, codex-apply | User stories, Tech Spec, updated codex | Stories with tech notes + stubs |
| 4 | Commit | constable | — | tech-notes | — | — |

## Artifacts

- **fi-context-map** — Scout output: maps codex documents relevant to the feature by lens
- **fi-prd** — Final PRD, self-contained product source of truth
- **fi-tech-spec** — Final Tech Spec with complete test strategy
- **fi-user-story** — Individual user story with acceptance criteria and tech notes
- **fi-user-story-index** — Index of all stories with PRD coverage map

## Knights

- **scout** — Maps the codex from both business and technical lenses in one pass.
- **pm** — Structures raw input into a concrete, scoped PRD.
- **architect** — Makes concrete architectural decisions. Produces Tech Specs.
- **ba** — Writes and finalizes testable user stories grounded in the PRD.
- **tech-writer** — Applies codex changes directly — no proposal step.
- **tech-lead** — Adds implementation layer to stories in one pass.

## Escalation

| Scenario | Orchestrator May | Orchestrator May Not |
|----------|-----------------|----------------------|
| Agent blocks on an unclear requirement | Surface the block to human, resume after clarification | Skip the step or approximate the output |
| PRD Gate surfaces scope too large for this cycle | Halt the quest, surface to human with a scope reduction proposal | Continue to Phase 2 with unresolved scope |
| Tech Spec Gate reveals an irreconcilable conflict | Block Phase 3, surface to human | Proceed with an unresolved spec |

## Notes

- Streamlined version of feature-implementation — use when the feature is well-understood and creative divergence phases are not needed
- Single scout handles both lenses in one mission; tech-writer applies codex changes directly without a proposal step
- BA stories are drafted and finalized in one mission (no separate draft/final split)
- Single commit at the end covers all outputs
