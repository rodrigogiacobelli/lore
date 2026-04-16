---
id: standards-facade
title: Facade
summary: The public surface of a layer is a facade over its internals — simple, stable,
  and narrow. lore.models.__all__ is the stable public surface for external consumers.
  Internal modules may change freely without breaking the facade.
related:
- decisions-010-public-api-stability
- tech-api-surface
---

# Facade

The public surface of a layer is a facade over its internals. It should be simple, stable, and narrow. Complexity lives behind it. A caller should be able to use the facade without knowing how the internals work, and the internals should be free to change without breaking the facade.

## The Public Facade

`lore.models.__all__` defines the public API surface — the complete set of names that external consumers (Realm, scripts) can safely depend on. Any name not in `__all__` is an internal implementation detail.

Current public surface: `Quest`, `Mission`, `BoardMessage`, `Artifact`, `Doctrine`, `Knight`, `Watcher`, and their associated status enums. See `tech-api-surface` for the full matrix.

## Rule

If a name is in `__all__`, it is public. Renaming, removing, or changing its interface requires a version bump (see `decisions-010-public-api-stability`).

If a name is not in `__all__`, it is internal. It may be refactored, renamed, or removed freely without a version bump.

Never expose internal implementation details through `__all__`. If a caller needs something, add a clean interface, not direct access to the internals.

## Internal Modules

The following modules are internal — they are not exported through `__all__` and must not be imported by external consumers:

- `lore.db` — database functions (called by Realm only through the models layer)
- `lore.cli` — Click handlers
- `lore.validators` — validation utilities
- `lore.paths` — path helpers
- `lore.graph` — graph algorithms

## Why This Matters

Without a clear facade, every internal refactor risks breaking external consumers. With a clean `__all__`, the internal structure of `lore` can evolve freely as long as the models layer stays stable.
