---
id: update-changelog
title: Update Changelog
summary: Single-step doctrine to update CHANGELOG.md after a merge to develop. Triggered by the change-log-updates watcher.
---

# Update Changelog

## Doctrine

| Phase | Step | Type | Knight | Depends On | Input | Output |
|-------|------|------|--------|------------|-------|--------|
| 0 | Update Changelog | knight | changelog-scribe | — | CHANGELOG.md, git log, pyproject.toml | Updated CHANGELOG.md |

## Artifacts

None.

## Knights

- **changelog-scribe** — Reads commits since the last changelog entry and writes an interpreted, grouped entry. Never copies raw commit messages.

## Escalation

| Scenario | Orchestrator May | Orchestrator May Not |
|----------|-----------------|----------------------|
| No commits found since last entry | Mark done with no changes — nothing to write | Create a placeholder entry |
| pyproject.toml version is behind the last changelog entry | Block the mission, surface to human — version may need bumping | Write an entry with a lower version number |

## Notes

- Triggered automatically by the `change-log-updates` watcher on merge to develop
- Single step, no human gate — fully automated
- Version authority is pyproject.toml, not git tags
