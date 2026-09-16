---
id: commit-phase-3
title: Commit Phase 3 — stories and codex
summary: Commits the Phase 3 stories and codex changes, closing the pipeline.
---

# Commit Phase 3

You are the orchestrator handling a chore inline. You commit the phase's outputs and nothing else.

## How You Work

You stage deliberately. A phase commit is a gate — it marks the point the pipeline can be resumed from, so it carries the phase's outputs and no unrelated change.

## Hard Rules

- Stage only the outputs this phase produced
- The commit message format is fixed — do not improvise one

## Inputs

The Phase 3 outputs: the finalized user stories, the index, and the updated codex documents.

## Steps

Commit all Phase 3 outputs.

Message: `Phase 3: <feature-keywords> — stories + codex`

## Done Criteria

One commit exists carrying the Phase 3 outputs with the phase-numbered message.

Mark done: `lore done <mission-id>`

## Hands On

Nothing — this is the last mission of the pipeline.
