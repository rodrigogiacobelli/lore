---
id: example-ops-deployment-production
title: Production Deployment
related: []
stability: stable
summary: >
  How to publish a production release: prerequisites, deployment process, verification,
  rollback procedure, and day-2 operations (backup, monitoring).
---

# Production Deployment

## Prerequisites

- Changes have been verified on staging
- `main` branch is up to date with the release commit
- Version number is bumped in `pyproject.toml` and committed
- Required credentials: _list what is needed (PyPI token, GitHub token, etc.)_
- Inform team before releasing: _channel or method (e.g. post in #releases Slack channel)_

## Deployment Process

_Describe how a production release is triggered. Replace the placeholder below._

```bash
_commands to build and publish the production release_
_e.g.:_
git tag v1.2.0
git push origin v1.2.0
_or trigger CI/CD pipeline manually_
```

_If release is automated on tag push, describe the pipeline:_

> Production release is triggered by pushing a version tag (`v*.*.*`) to `main`. The `release` workflow in `.github/workflows/release.yml` builds the wheel, runs the full test suite, then publishes to _PyPI / GitHub Releases / internal repo_.

## Verification

After releasing, verify:

- [ ] Release is available at _distribution location_
- [ ] `pip install taskapp==<version>` installs the new version
- [ ] `taskapp --version` shows the expected version string
- [ ] `taskapp task list` runs without error on a fresh install
- [ ] _Key smoke test for the primary change in this release_
- [ ] Release notes are published: _location (GitHub Release, CHANGELOG.md, etc.)_
- [ ] Notify team that the release is complete: _channel or method_

## Rollback

_Describe how to revert to the previous production release._

```bash
_command or procedure to roll back (e.g. yank PyPI release and re-install previous version)_
```

_State how quickly a rollback can be executed. For a CLI tool distributed via PyPI, rollback typically means yanking the broken release (`pip install taskapp==<previous-version>`) and advising users to pin. There is no downtime because there is no running server._

## Day-2 Operations

### Backup

_A local CLI tool stores data in the user's home directory. No centralised backup is needed unless a shared database is in use._

| Task | Command |
|------|---------|
| Manual database backup | `cp ~/.taskapp/taskapp.db ~/.taskapp/taskapp.db.bak.$(date +%Y%m%d)` |
| _automated backup procedure_ | _command or cron entry_ |

### Monitoring

_Describe what to monitor post-release._

| Task | Command or method |
|------|-----------------|
| Check for error reports | _e.g. GitHub Issues, Sentry, support channel_ |
| Verify no breaking changes in the wild | _e.g. monitor download counts on PyPI, check community forum_ |
| _additional monitoring step_ | _command_ |

### Version Pinning Notice

If a release is found to be broken after publication, consider yanking it from the package index:

```bash
_command to yank a release (e.g. `uv publish --yank v1.2.0 --yank-message "breaks task done on Windows"`)_
```

Yanked releases remain installable by explicit version pin but are excluded from default `pip install taskapp`.
