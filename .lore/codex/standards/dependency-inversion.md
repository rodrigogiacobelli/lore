---
id: standards-dependency-inversion
title: Dependency Inversion
summary: Core logic does not depend on the CLI. The dependency arrow always points
  inward — outer layers (CLI) depend on inner layers (business logic, validators),
  never the reverse. validators.py has zero lore.* imports. db.py does not import
  cli.py.
related:
- tech-overview
- tech-arch-source-layout
- tech-arch-validators
---

# Dependency Inversion

Core logic does not depend on the CLI. The dependency arrow always points inward: outer layers (CLI) depend on inner layers (business logic, validators), never the reverse. Both layers depend on abstractions (function signatures, modules) rather than on each other's implementation details.

## Import Rules

| Module | May import from | Must NOT import from |
|---|---|---|
| `validators.py` | stdlib only | Any `lore.*` module |
| `paths.py` | stdlib only | Any `lore.*` module |
| `db.py` | `validators`, `paths`, `models` | `cli.py` |
| `knight.py`, `doctrine.py`, `codex.py`, `artifact.py`, `watcher.py` | `paths`, `frontmatter`, `validators` (`watcher.py` omits `frontmatter.py` — uses `yaml.safe_load` directly) | `cli.py`, `db.py` |
| `cli.py` | All layers below it | Nothing — it is the outermost layer |

## Rule

If you find yourself importing `cli.py` from any inner module, stop. The dependency is inverted. Find the abstraction that both sides should depend on and introduce it instead.

`validators.py` is the bedrock example: it has zero `lore.*` imports, which means it can be imported by any layer without creating a circular dependency. This property must be preserved.

## Why This Matters

A dependency inversion violation creates circular imports at best, and hidden coupling at worst. When `db.py` imports `cli.py`, you can no longer use `db.py` in a non-CLI context (scripts, tests, Realm) without dragging in Click. The inversion makes the inner layer fragile by coupling it to the outer layer's concerns.

## See Also

See `tech-overview` (Module Layering section) for the full dependency graph of the Lore source tree.
