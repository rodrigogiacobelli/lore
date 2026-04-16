---
id: example-ops-deployment
title: Deployment Overview
summary: Deployment architecture, environment inventory, technology choices, and entry
  point for all environment-specific deployment documentation.
---

# Deployment Overview

## Environments

| Environment | Purpose | Location | Branch |
|-------------|---------|----------|--------|
| Development | Local development and testing | Developer machine | any |
| Staging | Pre-release verification | _staging location_ | `develop` |
| Production | Live system used by real users | _production location_ | `main` |

_Fill in the Location column with hostnames, URLs, or infrastructure references. Remove Staging if the project has no staging environment._

## Deployment Technology

_Describe what tooling is used to build and ship the application._

| Layer | Technology | Notes |
|-------|-----------|-------|
| Packaging | _e.g. uv build / pip wheel / PyInstaller_ | _how the CLI binary or package is built_ |
| Distribution | _e.g. PyPI / GitHub Releases / Homebrew tap / internal package repo_ | _how users install the tool_ |
| CI/CD | _e.g. GitHub Actions / GitLab CI_ | _pipeline file location_ |
| Version management | _e.g. manual tag / bumpversion / semantic-release_ | |

_This is a CLI tool — there is no hosting layer. If a web API is added later, extend this table with containerisation, orchestration, and hosting rows._

## Architecture Diagram

_High-level diagram of what runs where in production. For a CLI tool this is typically the distribution pipeline rather than a runtime architecture._

```
_Add diagram here (Mermaid or ASCII). Example for a CLI tool:_

Developer machine
  → uv build → dist/taskapp-*.whl
    → CI/CD pipeline
        → GitHub Release (attached wheel)
        → PyPI publish (optional)
            → End user: pip install taskapp / uv tool install taskapp
```

## Environment-Specific Guides

| Guide | Description |
|-------|-------------|
| `lore codex show example-ops-deployment-dev` | Set up a local development environment from scratch |
| `lore codex show example-ops-deployment-staging` | Deploy and verify a staging or pre-release build |
| `lore codex show example-ops-deployment-production` | Publish a production release, verify, and roll back |
