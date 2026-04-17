---
id: tdd-feature
title: TDD Feature
summary: Full spec pipeline followed by grouped TDD dev cycles. Stories are sized by the tech-lead and grouped by a knight. Orchestrator creates dev cycle missions dynamically after groups are defined.
---

# TDD Feature

## Doctrine

| Phase | Step | Type | Knight | Depends On | Input | Output |
|-------|------|------|--------|------------|-------|--------|
| 0 | Branch | constable | — | — | Quest title | Feature branch created off `work` |
| 1 | Scout | knight | scout | branch | Feature request | Business map + technical map |
| 2 | PRD | knight | pm | scout | Feature request, both maps | Final PRD |
| 2 | PRD Gate | human | — | prd | Final PRD | PRD + pre-architecture notes |
| 3 | Tech Spec | knight | architect | prd-gate | PRD, technical map | Final Tech Spec |
| 3 | Tech Spec Gate | human | — | tech-spec | Final Tech Spec | Annotated Tech Spec |
| 4 | BA Stories | knight | ba | tech-spec-gate | PRD, Tech Spec, business map | Finalized user stories + index |
| 4 | Codex Apply | knight | tech-writer | tech-spec-gate | PRD, Tech Spec, context maps | Updated codex documents |
| 4 | Tech Notes | knight | tech-lead | ba-stories, codex-apply | User stories, Tech Spec, updated codex | Stories with tech notes + complexity |
| 5 | Group Stories | knight | story-grouper | tech-notes | Sized stories + index | Groups appended to index + spec committed |

> **Phases 6+ are created dynamically.** After `group-stories` completes, the orchestrator reads the "Dev Cycle Groups" section from the story index and creates one Red → Green → Refactor → Dev Commit chain per group. Groups run sequentially: each group's Red depends on the previous group's Dev Commit.

## Orchestrator Boot Sequence

1. Create all fixed missions (branch through group-stories) using `start-tdd-quest`
2. Dispatch branch constable, then spec pipeline agents
3. When `group-stories` is done: read the story index, parse the "Dev Cycle Groups" section
4. For each group, create four missions: Red, Green, Refactor, Dev Commit
5. Wire dependencies: G1/Red has no needs (group-stories already done); G2/Red needs G1/Dev Commit; etc.
6. Dispatch Group 1 Red immediately

## Artifacts

- **fi-context-map** — Scout output: maps codex documents relevant to the feature by lens
- **fi-prd** — Final PRD, self-contained product source of truth
- **fi-tech-spec** — Final Tech Spec with complete test strategy
- **fi-user-story** — Individual user story with acceptance criteria and tech notes
- **fi-user-story-index** — Index of all stories with PRD coverage map and Dev Cycle Groups section

## Knights

- **scout** — Maps the codex from both business and technical lenses in one pass.
- **pm** — Structures raw input into a concrete, scoped PRD.
- **architect** — Makes concrete architectural decisions. Produces Tech Specs.
- **ba** — Writes and finalizes testable user stories grounded in the PRD.
- **tech-writer** — Applies codex changes directly — no proposal step.
- **tech-lead** — Adds implementation layer and complexity estimate to each story.
- **story-grouper** — Groups sized stories into dev cycle batches, appends groups to the index, commits spec outputs.
- **tdd-red** — Writes failing tests from acceptance criteria. No production code ever.
- **tdd-green** — Writes minimum viable production code to make tests pass. No refactoring.
- **tdd-refactor** — Improves code quality without changing behavior. Tests must stay green.

## Grouping Rules

`story-grouper` applies these rules to batch stories into dev cycles:

- **XL story** → one group alone
- **L story** → one group alone, or paired with a closely related S
- **M/S stories** → grouped by theme or shared infrastructure

Output format (appended to story index):
```
## Dev Cycle Groups
- G1: [<id1>, <id2>] — <one-line rationale>
- G2: [<id3>] — <one-line rationale>
```

## Git Flow

```
work
└── feat/<feature-slug>   ← created by Branch constable (Phase 0)
     ├── spec + grouping committed by group-stories (Phase 5)
     └── Red → Green → Refactor → Dev Commit (per group, sequentially)
```

Human squash-merges `feat/<feature-slug>` → `work` when all groups are done. AI never touches `work`.

## Escalation

| Scenario | Orchestrator May | Orchestrator May Not |
|----------|-----------------|----------------------|
| Agent blocks on an unclear requirement | Surface to human, resume after clarification | Skip the step or approximate the output |
| PRD Gate surfaces scope too large | Halt quest, surface scope reduction proposal | Continue to Phase 3 with unresolved scope |
| Tech Spec Gate reveals irreconcilable conflict | Block Phase 4, surface to human | Proceed with unresolved spec |
| Red: test passes immediately | Block mission, agent must fix or remove the test | Mark Red done with passing tests |
| Green: tests cannot pass with Tech Notes approach | Block mission, surface to human | Modify test files or skip failing tests |
| Refactor: refactoring breaks a test | Block mission, agent must revert and report | Accept a refactor that breaks tests |

## Notes

- Branch is Phase 0 — the very first step. All work happens on `feat/<feature-slug>`, never on `work`
- `group-stories` commits all `.lore/` spec outputs — there is no separate spec-commit mission
- Dev cycle missions are created by the orchestrator after `group-stories` completes, not pre-defined in this YAML
- `dev-commit` (per group) stages only `src/` and `tests/` — spec artifacts already committed
- Human squash-merges the feature branch into `work` — AI agents never merge
