---
id: ops-git-workflow
title: Git Workflow
summary: Branching model, commit conventions (US-N ticket format and conventional prefixes), feature development workflow, release process, and hotfix procedure for the Lore repository.
related: ["ops-installation", "decisions-010"]
stability: stable
---

# Git Workflow

## Branching Model

```
main        ← releases only (tagged)
└── develop ← integration branch
     ├── feat/...
     ├── fix/...
     └── hotfix/...
```

**`main`** always equals the latest release. Every commit on `main` is a tagged version.

**`develop`** is the working branch. All feature work merges here first. When stable and tested, `develop` promotes to `main` as a release.

**Feature branches** are short-lived. They branch from `develop` and squash-merge back into it.

> Note: the repository also uses short-lived `docs/` branches for documentation-only changes (e.g. `docs/codex-structure`). These follow the same squash-merge convention as feature branches.

## Commits

Single-line messages, prefixed with the ticket ID:

```
US-30: Context-Aware Quest Inference
```

For changes without a ticket, use a conventional prefix:

```
fix: crash on empty database
doc: installation guide
chore: update dependencies
feat: mission types
```

## Feature Development

```bash
git checkout develop
git checkout -b feat/my-feature

# ... work, commit ...

git checkout develop
git merge --squash feat/my-feature
git commit -m "US-31: My Feature"
git branch -d feat/my-feature
```

Always squash. One commit per feature on `develop`.

## Releasing

1. Bump the version in `pyproject.toml` on `develop`.
2. Update `CHANGELOG.md` on `develop`. Add a `[X.Y.Z] - YYYY-MM-DD` entry listing all
   additions, changes, and removals. For any release that touches `lore.models` exports,
   the changelog entry is **required** — it is the human-readable record for Realm's
   maintainers. Rename the `[Unreleased]` section to the new version and add a fresh
   empty `[Unreleased]` section above it.
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
git merge hotfix/fix-crash                 # bring fix into develop too
git branch -d hotfix/fix-crash
```

## Summary

| Action | Flow |
|---|---|
| New feature | `feat/*` → squash into `develop` |
| Release | `develop` → squash into `main` → tag `vX.Y.Z` |
| Hotfix | branch from tag → merge into `main` + `develop` |
| Inspect release | `git checkout vX.Y.Z` or `git diff` between tags |
