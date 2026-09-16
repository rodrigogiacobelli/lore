---
id: tdd-implementation
title: TDD Implementation
summary: Strict Red-Green-Refactor cycle for a single dev-ready user story. Hard boundaries between each mission — no production code in Red, no test changes in Green, no new features in Refactor.
---

# TDD Implementation

## Doctrine

| Phase | Mission | Type | Depends On | Input | Output |
|-------|---------|------|------------|-------|--------|
| 0 | red | agent | — | User story with Tech Notes | Failing tests |
| 0 | green | agent | red | Failing tests, Tech Notes | Passing tests + production code |
| 0 | refactor | agent | green | Production code + tests | Clean, passing code |
| 0 | commit | constable | refactor | — | — |

## Missions

- **red** — Writes failing tests from acceptance criteria. No production code ever.
- **green** — Writes minimum viable production code to make tests pass. No refactoring.
- **refactor** — Improves code quality without changing behavior. Tests must stay green.
- **commit** — Commits the story's changes with the story-numbered message.

## Artifacts

None — the user story and its Tech Notes are the inputs, created upstream by the feature-implementation pipeline.

## Escalation

| Scenario | Orchestrator May | Orchestrator May Not |
|----------|-----------------|----------------------|
| Red: test passes immediately (not testing new behavior) | Block the mission, ask the agent to fix or remove the test | Mark Red done with passing tests |
| Green: tests cannot be made to pass with the Tech Notes approach | Block the mission, surface to human — the Tech Notes may need revision | Modify test files or skip failing tests |
| Refactor: refactoring breaks a test | Block the mission, agent must revert and report | Accept a refactor that breaks tests |

## Notes

- All four missions share the same phase (0) but are strictly sequential — each depends on the one before it
- This doctrine is instantiated once per user story — run it multiple times in parallel for multiple stories
- The user story codex ID is passed in the mission description by the orchestrator
- Commit message format: `US-xxx: {user story title}`
