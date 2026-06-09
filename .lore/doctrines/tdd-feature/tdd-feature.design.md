---
id: tdd-feature
title: TDD Feature
summary: Spec pipeline over a pre-existing PRD — Scout, Tech Spec, ADR reconciliation, human gate, then parallel Tech Planning and Codex Apply — followed by grouped TDD dev cycles and a final defaults reconciliation. Deliverables are authored and sized in one Tech Planning pass; the orchestrator creates dev cycle and Defaults Review missions dynamically.
---

# TDD Feature

## Precondition

A final **PRD already exists in the codex before this doctrine runs.** Product planning — PRD authoring and its review gate — happens *before* the quest is started (e.g. via the `feature-implementation` or `quick-feature-implementation` doctrine, or by hand). This doctrine does **not** produce a PRD; it consumes one. The orchestrator passes the PRD codex ID into the quest's mission descriptions. If there is no settled PRD, do not start this doctrine.

## Doctrine

| Phase | Step | Type | Knight | Depends On | Input | Output |
|-------|------|------|--------|------------|-------|--------|
| 0 | Branch | constable | — | — | Quest title | Feature branch created off `work` |
| 1 | Scout | knight | scout | branch | Feature request, existing PRD | Business map + technical map |
| 2 | Tech Spec | knight | architect | scout | PRD, technical map | Final Tech Spec |
| 3 | ADR Enforcer | knight | adr-standards-enforcer | tech-spec | Tech Spec, ADRs, standards | Tech Spec reconciled to ADRs + audit |
| 4 | Spec Gate | human | — | adr-enforce | Reconciled Tech Spec | Annotated Tech Spec |
| 5 | Tech Planning | knight | tech-planner | spec-gate | Tech Spec, PRD, technical map | Sized, testable user stories + index |
| 5 | Codex Apply | knight | tech-writer | spec-gate | Tech Spec, PRD, context maps | Updated codex + new ADRs |
| 6 | Group Stories | knight | story-grouper | tech-planning, codex-apply | Sized stories + index | Groups appended to index + spec committed |
| 7+ | **Dev Cycle** (per group) | knights + constable | tdd-red → tdd-green → tdd-refactor → — | group-stories | Story group | Red → Green → Refactor → Dev Commit |
| last | **Defaults Review** | knight | defaults-reviewer | last Dev Commit | Shipped diff, stories, Tech Spec | `src/lore/defaults/` reconciled + committed |

> **Phases 7+ are created dynamically.** After `group-stories` completes, the orchestrator reads the "Dev Cycle Groups" section from the story index and creates one Red → Green → Refactor → Dev Commit chain per group. Groups run sequentially: each group's Red depends on the previous group's Dev Commit. After the **last** group's Dev Commit, the orchestrator creates one **Defaults Review** mission depending on it.

### The TDD Dev Cycle (per group)

Each story group runs a strict four-step cycle. Hard boundaries between steps — the boundary is the point.

| Step | Type | Knight | Rule |
|------|------|--------|------|
| Red | knight | tdd-red | Writes failing tests from the story's acceptance criteria. **No production code, ever.** Tests must fail for the right reason. |
| Green | knight | tdd-green | Writes the **minimum** production code to make every Red test pass. No refactoring, no new features, no test edits. |
| Refactor | knight | tdd-refactor | Improves production and test code — clarity, naming, duplication — **without changing behavior.** Tests must stay green. |
| Dev Commit | constable | — | Stages only `src/` and `tests/` and commits the group's work. Spec artifacts were already committed by group-stories. |

## Orchestrator Boot Sequence

1. Confirm a settled PRD exists; capture its codex ID. Put it in each mission description that needs it.
2. Create all fixed missions (branch through group-stories) using `start-tdd-quest`.
3. Dispatch branch constable, then the spec pipeline agents (Scout → Tech Spec → ADR Enforcer → Spec Gate → Tech Planning ∥ Codex Apply).
4. When `group-stories` is done: read the story index, parse the "Dev Cycle Groups" section.
5. For each group, create four missions: Red, Green, Refactor, Dev Commit.
6. Wire dependencies: G1/Red has no needs (group-stories already done); G2/Red needs G1/Dev Commit; etc. Dispatch Group 1 Red immediately.
7. After the **last** group's Dev Commit completes, create one **Defaults Review** mission (knight `tdd-feature/defaults-reviewer.md`) depending on it. Dispatch it.
8. When Defaults Review is done, the branch is ready for human squash-merge into `work`.

## Artifacts

- **fi-context-map** — Scout output: maps codex documents relevant to the feature by lens
- **fi-tech-spec** — Final Tech Spec with complete test strategy (and the appended ADR & Standards Audit)
- **fi-user-story** — Individual user story with acceptance criteria **and** tech notes (authored in one pass by Tech Planning)
- **fi-user-story-index** — Index of all stories with the coverage map and Dev Cycle Groups section

> The PRD is a **precondition input**, not an output of this doctrine — it uses `fi-prd` but does not produce it.

## Knights

- **scout** — Maps the codex from both business and technical lenses in one pass.
- **architect** — Makes concrete architectural decisions. Produces Tech Specs.
- **adr-standards-enforcer** — Reconciles the Tech Spec against settled ADRs and standards: rewrites conflicting lines to comply, fills cross-cutting gaps, flags new decisions that need an ADR, escalates what it cannot resolve. Audits in place; never silently passes a spec that contradicts an ADR.
- **tech-planner** (Tech Lead — Tech Planning) — Translates the settled Tech Spec into the full set of deliverables: testable user stories with verified file paths, a test stub per acceptance-criterion scenario, and a complexity estimate each. Owns authoring **and** sizing — there is no separate BA.
- **tech-writer** — Applies codex changes directly — no proposal step. Creates an ADR for each new decision the enforcer flagged.
- **story-grouper** — Groups sized stories into dev cycle batches, appends groups to the index, commits spec outputs.
- **tdd-red** — Writes failing tests from acceptance criteria. No production code ever.
- **tdd-green** — Writes minimum viable production code to make tests pass. No refactoring.
- **tdd-refactor** — Improves code quality without changing behavior. Tests must stay green.
- **defaults-reviewer** — After the dev cycles ship, reconciles `src/lore/defaults/` (docs, artifacts, doctrines, knights, skills, watchers, schema) with what was actually built; creates/updates/deletes seeds so a fresh `lore init` reflects reality, then commits.

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
     ├── spec + grouping committed by group-stories (Phase 6)
     ├── Red → Green → Refactor → Dev Commit (per group, sequentially)
     └── seed reconciliation committed by defaults-reviewer (final)
```

Human squash-merges `feat/<feature-slug>` → `work` when Defaults Review is done. AI never touches `work`.

## Escalation

| Scenario | Orchestrator May | Orchestrator May Not |
|----------|-----------------|----------------------|
| Agent blocks on an unclear requirement | Surface to human, resume after clarification | Skip the step or approximate the output |
| ADR Enforcer returns `BLOCKED` (unresolvable conflict) | Hold at the human gate until resolved | Proceed to Tech Planning with an unresolved ADR conflict |
| Spec Gate reveals an irreconcilable conflict | Block Phase 5, surface to human | Proceed with an unresolved spec |
| Red: test passes immediately | Block mission, agent must fix or remove the test | Mark Red done with passing tests |
| Green: tests cannot pass with the Tech Notes approach | Block mission, surface to human | Modify test files or skip failing tests |
| Refactor: refactoring breaks a test | Block mission, agent must revert and report | Accept a refactor that breaks tests |
| Defaults Review returns `HUMAN JUDGMENT REQUIRED` | Surface the listed seed drift to human | Squash-merge with seeds the agent flagged unresolved |

## Notes

- A settled PRD is a **precondition** — this doctrine consumes it, never produces it. Planning happens before the quest.
- Branch is Phase 0 — the very first step. All work happens on `feat/<feature-slug>`, never on `work`.
- The ADR Enforcer **rewrites** the spec to obey settled ADRs (it does not merely audit) and runs *before* the human gate, so the human reviews an already-reconciled spec.
- Tech Planning replaces the old BA + Tech Notes split — one knight (`tech-planner`) authors the stories and sizes them in a single pass. It runs in parallel with Codex Apply.
- `group-stories` commits all `.lore/` spec outputs (including new ADRs) — there is no separate spec-commit mission.
- Dev cycle missions and the final Defaults Review are created by the orchestrator after `group-stories` completes, not pre-defined in this YAML.
- `dev-commit` (per group) stages only `src/` and `tests/` — spec artifacts already committed.
- Defaults Review reconciles `src/lore/defaults/` against the shipped feature and is the last step before merge — it runs once, after the last dev cycle, not per group.
- Human squash-merges the feature branch into `work` — AI agents never merge.
