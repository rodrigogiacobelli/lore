---
id: example-ops-deployment-staging
title: Staging Deployment
summary: 'How to deploy a pre-release build to the staging environment: prerequisites,
  deployment process, verification steps, and rollback procedure.'
---

# Staging Deployment

Staging mirrors the production release process and is used to verify a build before it is published to real users.

## When to Deploy to Staging

- After a feature branch merges into `develop`
- Before cutting a production release
- When testing changes to the packaging or distribution pipeline
- When testing infrastructure or configuration changes

## Prerequisites

- Access to the staging deployment target (_describe: CI/CD system, package repository, test machine, etc._)
- Required credentials: _list what is needed (API token, SSH key, etc.)_
- Latest `develop` branch checked out and CI passing

## Deployment Process

_Describe how a staging deployment is triggered. Replace the placeholder below with actual commands or CI/CD trigger description._

```bash
_commands to build and publish a pre-release (e.g. test PyPI upload, GitHub pre-release, internal repo push)_
```

_If staging deployment is triggered automatically by CI/CD on merge to `develop`, describe the pipeline instead:_

> Staging deployment is automated. Merging a PR into `develop` triggers the `staging` workflow in `.github/workflows/staging.yml`. The workflow builds the wheel, runs integration tests against the staging database, and publishes the pre-release to _location_.

## Verification

After deploying, verify:

- [ ] Pre-release build is reachable at _staging location or package index_
- [ ] `pip install --pre taskapp` (or equivalent) installs the new version
- [ ] `taskapp --version` shows the expected version string
- [ ] `taskapp task list` runs without error against a fresh staging database
- [ ] _Key smoke test for the feature being released_
- [ ] No errors in logs: `_command to check logs_`

## Rollback

_Describe how to revert to the previous staging build._

```bash
_command or procedure to roll back (e.g. re-deploy previous git tag, re-publish previous wheel)_
```
