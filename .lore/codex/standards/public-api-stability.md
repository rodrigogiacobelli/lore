---
id: standards-public-api-stability
title: Public API Stability
stability: stable
summary: >
  Everything in lore.models.__all__ is the public API of lore-agent-task-manager.
  Semver policy for pre-1.0: adding names or fields → minor bump; removals,
  renames, or type changes → major bump or explicit breaking-change notice in
  CHANGELOG.md.
related: ["tech-api-surface", "decisions-011-api-parity-with-cli"]
---

# Public API Stability

## Public API Definition

**The public API of `lore-agent-task-manager` is the set of names listed in
`lore.models.__all__`.**

As of the `0.3.0` release, `__all__` contains:

```python
__all__ = [
    "QuestStatus",
    "MissionStatus",
    "DependencyType",
    "Quest",
    "Mission",
    "Dependency",
    "BoardMessage",
    "DoctrineStep",
    "Doctrine",
    "Artifact",
    "CodexDocument",
    "Knight",
    "DoctrineListEntry",
    "Watcher",
]
```

Names not listed in `__all__`, internal modules (`db.py`, `cli.py`, `doctrine.py`,
`codex.py`, `artifact.py`, `priority.py`, etc.), and the CLI entry point (`lore.cli:main`)
are **not part of the public API**. They may change without notice between any two releases.

## Semver Policy (Pre-1.0)

The package is pre-1.0. Under standard semver, `0.x` releases allow breaking changes in
minor version bumps. This project applies a more conservative policy:

| Change type | Required version bump |
|-------------|----------------------|
| Adding a new name to `lore.models.__all__` | Minor bump (e.g., `0.3.0` → `0.4.0`) |
| Adding a new field to an existing exported dataclass | Minor bump |
| Removing a name from `lore.models.__all__` | **Major bump** OR explicit breaking-change notice in `CHANGELOG.md` |
| Renaming a name in `lore.models.__all__` | **Major bump** OR explicit breaking-change notice |
| Changing the type of an existing exported field | **Major bump** OR explicit breaking-change notice |
| Bug fix with no API surface change | Patch bump (e.g., `0.3.0` → `0.3.1`) |

"Explicit breaking-change notice" means a `BREAKING CHANGE:` section in `CHANGELOG.md`
under the release entry, plus a note in release tags and any communication channels used
for the Camelot system.

## CHANGELOG.md

A `CHANGELOG.md` at the repository root (Keep a Changelog format) is the canonical record
of public API changes. Every release that touches names exported from `lore.models` must
include a changelog entry.

Changelog format:

```markdown
## [0.3.0] - 2026-MM-DD

### Added
- `lore.models` module: Quest, Mission, ... (full list of new names)
- `py.typed` PEP 561 marker

### Changed
- (any changed API surface)

### Removed
- (any removed names — BREAKING if without major bump)
```

## How Realm Should Pin

Realm must specify a minimum version and an upper bound when declaring its dependency:

```toml
# In Realm's pyproject.toml or requirements file:
lore-agent-task-manager>=0.3.0,<1.0
```

This range is safe **as long as this semver policy holds**: minor version bumps are
additive only; removals and renames require either a major bump or an explicit
breaking-change notice.

Realm must **not** pin to an exact version (e.g., `==0.3.0`).

## Transition to 1.0.0

The package will transition to `1.0.0` when:

1. The public API (names in `lore.models.__all__`) is considered stable for production
   external consumers beyond the Camelot system.
2. The Camelot team explicitly decides that the API contract is ready for full semver
   major-version semantics.

The 1.0.0 transition is a deliberate decision, not a scheduled event. At that point,
standard semver applies in full: breaking changes require a major version bump with no
exceptions.

## Rules for Contributors

- `lore/models.py` must maintain `__all__` as the authoritative list of exported names.
  Any addition to or removal from `__all__` triggers the semver policy above.
- Every release that changes the public API must include a `CHANGELOG.md` entry.
- Realm's dependency declaration must use a `>=min,<1.0` range, not an exact pin.
- Adding a new type to `lore.models` requires updating `__all__` and the changelog.
  `__all__` is the contract, not mere importability.
- Internal refactors that do not touch `lore.models.__all__` or the field shapes of
  exported types are free to proceed without a semver bump or changelog entry.
