---
id: decisions-010-public-api-stability
title: 'ADR-010: lore.api.__all__ is the stable public API contract'
summary: 'ADR establishing that lore.api.__all__ is the sole public API surface of
  lore-agent-task-manager. lore.api is a facade module that re-exports names selected
  from internal modules (lore.models, lore.db, lore.validators, lore.codex, ...). Names
  not re-exported through lore.api are internal and may change without notice. Pre-1.0
  semver policy: additions are minor bumps; removals and renames require a major bump
  or explicit breaking-change notice in CHANGELOG.md.

  '
binds:
- src/lore/api.py
- src/lore/models.py
- src/lore/__init__.py
related:
- standards-public-api-stability
- decisions-011-api-parity-with-cli
- ref-lore_api-core
---

# ADR-010: lore.api.__all__ is the stable public API contract

**Status:** ACCEPTED

## Context

Lore has two consumers today: human operators via the CLI, and Realm via Python import. A future third consumer — Lore Server — will expose the same surface over HTTP/MCP. All three must call the same underlying functions: no consumer may re-implement logic, and no consumer may be given a surface the others don't trust.

Without a defined boundary, any module under `lore` could be imported externally, making every refactor a potential breaking change. The first attempt at this boundary placed the public contract at `lore.models.__all__` — limited to frozen dataclasses and enums. That choice does not match reality: the operational surface (`create_quest`, `claim_mission`, `read_document`, `scan_glossary`, …) lives across `lore.db`, `lore.codex`, `lore.validators`, `lore.knight`, `lore.doctrine`, `lore.artifact`, `lore.watcher`, `lore.glossary`, `lore.impacts`, `lore.priority`, and `lore.health`. Consumers reach into those modules directly today. The result: a "models-only" contract that nobody actually honours, and an implicit promise that every internal module's name and layout is stable.

A separate audit (ADR-011) established that callable behaviour must be identical between CLI and direct Python calls. Reconciling that with ADR-010's original scope requires a single, explicit facade for the callable surface — not a spread of internal modules.

## Decision

**The public API of `lore-agent-task-manager` is the set of names listed in `lore.api.__all__`.**

`lore.api` is a facade module. It contains no business logic — only re-exports of names selected from internal modules:

- Dataclasses and enums sourced from `lore.models`.
- Callables sourced from `lore.db`, `lore.validators`, `lore.codex`, `lore.knight`, `lore.doctrine`, `lore.artifact`, `lore.watcher`, `lore.glossary`, `lore.impacts`, `lore.priority`, and `lore.health`.

Rules:

- All exported types are frozen `@dataclass` classes or `StrEnum` subclasses.
- All exported callables conform to ADR-011 — self-contained, validated, behaviourally equivalent to the CLI.
- Internal modules (`lore.db`, `lore.cli`, `lore.codex`, `lore.models`, …) are not part of the public API. They may be renamed, split, or merged between any two releases as long as `lore.api.__all__` is preserved.
- External consumers import exclusively from `lore.api`. Any other import is a bug in the consumer.
- `lore.models.__all__` continues to exist for internal use as the dataclass/enum index, but it is no longer the contract. Consumers must not import from `lore.models` directly.

## Semver Policy (Pre-1.0)

| Change type | Required version bump |
|-------------|----------------------|
| Adding a name to `lore.api.__all__` | Minor bump |
| Adding a field to an exported dataclass | Minor bump |
| Adding a keyword argument with a default to an exported function | Minor bump |
| Removing a name from `lore.api.__all__` | Major bump or explicit breaking-change notice |
| Renaming an exported name | Major bump or explicit breaking-change notice |
| Changing a field type | Major bump or explicit breaking-change notice |
| Changing a positional parameter list or a return shape | Major bump or explicit breaking-change notice |
| Bug fix with no API surface change | Patch bump |

## Consequences

- Consumers can declare `lore-agent-task-manager>=0.x.0,<1.0` and trust that minor bumps are additive-only against `lore.api`.
- Contributors update `CHANGELOG.md` and `lore.api.__all__` together whenever the public API changes.
- Internal refactors that do not touch `lore.api.__all__` or exported shapes require no semver bump and no changelog entry — this includes renaming, splitting, or merging modules below the facade.
- The CLI, the future Lore Server, and Realm all call `lore.api`. No consumer reaches into internal modules.
- ADR-011 governs the behaviour and parity rules for callables routed through `lore.api`.

## History

- Originally accepted with `lore.models.__all__` (frozen dataclasses + enums) as the public surface.
- Amended to use `lore.api.__all__` as the public facade after audit revealed that the operational surface spans multiple internal modules and that consumers were already reaching into them. The facade decouples the public contract from internal module layout and gives the project a single, enforceable boundary for CLI, Realm, and Lore Server.
