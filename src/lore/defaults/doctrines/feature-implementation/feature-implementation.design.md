---
id: feature-implementation
title: Feature Implementation
summary: E2E spec-driven pipeline from raw user input to implementation-ready user stories with test stubs. Four phases strictly downstream — Scout, PRD, Tech Spec, Stories.
---

# Feature Implementation

## Doctrine

| Phase | Step | Type | Knight | Depends On | Input | Output |
|-------|------|------|--------|------------|-------|--------|
| 0 | Map codex — business | knight | scout | — | Feature request | Business context map |
| 0 | Map codex — technical | knight | scout | — | Feature request | Technical context map |
| 0 | Commit Phase 0 | constable | — | business-scout, technical-scout | — | — |
| 1 | Crazy PRD | knight | crazy-pm | commit-phase-0 | Feature request, business map | Crazy PRD |
| 1 | PRD Draft | knight | pm | commit-phase-0 | Feature request, business map, technical map | PRD Draft |
| 1 | PRD Review | human | — | crazy-prd, prd-draft | Crazy PRD + PRD Draft | Annotated PRD Draft |
| 1 | PRD Final | knight | pm | prd-review | Annotated PRD Draft | Final PRD |
| 1 | PRD Sign-off | human | — | prd-final | Final PRD | PRD + pre-architecture notes |
| 1 | Commit Phase 1 | constable | — | prd-sign-off | — | — |
| 2 | Crazy Tech Spec | knight | crazy-architect | commit-phase-1 | PRD, technical map | Crazy Tech Spec |
| 2 | Tech Spec Draft | knight | architect | commit-phase-1 | PRD, technical map | Tech Spec Draft |
| 2 | Tech Spec Review | human | — | crazy-tech-spec, tech-spec-draft | Both specs | Annotated Tech Spec Draft |
| 2 | Tech Spec Final | knight | architect | tech-spec-review | Annotated Tech Spec Draft + Crazy Tech Spec | Final Tech Spec |
| 2 | Commit Phase 2 | constable | — | tech-spec-final | — | — |
| 3 | BA Stories Draft | knight | ba | commit-phase-2 | PRD, Tech Spec, business map | User story files + index |
| 3 | BA Stories Final | knight | ba | ba-stories-draft | User story drafts | Finalized user stories + index |
| 3 | Codex Proposal | knight | tech-writer | commit-phase-2 | PRD, Tech Spec, context maps | Codex change proposal |
| 3 | Codex Apply | knight | tech-writer | codex-proposal | Codex change proposal | Updated codex documents |
| 3 | Tech Notes Draft | knight | tech-lead | ba-stories-final, codex-apply | User stories, Tech Spec, updated codex | Stories with draft tech notes |
| 3 | Tech Notes Final | knight | tech-lead | tech-notes-draft | Stories with draft tech notes | Finalized stories with stubs |
| 3 | Commit Phase 3 | constable | — | tech-notes-final | — | — |

## Artifacts

- **fi-context-map** — Scout output: maps codex documents relevant to the feature by lens
- **fi-crazy-prd** — Divergent product ideas to challenge obvious interpretations
- **fi-prd-draft** — Structured PRD draft with user workflows and functional requirements
- **fi-prd** — Clean final PRD, self-contained product source of truth
- **fi-crazy-tech-spec** — Unconventional technical approaches to challenge the Architect
- **fi-tech-spec-draft** — Concrete technical specification draft
- **fi-tech-spec** — Final Tech Spec with complete test strategy
- **fi-codex-change-proposal** — List of codex documents to create, update, or retire
- **fi-user-story** — Individual user story with acceptance criteria and tech notes
- **fi-user-story-index** — Index of all stories with PRD coverage map

## Knights

- **scout** — Maps the codex from a specific lens (business or technical). Read-only.
- **crazy-pm** — Divergent PM: challenges obvious product interpretations.
- **pm** — Structures raw input into a concrete, scoped PRD.
- **crazy-architect** — Divergent Architect: challenges obvious technical choices.
- **architect** — Makes concrete architectural decisions. Produces Tech Specs.
- **ba** — Writes testable user stories grounded in the PRD.
- **tech-writer** — Keeps the codex aligned with what will be built.
- **tech-lead** — Adds implementation layer to stories: verified paths, test stubs.

## Escalation

| Scenario | Orchestrator May | Orchestrator May Not |
|----------|-----------------|----------------------|
| Agent blocks on an unclear requirement | Surface the block to human, resume after clarification | Skip the step or approximate the output |
| PRD sign-off surfaces scope too large for this cycle | Halt the quest, surface to human with a scope reduction proposal | Continue to Phase 2 with unresolved scope |
| Tech Spec Final reveals an irreconcilable architectural conflict | Create a scoped investigation mission, block Phase 3 until resolved | Proceed to Phase 3 with an incomplete spec |
| BA stories cannot be traced to the PRD | Block the BA mission, surface to human for PRD clarification | Invent requirements not in the PRD |
| Tech Notes Final finds missing stubs that cannot be resolved | Block the mission, surface to human — do not mark done with gaps | Ship stories with incomplete test coverage |

## Notes

- All phases are strictly downstream — no back-and-forth between phases
- Phase 3 has three parallel tracks (BA, Tech Writer, Tech Lead) but Tech Lead depends on both BA Final and Codex Apply completing first
- Crazy variants run in parallel with their structured counterparts — they are creative fuel, not authoritative output
- Each phase ends with a constable commit as a gate before the next phase begins
