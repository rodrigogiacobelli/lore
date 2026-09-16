---
id: commit-phase-2
title: Commit Phase 2 — tech spec
summary: Commits the Phase 2 tech spec as the gate into Phase 3.
---

# Commit Phase 2

You are the orchestrator handling a chore inline. You commit the phase's outputs and nothing else.

## How You Work

You stage deliberately. A phase commit is a gate — it marks the point the pipeline can be resumed from, so it carries the phase's outputs and no unrelated change.

## Hard Rules

- Stage only the outputs this phase produced
- The commit message format is fixed — do not improvise one

## Inputs

The Phase 2 outputs: the Crazy Tech Spec, the annotated Tech Spec Draft, and the final Tech Spec.

## Steps

Commit all Phase 2 outputs.

Message: `Phase 2: <feature-keywords> — tech spec`

## Done Criteria

One commit exists carrying the Phase 2 outputs with the phase-numbered message.

Mark done: `lore done <mission-id>`

## Hands On

The gate into Phase 3.
