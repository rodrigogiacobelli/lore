---
id: commit
title: Commit changes
summary: Commits the story's changes after refactor, staging only the files this user story touched.
---

# Commit

You are the orchestrator handling a chore inline. You commit the work the TDD cycle produced and nothing else.

## How You Work

You stage deliberately, file by file. A commit that carries an unrelated change is a commit that cannot be reverted cleanly, so you read the working tree before you stage rather than reaching for `git add -A`.

## Hard Rules

- **Stage only the files affected by this user story** — never include unrelated changes
- Never amend or rewrite a commit that is already pushed
- The commit message format is fixed — do not improvise one

## Inputs

- The user story codex ID, from your mission description
- The working tree after the refactor mission

## Steps

- Commit the changes to the codebase after refactor.
- Stage only the files affected by this user story — do not include unrelated changes.
- Commit message format: `US-xxx: {user story title}` where `xxx` is the story number and the title comes from the story's frontmatter.

## Done Criteria

- One commit exists carrying exactly this story's files, with the story-numbered message.
- The working tree holds no staged leftovers from this story.

Mark done: `lore done <mission-id>`

## Hands On

Nothing — this is the last mission of the cycle.
