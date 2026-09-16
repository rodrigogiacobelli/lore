---
id: commit-phase-0
title: Commit Phase 0 — context maps
summary: Commits the Phase 0 context maps as the gate into Phase 1.
---

# Commit Phase 0

You are the orchestrator handling a chore inline. You commit the phase's outputs and nothing else.

## How You Work

You stage deliberately. A phase commit is a gate — it marks the point the pipeline can be resumed from, so it carries the phase's outputs and no unrelated change.

## Hard Rules

- Stage only the outputs this phase produced
- The commit message format is fixed — do not improvise one

## Inputs

The Phase 0 outputs: the business and technical context maps.

## Steps

Commit all Phase 0 outputs.

Message: `Phase 0: <feature-keywords> — context maps`

## Done Criteria

One commit exists carrying the Phase 0 outputs with the phase-numbered message.

Mark done: `lore done <mission-id>`

## Hands On

The gate into Phase 1.
