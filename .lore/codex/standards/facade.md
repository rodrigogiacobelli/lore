---
id: standards-facade
title: Facade
summary: The public surface of a layer is a facade over its internals — simple, stable,
  and narrow. lore.api.__all__ is the stable public facade for external consumers.
  Every other module under lore is internal and may change freely without breaking
  the facade.
related:
- decisions-010-public-api-stability
- standards-public-api-stability
- tech-arch-api-facade
- ref-lore_api-core
---

# Facade

The public surface of a layer is a facade over its internals. It should be simple, stable, and narrow. Complexity lives behind it. A caller should be able to use the facade without knowing how the internals work, and the internals should be free to change without breaking the facade.

## The Public Facade

`lore.api.__all__` defines the public API surface — the complete set of names that external consumers (Realm, Citadel, the future Lore Server, third-party scripts) can safely depend on. Any name not in `__all__` is an internal implementation detail.

`lore.api` is a pure re-export module: zero `def`, zero `class`. Every name in `__all__` is imported from an internal module and re-exported verbatim. See `tech-arch-api-facade` for the mechanics; see `standards-public-api-stability` for the current contents of `__all__` and the semver policy.

## Rule

If a name is in `lore.api.__all__`, it is public. Renaming, removing, or changing its interface requires a version bump (see `decisions-010-public-api-stability`).

If a name is not in `lore.api.__all__`, it is internal. It may be refactored, renamed, or removed freely without a version bump — including renaming or splitting the module it currently lives in.

Never expose internal implementation details through `lore.api.__all__`. If a caller needs something, add a clean interface, populate the validators / operational layer behind the facade with it, and re-export the name from `lore.api` — never give callers direct access to a submodule.

## Internal Modules

Every module under `lore` other than `lore.api` is internal. They are not re-exported as importable submodules through `lore.api.__all__` and must not be imported by external consumers:

- `lore.cli` — Click handlers and entry point
- `lore.db` — database functions
- `lore.models` — internal typed-record index (its dataclasses are re-exported through `lore.api`; the module itself is not)
- `lore.validators` — validation utilities (functions re-exported individually through `lore.api`)
- `lore.paths` — `.lore/` path helpers
- `lore.graph` — graph algorithms
- `lore.priority` — ready-queue logic (`get_ready_missions` re-exported)
- `lore.knight` / `lore.doctrine` / `lore.artifact` / `lore.watcher` — file-backed entity operations (CRUD callables re-exported individually)
- `lore.codex` — codex scanning, retrieval, search, traversal (operations re-exported individually)
- `lore.glossary` — glossary loading and matcher
- `lore.impacts` — codex↔code surfacing primitive
- `lore.health` — `lore health` audit implementation
- `lore.schemas` — JSON Schema loader + entity validators
- `lore.frontmatter` — shared frontmatter parsing
- `lore.config` — TOML config loader
- `lore.init` / `lore.oracle` — `lore init` and report generation
- `lore.ids` / `lore.root` / `lore.migrations.*` — supporting infrastructure

Lore's own `cli.py` is also a consumer of `lore.api`. It reaches its internal helpers through leading-underscore namespace aliases re-exported from `api.py` (e.g. `lore.api._paths`, `lore.api._knight`, `lore.api._validate_frontmatter`). The underscore prefix keeps these out of `dir(lore.api)` and outside the public surface — they exist so the CLI does not have to breach the facade boundary it tells external consumers to honour.

## Why This Matters

Without a clear facade, every internal refactor risks breaking external consumers. With a clean `lore.api.__all__`, the internal structure of `lore` can evolve freely as long as the facade module keeps re-exporting the same names. Splitting `db.py`, renaming `codex.py`, moving a helper from one module to another — none of these require a semver bump if `lore.api.__all__` is unchanged.
