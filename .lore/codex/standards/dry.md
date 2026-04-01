---
id: standards-dry
title: DRY — Don't Repeat Yourself
stability: stable
summary: Every piece of logic has one authoritative home. If the same rule, check, or transformation appears in more than one place, one of them is wrong. Covers the canonical module homes for validation, path construction, YAML parsing, and graph algorithms.
related: ["tech-arch-source-layout", "tech-arch-validators", "tech-arch-frontmatter", "tech-arch-graph"]
---

# DRY — Don't Repeat Yourself

Every piece of logic has one authoritative home. If the same rule, check, or transformation appears in more than one place, one of them is wrong. The fix is always to find the right home and have all other call sites delegate to it — never to keep both copies in sync.

## Canonical Module Homes

| Logic type | Authoritative home | Module |
|---|---|---|
| All input validation | `validators.py` | `lore.validators` |
| `.lore/` path construction | `paths.py` | `lore.paths` |
| YAML frontmatter parsing | `frontmatter.py` | `lore.frontmatter` |
| Topological sort of missions | `graph.py` | `lore.graph` |
| Knight filesystem operations | `knight.py` | `lore.knight` |
| Doctrine loading and validation | `doctrine.py` | `lore.doctrine` |
| Watcher filesystem operations | `watcher.py` | `lore.watcher` |

## Rule

When you need validation, import from `lore.validators`. When you need a `.lore/` path, import from `lore.paths`. Never duplicate the logic inline at the call site.

If the logic you need does not have a home yet, create the home first — add it to the correct module — then call it from the new location. Never add a second copy.

## Violation Pattern

The most common DRY violation in this codebase is validation logic duplicated between `cli.py` and `db.py`. A validator belongs in `validators.py` and is called by both layers. It does not live in either layer.

## See Also

See `tech-arch-source-layout` for the full module inventory and responsibility boundaries. See `decisions-011-api-parity-with-cli` for why both layers must enforce the same rules.
