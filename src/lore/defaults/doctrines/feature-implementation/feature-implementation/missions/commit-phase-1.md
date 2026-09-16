---
id: commit-phase-1
title: Commit Phase 1 — PRD
summary: Commits the Phase 1 PRD as the gate into Phase 2.
---

# Commit Phase 1

You are the orchestrator handling a chore inline. You commit the phase's outputs and nothing else.

## How You Work

You stage deliberately. A phase commit is a gate — it marks the point the pipeline can be resumed from, so it carries the phase's outputs and no unrelated change.

## Hard Rules

- Stage only the outputs this phase produced
- The commit message format is fixed — do not improvise one

## Inputs

The Phase 1 outputs: the Crazy PRD, the annotated PRD Draft, and the signed-off final PRD.

## Steps

Commit all Phase 1 outputs.

Message: `Phase 1: <feature-keywords> — PRD`

## Done Criteria

One commit exists carrying the Phase 1 outputs with the phase-numbered message.

Mark done: `lore done <mission-id>`

## Hands On

The gate into Phase 2.
