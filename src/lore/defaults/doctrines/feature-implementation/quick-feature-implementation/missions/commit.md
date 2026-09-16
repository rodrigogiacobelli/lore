---
id: commit
title: Commit all pipeline outputs
summary: Commits every pipeline output in a single commit.
---

# Commit

You are the orchestrator handling a chore inline. You commit the pipeline's outputs and nothing else.

## How You Work

You stage deliberately. This pipeline ends in one commit, so it carries every output the pipeline produced and no unrelated change.

## Hard Rules

- Stage only the outputs this pipeline produced
- The commit message format is fixed — do not improvise one

## Inputs

Every pipeline output: the context maps, the PRD, the Tech Spec, the user stories with tech notes, the index, and the updated codex documents.

## Steps

Commit all pipeline outputs in a single commit.

Message: `feat(<feature-slug>): PRD, tech spec, user stories, codex updates`

## Done Criteria

One commit exists carrying every pipeline output with the feature-slugged message.

Mark done: `lore done <mission-id>`

## Hands On

Nothing — this is the last mission of the pipeline.
