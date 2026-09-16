---
id: prd-gate
title: Review PRD — append pre-architecture notes
summary: Human gate on the PRD, with pre-architecture notes appended for the tech-spec mission.
---

# PRD Gate

This mission belongs to the human. The orchestrator does not claim it and does not complete it.

## How It Works

The human reads the PRD and fills the Pre-Architecture Notes section — technical preferences, constraints, priorities, or context. That section is the one channel through which the human steers Phase 2.

## Hard Rules

- The orchestrator never marks this mission done on the human's behalf
- Notes go into the Pre-Architecture Notes section of the PRD, not into a new document

## Inputs

The PRD ID, from the board: `lore show <mission-id>`

## Steps

- Read the PRD from your board: `lore show <mission-id>`.
- Read it: `lore codex show <prd-id>`.
- Append pre-architecture notes directly to the Pre-Architecture Notes section — technical preferences, constraints, priorities, or context for the tech-spec mission.

## Done Criteria

The PRD's Pre-Architecture Notes section carries the human's notes.

Mark done.

## Hands On

The PRD with pre-architecture notes, to tech-spec.
