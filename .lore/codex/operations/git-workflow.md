---
id: ops-git-workflow
title: Git Workflow
summary: Branching model with three tiers (main, develop, feature), commit conventions,
  AI vs human merge responsibilities, release process, and hotfix procedure.
related:
- ops-installation
- decisions-010-public-api-stability
---

# Git Workflow

## Branching Model

```
main         ← official releases (tagged, human-only)
└── develop  ← integration branch (human-only merges, cloud-protected)
     ├── feat/...
     ├── fix/...
     └── hotfix/...
```

**`main`** — official releases only. Every commit is a tagged version. Only the human owner decides what ships here. Cloud-protected: no AI agent may merge into `main`.

**`develop`** — integration. No tags. Feature branches are cut from it and squash-merged back into it. Cloud-protected: no AI agent may merge into `develop`.

**Feature branches** (`feat/...`, `fix/...`) — AI territory. Agents branch from `develop`, commit freely (many small commits are fine), and stop there. The human squash-merges the branch back into `develop`.

## Who Merges Where

All merges are performed by humans. AI agents commit freely to feature branches and never merge, never rebase another branch onto theirs, and never push to `develop` or `main`.

| Merge | Who |
|---|---|
| `feat/*` → `develop` | Human (squash, clean commit message) |
| `develop` → `main` | Human |

## Commits

Single-line messages, prefixed with the ticket ID when available:

```
US-30: Context-Aware Quest Inference
```

Without a ticket, use a conventional prefix:

```
fix: crash on empty database
doc: installation guide
chore: update dependencies
feat: mission types
```

Feature branch commits can be granular — the squash-merge collapses them into one commit on `develop`.

## Feature Development

```bash
git checkout develop
git checkout -b feat/my-feature

# ... AI commits freely ...

# Human squash-merges into develop with a clean message:
git checkout develop
git merge --squash feat/my-feature
git commit -m "US-31: My Feature"
git branch -d feat/my-feature
```

One clean commit per feature on `develop`. The human writes every merge commit message.

## Releasing

1. On `develop`, bump the version in `pyproject.toml`.
2. Update `CHANGELOG.md`. Add a `[X.Y.Z] - YYYY-MM-DD` entry. For any release that touches `lore.api` exports, the changelog entry is **required** — it is the human-readable record for Realm's maintainers. Rename `[Unreleased]` to the new version and add a fresh empty `[Unreleased]` above it.
3. Commit both:

```bash
git commit -m "release: v0.2.0"
```

4. Promote to `main` and tag:

```bash
git checkout main
git merge --squash develop
git commit -m "Release v0.2.0"
git tag v0.2.0
git push origin main --tags
```

5. Return to `develop`:

```bash
git checkout develop
```

`main` gets one commit per release. Tags preserve every version permanently.

## Inspecting Past Releases

```bash
git checkout v0.1.0              # exact state of that release
git diff v0.1.0 v0.2.0           # compare two releases
git log v0.1.0..v0.2.0           # what changed between them
```

## Hotfixes

For critical bugs in a released version:

```bash
git checkout -b hotfix/fix-crash v0.1.0   # branch from the tag

# ... fix the bug ...
git commit -m "fix: crash on empty db"

git checkout main
git merge hotfix/fix-crash
git tag v0.1.1
git push origin main --tags

git checkout develop
git merge hotfix/fix-crash

git branch -d hotfix/fix-crash
```

## Summary

| Action | Flow |
|---|---|
| New feature | `feat/*` (AI commits) → squash into `develop` (human) |
| Release | `develop` (human) → squash into `main` → tag `vX.Y.Z` |
| Hotfix | branch from tag → merge into `main` + `develop` |
| Inspect release | `git checkout vX.Y.Z` or `git diff` between tags |
