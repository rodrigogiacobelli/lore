---
id: feature-implementation
title: Feature Implementation
summary: E2E spec-driven pipeline from raw user input to implementation-ready user stories with test stubs. Four phases strictly downstream — Scout, PRD, Tech Spec, Stories.
---

# Feature Implementation

## Doctrine

| Phase | Mission | Type | Depends On | Input | Output |
|-------|---------|------|------------|-------|--------|
| 0 | business-scout | agent | — | Feature request | Business context map |
| 0 | technical-scout | agent | — | Feature request | Technical context map |
| 0 | commit-phase-0 | constable | business-scout, technical-scout | — | — |
| 1 | crazy-prd | agent | commit-phase-0 | Feature request, business map | Crazy PRD |
| 1 | prd-draft | agent | commit-phase-0 | Feature request, business map, technical map | PRD Draft |
| 1 | prd-review | human | crazy-prd, prd-draft | Crazy PRD + PRD Draft | Annotated PRD Draft |
| 1 | prd-final | agent | prd-review | Annotated PRD Draft | Final PRD |
| 1 | prd-sign-off | human | prd-final | Final PRD | PRD + pre-architecture notes |
| 1 | commit-phase-1 | constable | prd-sign-off | — | — |
| 2 | crazy-tech-spec | agent | commit-phase-1 | PRD, technical map | Crazy Tech Spec |
| 2 | tech-spec-draft | agent | commit-phase-1 | PRD, technical map | Tech Spec Draft |
| 2 | tech-spec-review | human | crazy-tech-spec, tech-spec-draft | Both specs | Annotated Tech Spec Draft |
| 2 | tech-spec-final | agent | tech-spec-review | Annotated Tech Spec Draft + Crazy Tech Spec | Final Tech Spec |
| 2 | commit-phase-2 | constable | tech-spec-final | — | — |
| 3 | ba-stories-draft | agent | commit-phase-2 | PRD, Tech Spec, business map | User story files + index |
| 3 | ba-stories-final | agent | ba-stories-draft | User story drafts | Finalized user stories + index |
| 3 | codex-proposal | agent | commit-phase-2 | PRD, Tech Spec, context maps | Codex change proposal |
| 3 | codex-apply | agent | codex-proposal | Codex change proposal | Updated codex documents |
| 3 | tech-notes-draft | agent | ba-stories-final, codex-apply | User stories, Tech Spec, updated codex | Stories with draft tech notes |
| 3 | tech-notes-final | agent | tech-notes-draft | Stories with draft tech notes | Finalized stories with stubs |
| 3 | commit-phase-3 | constable | tech-notes-final | — | — |

## Missions

- **business-scout** — Maps the codex through the business lens. Read-only.
- **technical-scout** — Maps the codex through the technical lens. Read-only.
- **commit-phase-0** — Commits the context maps.
- **crazy-prd** — Divergent product ideas that challenge the obvious interpretation.
- **prd-draft** — Structures raw input into a concrete, scoped PRD draft.
- **prd-review** — Human reads both PRDs and appends feedback to the draft.
- **prd-final** — Produces the clean, self-contained final PRD.
- **prd-sign-off** — Human appends pre-architecture notes to the final PRD.
- **commit-phase-1** — Commits the PRD.
- **crazy-tech-spec** — Unconventional technical approaches that challenge the Architect.
- **tech-spec-draft** — Makes concrete architectural decisions from the PRD.
- **tech-spec-review** — Human reads both specs and appends feedback to the draft.
- **tech-spec-final** — Produces the final Tech Spec with a complete test strategy.
- **commit-phase-2** — Commits the tech spec.
- **ba-stories-draft** — Writes testable user stories grounded in the PRD, plus the index.
- **ba-stories-final** — Verifies every story's testability and PRD coverage.
- **codex-proposal** — Lists every codex document to create, update or retire.
- **codex-apply** — Applies the approved codex changes exactly as proposed.
- **tech-notes-draft** — Adds verified paths and test stubs beneath each story.
- **tech-notes-final** — Verifies every stub, path and reference in the tech notes.
- **commit-phase-3** — Commits the stories and codex.

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

## Escalation

| Scenario | Orchestrator May | Orchestrator May Not |
|----------|-----------------|----------------------|
| Agent blocks on an unclear requirement | Surface the block to human, resume after clarification | Skip the mission or approximate the output |
| PRD sign-off surfaces scope too large for this cycle | Halt the quest, surface to human with a scope reduction proposal | Continue to Phase 2 with unresolved scope |
| Tech Spec Final reveals an irreconcilable architectural conflict | Create a scoped investigation mission, block Phase 3 until resolved | Proceed to Phase 3 with an incomplete spec |
| BA stories cannot be traced to the PRD | Block the BA mission, surface to human for PRD clarification | Invent requirements not in the PRD |
| Tech Notes Final finds missing stubs that cannot be resolved | Block the mission, surface to human — do not mark done with gaps | Ship stories with incomplete test coverage |

## Notes

- All phases are strictly downstream — no back-and-forth between phases
- Phase 3 has three parallel tracks (stories, codex, tech notes) but tech-notes-draft depends on both ba-stories-final and codex-apply completing first
- Crazy missions run in parallel with their structured counterparts — they are creative fuel, not authoritative output
- Each phase ends with a constable commit as a gate before the next phase begins
