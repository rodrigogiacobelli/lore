---
id: update-changelog
title: Update Changelog
summary: Single-mission doctrine to update CHANGELOG.md after a merge to develop. Triggered by the change-log-updates watcher.
---

# Update Changelog

## Doctrine

| Phase | Mission | Type | Depends On | Input | Output |
|-------|---------|------|------------|-------|--------|
| 0 | update-changelog-entry | agent | — | CHANGELOG.md, git log, pyproject.toml | Updated CHANGELOG.md |

## Missions

- **update-changelog-entry** — Reads commits since the last changelog entry and writes an interpreted, grouped entry. Never copies raw commit messages.

## Artifacts

None.

## Escalation

| Scenario | Orchestrator May | Orchestrator May Not |
|----------|-----------------|----------------------|
| No commits found since last entry | Mark done with no changes — nothing to write | Create a placeholder entry |
| pyproject.toml version is behind the last changelog entry | Block the mission, surface to human — version may need bumping | Write an entry with a lower version number |

## Notes

- Triggered automatically by the `change-log-updates` watcher on merge to develop
- Single mission, no human gate — fully automated
- A version is released only once it carries a git tag; an untagged version bump in `pyproject.toml` is the next version being prepared, not a release
