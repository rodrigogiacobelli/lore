---
id: decisions-010-public-api-stability
title: 'ADR-010: lore.models.__all__ is the stable public API contract'
summary: 'ADR establishing that lore.models.__all__ is the sole public API surface
  of lore-agent-task-manager. Everything not listed there is internal and may change
  without notice. Pre-1.0 semver policy: additions are minor bumps; removals and renames
  require a major bump or explicit breaking-change notice in CHANGELOG.md.

  '
related:
- standards-public-api-stability
- decisions-011-api-parity-with-cli
- tech-api-surface
---

# ADR-010: lore.models.__all__ is the stable public API contract

**Status:** ACCEPTED

## Context

Lore has two consumers: human operators via the CLI, and Realm via Python import. The CLI
is versioned through the package itself; Realm's Python import surface needed an explicit,
stable contract so that Realm could pin a version range and trust it.

Without a defined boundary, any module in `lore` could be imported by Realm, making every
refactor a potential breaking change. This created friction for both development (fear of
breaking Realm) and release management (no clear signal for version bumps).

## Decision

**The public API of `lore-agent-task-manager` is the set of names listed in
`lore.models.__all__`.**

- All exported types are frozen `@dataclass` classes or `StrEnum` subclasses.
- Everything not in `__all__` — including internal modules (`db.py`, `cli.py`,
  `doctrine.py`, `codex.py`, etc.) and the CLI entry point — is internal and may
  change without notice between any two releases.
- Realm imports exclusively from `lore.models`. Any other import is a bug in Realm.

## Semver Policy (Pre-1.0)

| Change type | Required version bump |
|-------------|----------------------|
| Adding a name to `__all__` | Minor bump |
| Adding a field to an exported dataclass | Minor bump |
| Removing a name from `__all__` | Major bump or explicit breaking-change notice |
| Renaming an exported name | Major bump or explicit breaking-change notice |
| Changing a field type | Major bump or explicit breaking-change notice |
| Bug fix with no API surface change | Patch bump |

## Consequences

- Realm can safely declare `lore-agent-task-manager>=0.x.0,<1.0` and trust that
  minor bumps are additive-only.
- Contributors must update `CHANGELOG.md` and `__all__` together whenever the
  public API changes.
- Internal refactors that do not touch `lore.models.__all__` or exported field
  shapes require no semver bump and no changelog entry.
