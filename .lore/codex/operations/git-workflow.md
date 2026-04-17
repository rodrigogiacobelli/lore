---
id: ops-git-workflow
title: Git Workflow
summary: Branching model with four tiers (main, develop, work, feature), commit conventions, AI vs human merge responsibilities, release process, and hotfix procedure.
related:
- ops-installation
- decisions-010-public-api-stability
---

# Git Workflow

## Branching Model

```
main        ← official releases (tagged, human-only)
└── develop ← pre-releases (human-only merges, cloud-protected)
     └── work ← AI buffer branch (human reviews before merging up)
          ├── feat/...
          ├── fix/...
          └── hotfix/...
```

**`main`** — official releases only. Every commit is a tagged version. Only the human owner decides what ships here. Cloud-protected: no AI agent may merge into `main`.

**`develop`** — pre-release integration. No tags. Receives squash-merges from `work` when the human is satisfied. Cloud-protected: no AI agent may merge into `develop`.

**`work`** — AI buffer. Protects `develop` from unreviewed churn. AI agents squash feature branches into `work`. Humans inspect `work`, then promote to `develop`.

**Feature branches** (`feat/...`, `fix/...`) — AI territory. Agents branch from `work`, commit freely (many small commits OK), then squash-merge back into `work`.

## Who Merges Where

All merges are performed by humans. AI agents commit freely to feature branches but never merge.

| Merge | Who |
|---|---|
| `feat/*` → `work` | Human (squash, clean commit message) |
| `work` → `develop` | Human |
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

Feature branch commits can be granular — they will be squashed before entering `work`.

## Feature Development

```bash
git checkout work
git checkout -b feat/my-feature

# ... AI commits freely ...

# Human squashes into work with a clean message:
git checkout work
git merge --squash feat/my-feature
git commit -m "US-31: My Feature"
git branch -d feat/my-feature

# Human promotes to develop when ready:
git checkout develop
git merge --squash work
git commit -m "US-31: My Feature"
```

One clean commit per feature on `develop`. Human writes all merge commit messages.

## Releasing

1. On `develop`, bump the version in `pyproject.toml`.
2. Update `CHANGELOG.md`. Add a `[X.Y.Z] - YYYY-MM-DD` entry. For any release that touches `lore.models` exports, the changelog entry is **required** — it is the human-readable record for Realm's maintainers. Rename `[Unreleased]` to the new version and add a fresh empty `[Unreleased]` above it.
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

5. Return to `develop`, then sync `work`:

```bash
git checkout develop
git checkout work
git merge develop
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

git checkout work
git merge develop

git branch -d hotfix/fix-crash
```

## Summary

| Action | Flow |
|---|---|
| New feature | `feat/*` (AI commits) → squash into `work` (human) → squash into `develop` (human) |
| Release | `develop` (human) → squash into `main` → tag `vX.Y.Z` |
| Hotfix | branch from tag → merge into `main` + `develop` + `work` |
| Inspect release | `git checkout vX.Y.Z` or `git diff` between tags |
