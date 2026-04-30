---
id: conceptual-entities-knight
title: Knight
summary: What a Knight is — a reusable AI agent persona stored as a markdown file
  that tells a worker agent how to approach work. Covers the what/how separation,
  soft-delete semantics, and how Knight contents are surfaced to workers at runtime.
related:
- conceptual-entities-mission
- conceptual-entities-glossary
- tech-arch-knight-module
- tech-cli-commands
- conceptual-relationships-knight--mission
---

# Knight

A Knight is a reusable AI agent persona — a markdown file containing behavioural instructions that tell a worker agent *how* to approach work. Knights define best practices, coding standards, communication style, or domain-specific guidance.

Knights are always files stored in the project's `.lore/knights/` directory tree. They are never inline text. For CLI commands (`lore knight new`, `lore knight show`, etc.) see tech-cli-commands (lore codex show tech-cli-commands).

## The What / How Separation

The separation between Mission and Knight is:

- **Mission (lore codex show conceptual-entities-mission) description** = the **what**. Detailed requirements, context, acceptance criteria. Written per-task by the orchestrator.
- **Knight** = the **how**. Reusable behavioural guidelines. "Use TDD", "Follow REST conventions", "Write docstrings on all public methods."

A worker agent reads both: the Mission tells it what to build, the Knight tells it how to behave while building it.

A Knight is optional — the Mission description alone should be sufficient to complete the work. The Knight makes execution more consistent and robust across tasks.

## Python API

`Knight` is exported from `lore.models` as a typed, immutable dataclass. Python consumers import it as:

```python
from lore.models import Knight
```

Fields: `name` (the filename stem, e.g., `"architect-consolidator"`) and `content` (the full markdown body passed verbatim to worker agents).

`Knight` has no `from_dict()` or `from_row()` classmethod. There is no `scan_knights()` or `read_knight()` function in any Lore module — knight files are read directly via `path.read_text()` in `cli.py`. Python consumers constructing a `Knight` object must read the file themselves and supply both fields directly:

```python
knight = Knight(name="developer", content=path.read_text())
```

Knight objects are immutable — attempting to assign to any field raises `FrozenInstanceError`.

## Structure

Knights have no required structure — they are free-form markdown. The content is passed verbatim to the worker agent as behavioural context. An empty Knight file is valid but serves no purpose.

Knight names must start with an alphanumeric character and may contain alphanumeric characters, hyphens, and underscores. This naming constraint is enforced on write commands; read commands handle invalid names via file-not-found errors.

## Discovery

`lore init` places bundled default knights inside `.lore/knights/default/`. User-created knights (added via `lore knight new`) land directly in `.lore/knights/`. Both `lore knight list` and `lore knight show` search the full `.lore/knights/` directory tree recursively — they discover knights regardless of which subdirectory the file lives in.

`lore knight list` returns a single flat merged list of all knights found anywhere in the tree. The list is sorted by full filesystem path. No subdirectory annotation or `(default)` label is shown; all knights appear identically regardless of origin.

`lore knight show <name>` resolves a knight by its filename stem (e.g., `developer` for `developer.md`). The search is recursive across the full tree. A name containing a path separator does not resolve — resolution is always by stem only. If no match is found, the command exits with a "not found" error.

Entity names are expected to be unique across the entire tree. If a user places two files with the same stem in different subdirectories, both appear in list output, and show returns the first match by filesystem sort order.

## How Knights Are Used

When a worker agent views a Mission via `lore show`, the Knight file's contents are included inline by default. This means the worker gets everything it needs — Mission details and behavioural guidelines — in a single command.

Knights can be referenced in Doctrines (lore codex show conceptual-entities-doctrine) (so the right persona handles each step automatically) or assigned directly to Missions by the orchestrator at creation time.

## Agent Orientation

An orchestrator agent orienting to a project should use the Codex commands to read documentation rather than navigating the `.lore/codex/` directory directly. The standard orientation pattern is:

1. Run `lore codex list` to see all available documentation.
2. Run `lore codex search <keyword>` to find documents relevant to the task at hand.
3. Run `lore codex show <id>` to retrieve one or more documents in full.

Using the CLI commands instead of direct file reads insulates agents from directory restructuring and ensures the correct document is retrieved by its stable ID.

When a mission requires producing a document from a scaffold, agents should retrieve artifact templates via the artifact commands rather than navigating `.lore/artifacts/` directly:

1. Run `lore artifact list` to see all available template artifacts.
2. Run `lore artifact show <id>` to retrieve the full template body by ID.

This applies to both orchestrator and worker agents. The `AGENTS.md` file generated by `lore init` includes explicit guidance for both roles on using artifact commands.

## Soft-Delete Semantics

Knights are soft-deleted by renaming the file with a `.deleted` suffix. Glob patterns that match `*.md` naturally exclude `.deleted` files, so soft-deleted Knights are invisible to all normal operations. Creating a new Knight with the same name as a soft-deleted one succeeds; the old `.deleted` file is left as-is.

Soft-deleting a Knight does **not** clear the `knight` field on Missions that reference it. Those Missions continue to function normally but display a "knight file not found" warning on `lore show`. This preserves the historical record of what persona was assigned.

## Related

- Mission (lore codex show conceptual-entities-mission) — the task that a Knight's persona guides the execution of
- Doctrine (lore codex show conceptual-entities-doctrine) — templates that reference Knight files for each step
- Artifact (lore codex show conceptual-entities-artifact) — template files referenced by Knights that produce template-derived documents
- tech-cli-commands (lore codex show tech-cli-commands) — `lore knight` command reference
- tech-arch-knight-module (lore codex show tech-arch-knight-module) — Python API for knight filesystem operations (`list_knights`, `find_knight`)
