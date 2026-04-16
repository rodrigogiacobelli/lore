---
id: example-ops-git
title: Git Workflow
summary: Branching model, commit conventions, PR process, review process, merge strategy,
  and release process for this project. AI agents must follow these conventions on
  every commit and every PR.
---

# Git Workflow

## Branching Model

_Describe the branching strategy. Examples: Git Flow, trunk-based, GitHub Flow._

| Branch | Purpose | Created from | Merges into |
|--------|---------|-------------|-------------|
| `main` | Production-ready code | — | — |
| `develop` | Integration branch | `main` | `main` |
| `feat/{name}` | New features | `develop` | `develop` |
| `fix/{name}` | Bug fixes | `develop` | `develop` |
| `hotfix/{name}` | Urgent production fixes | `main` | `main` + `develop` |

_Adjust the table to match this project's actual branching strategy. Remove branches that are not used. Add branches that are not listed._

## Commit Conventions

_Describe the commit message format. The example below uses Conventional Commits._

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

**Types:**

| Type | When to use |
|------|------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or correcting tests |
| `chore` | Build process, tooling, dependencies |

**Rules:**
- Summary line ≤ 72 characters
- Use imperative mood: "add command" not "added command"
- Reference issue or user story in footer when applicable: `Refs: US-042`

_Replace or extend the type list to match this project's conventions._

## Pull Requests

- One PR per feature or fix
- PR title follows the same convention as commit messages
- Description must include: what changed, why, and how to test
- Link to the relevant user story or spec if applicable

_Add any project-specific PR requirements: template link, required labels, etc._

## Review Process

_Describe who reviews, what reviewers check, and what constitutes approval._

- Minimum reviewers required: _N_
- Reviewer checks: correctness, test coverage, documentation updated if behaviour changed
- Blocking comments must be resolved before merge

_Name specific reviewers or teams if applicable. Link to a CODEOWNERS file if one exists._

## Merge Strategy

_Pick one strategy and state why._

- Strategy: _squash merge_ (keeps `develop` history linear)
- Delete branch after merge: _yes / no_

_Options: squash merge, rebase, merge commit. Note the trade-offs for your team._

## Release Process

_How a release is cut. Tags, changelogs, version bumps._

1. Merge `develop` → `main`
2. Tag `main` with version: `git tag v{major}.{minor}.{patch}`
3. Push tag: `git push origin v{major}.{minor}.{patch}`
4. _Any additional steps: changelog generation, PyPI publish, GitHub Release creation, etc._

_If releases are automated via CI/CD, describe that here instead._
