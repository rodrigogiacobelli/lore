---
id: ops-publish-pypi
title: Publish to PyPI
summary: Release runbook for cutting a new version of lore-agent-task-manager
  to PyPI. Covers the pre-flight checklist, version bump, changelog finalization,
  git tag, build, upload, and post-publish verification. Git tagging alone does
  not publish — PyPI is a separate step that has been missed in past releases.
related:
- ops-installation
- ops-git-workflow
- decisions-002-package-name
- decisions-010-public-api-stability
---

# Publish to PyPI

The authoritative PyPI package is **`lore-agent-task-manager`**. The PyPI publish is separate from the git release — tagging a version on GitHub does not push a wheel to PyPI. Every release runbook below assumes `develop` is clean and the release has already been merged to `main` per `ops-git-workflow`.


## Pre-flight

1. You are on `main` at the release commit.
2. `pyproject.toml`'s `[project].version` matches the intended release (e.g. `0.3.0`).
3. `CHANGELOG.md` has a dated section for the release — not `## [Unreleased]`.
4. Working tree is clean: `git status` prints nothing.
5. Tests pass: `uv run pytest`.
6. `lore health` is green on this repo's own codex.
7. You have a PyPI account and an API token. Token lives in `~/.pypirc` or is passed via `UV_PUBLISH_TOKEN` / `--token`. If creating a new token, scope it to this project on <https://pypi.org/manage/account/token/>.

## Release runbook

```bash
# 1. Confirm version + changelog are ready
grep '^version' pyproject.toml
grep '^## \[' CHANGELOG.md | head -3

# 2. Clean prior build artifacts so dist/ only contains the new release
rm -rf dist/

# 3. Build sdist + wheel
uv build

# 4. Inspect what will be uploaded
ls -lh dist/
# Expect exactly two files:
#   lore_agent_task_manager-<version>-py3-none-any.whl
#   lore_agent_task_manager-<version>.tar.gz

# 5. (Optional but recommended for a major/minor release) dry-run against TestPyPI
uv publish --publish-url https://test.pypi.org/legacy/
# Then verify in a throwaway venv:
uv tool install --index-url https://test.pypi.org/simple/ \
                --extra-index-url https://pypi.org/simple/ \
                lore-agent-task-manager
lore --version
uv tool uninstall lore-agent-task-manager

# 6. Publish to PyPI for real
uv publish

# 7. Tag the release in git (if not already tagged)
git tag -a v<version> -m "Release <version>"
git push origin v<version>

# 8. Verify the release is visible
#    Browser: https://pypi.org/project/lore-agent-task-manager/<version>/
#    CLI:
uv tool install lore-agent-task-manager --force --reinstall
lore --version
```

The `--extra-index-url https://pypi.org/simple/` in step 5 is required because TestPyPI does not mirror Lore's dependencies (Click, PyYAML, jsonschema) — `uv` resolves them from the real PyPI.

## Back-filling a missed publish

If you discover a git tag (e.g. `v0.3.0`) has no matching PyPI release:

1. Check out the tagged commit: `git checkout v<version>`.
2. Confirm `pyproject.toml` on that commit declares the expected version.
3. Run the runbook from step 2 onward (build → inspect → publish → verify). Skip step 7 — tag already exists.
4. Return to your prior branch: `git checkout -`.

PyPI **does not permit re-uploading** a filename that was already accepted for a given version, so partial or broken uploads must be cleaned up by yanking and bumping to a new patch version — there is no re-push over an existing artifact.

## Troubleshooting

- **`uv publish` says "403 Forbidden"** — token missing, expired, or scoped to the wrong project. Regenerate a project-scoped token and retry.
- **`ls dist/` shows files from two versions** — the prior build was not cleaned. Remove `dist/` and rebuild; `uv publish` would otherwise attempt to upload both and fail on the older one.
- **Install from PyPI still resolves to the old version** — give the CDN 1–2 minutes to propagate, then retry. If still old, double-check the release appears at `https://pypi.org/project/lore-agent-task-manager/#history`.
- **`lore --version` disagrees with the intended release after `uv tool install`** — use `--force --reinstall`; `uv` aggressively caches wheels.
