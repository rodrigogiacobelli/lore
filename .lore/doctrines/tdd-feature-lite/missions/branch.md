---
id: branch
title: Create feature branch off work
summary: Puts the quest on its own feature branch off `work`, derives the feature slug, and posts both to the recon mission board. Orchestrator chore, handled inline.
---

# Branch

You are the orchestrator handling a chore inline. You put the quest on its own feature branch before any other mission runs, and you do nothing else.

## How You Work

You check where you are before you branch. A feature branch cut from the wrong base carries every unmerged change on that base into the quest, and nothing downstream will notice. So you read the current branch first and stop if it is not `work`.

The feature slug is derived from the quest title — lowercase, hyphens, no spaces — and every later mission names transient documents, commit messages, and the branch itself by that slug. You pick it once and publish it.

## Hard Rules

- All work happens on `feat/<feature-slug>` — **never** on `work`
- If the current branch is not `work`, stop and surface to the human rather than branching from wherever you happen to be
- One quest is one branch. Do not merge, do not push, do not touch `work`

## Inputs

- The quest title, from your mission description
- The current git branch

## Steps

Verify the current branch is `work`:

```
git branch --show-current
```

If not on `work`, stop and surface to the human.

Derive the feature slug from the quest title (lowercase, hyphens, no spaces).

Create the feature branch:

```
git checkout -b feat/<feature-slug>
```

Post the branch name and the feature slug to the recon mission board:

```
lore board add <recon-mission-id> "Branch: feat/<feature-slug> | slug: <feature-slug>"
```

## Done Criteria

- `git branch --show-current` reports `feat/<feature-slug>`.
- The branch was cut from `work`, not from another branch.
- The recon mission board carries the branch name and the slug.

Mark done: `lore done <mission-id>`

## Hands On

The feature branch and its slug, to the recon mission.
