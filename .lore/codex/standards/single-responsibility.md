---
id: standards-single-responsibility
title: Single Responsibility
stability: stable
summary: A CLI handler does one thing — translate between the terminal and the core. A core function does one thing — business logic. Each module owns exactly one concern. When a unit starts doing two things, one of them belongs somewhere else.
related: ["tech-arch-source-layout", "standards-dry", "standards-separation-of-concerns"]
---

# Single Responsibility

A CLI handler does one thing: translate between the terminal and the core. A core function does one thing: business logic. A validator does one thing: enforce a rule. When a unit starts doing two things, one of them belongs somewhere else.

## Module Responsibilities

Each module in the Lore source tree has exactly one job:

| Module | Single responsibility |
|---|---|
| `cli.py` | CLI I/O translation — parse args, call core, format output |
| `db.py` | Database operations and business rule enforcement |
| `validators.py` | Input validation — one function per rule |
| `paths.py` | `.lore/` path construction helpers |
| `knight.py` | Knight filesystem operations only |
| `watcher.py` | Watcher YAML filesystem operations only |
| `doctrine.py` | Doctrine YAML loading, validation, and storage |
| `codex.py` | Codex document discovery and retrieval |
| `artifact.py` | Artifact file discovery and retrieval |
| `frontmatter.py` | YAML frontmatter parsing |
| `graph.py` | Topological sort of mission graphs |
| `oracle.py` | Report generation |
| `root.py` | Project root detection |
| `models.py` | Public dataclass definitions and `__all__` |

## Rule

If a module is doing two things, split it or move the second concern to the right module.

If a CLI handler is growing complex logic (beyond parse → call → format), that logic belongs in `db.py` or a domain module.

If `db.py` is accumulating filesystem operations, those belong in the relevant entity module (`knight.py`, `doctrine.py`, etc.).

## Violation Pattern

The most common violation is a CLI handler that accumulates helper logic over time — building data structures, computing derived values, making multiple `db.py` calls and merging results. Each of these additions is a second responsibility creeping in. When you notice this, extract the logic into a named function in `db.py` or the appropriate domain module.
