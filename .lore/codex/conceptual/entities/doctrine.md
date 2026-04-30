---
id: conceptual-entities-doctrine
title: Doctrine
summary: What a Doctrine is — a reusable, passive workflow template stored as a paired .yaml and .design.md file. The .design.md is the primary entry point for discovery. Doctrines are read by orchestrators to guide quest and mission creation; they have no execution engine of their own.
related: ["conceptual-entities-quest", "conceptual-entities-mission", "conceptual-entities-knight", "conceptual-entities-glossary", "tech-doctrine-internals", "conceptual-relationships-doctrine--knight", "conceptual-relationships-doctrine--mission", "conceptual-relationships-doctrine--quest"]
---

# Doctrine

A Doctrine is a reusable workflow template stored as two paired files: a `.yaml` for machine-readable steps and a `.design.md` for human-readable design documentation. Doctrines are **passive documents** — there is no template engine, no variable substitution, no execution. An orchestrator reads a Doctrine and uses it as a guide when manually creating the corresponding Quests (lore codex show conceptual-entities-quest) and Missions (lore codex show conceptual-entities-mission) via CLI commands.

A Doctrine describes:

- What steps a workflow typically involves
- Their suggested order and dependencies
- Recommended Knights (lore codex show conceptual-entities-knight) for each step
- Notes about how to execute each step, including references to Artifact (lore codex show conceptual-entities-artifact) IDs where a step produces a template-derived document

The `.design.md` file contains rich human-readable documentation — tables, narratives, phase overviews — and serves as the primary entry point for all discovery. The `.yaml` file contains only machine-readable step data.

Doctrines are stored in the project's `.lore/doctrines/` directory tree. For the technical schema (field names, types, required/optional) see tech-doctrine-internals (lore codex show tech-doctrine-internals). For CLI commands (`lore doctrine show`, `lore doctrine list`, etc.) see tech-cli-commands (lore codex show tech-cli-commands).

## Python API

`Doctrine` and `DoctrineStep` are exported from `lore.models` as typed, immutable dataclasses. Python consumers import them as:

```python
from lore.models import Doctrine, DoctrineStep
```

`Doctrine` fields: `id`, `title`, `summary`, `steps` (a `tuple[DoctrineStep, ...]` — an ordered, immutable sequence). `DoctrineStep` fields: `id`, `title`, `priority`, `type`, `knight`, `notes`, `needs` (a `list[str]`, always present, empty list when the step has no dependencies).

**Construction source:** `Doctrine.from_dict()` accepts the dict returned by `show_doctrine(id, doctrines_dir)`. It does **not** accept `list_doctrines()` output. `list_doctrines()` returns listing dicts containing `"valid"` and `"filename"` keys but no `"steps"` — passing these to `from_dict()` raises `KeyError: 'steps'`. The correct construction pattern is:

```python
from lore.doctrine import show_doctrine
from lore.models import Doctrine

result = show_doctrine("my-workflow", doctrines_dir)
doctrine_obj = Doctrine.from_dict(result)
```

Doctrine and DoctrineStep objects are immutable — attempting to assign to any field raises `FrozenInstanceError`. The `steps` tuple also prevents `append` — mutation attempts raise `AttributeError`.


## Discovery

`lore init` places bundled default doctrines inside `.lore/doctrines/default/`. Each default doctrine is a paired `.yaml` and `.design.md` file. User-created doctrines (added via `lore doctrine new`) land directly in `.lore/doctrines/`. Both `lore doctrine list` and `lore doctrine show` search the full `.lore/doctrines/` directory tree recursively.

**The `.design.md` file is the discovery entry point.** `lore doctrine list` scans for `*.design.md` files and checks for a matching `.yaml` in the same directory. A `.yaml` with no `.design.md` counterpart is completely invisible — it does not appear in any listing or show operation.

`lore doctrine list` returns a single flat sorted list of all valid doctrine pairs found anywhere in the tree. Only complete pairs (both files present and parseable) are returned. Orphaned design files (missing YAML) and YAML-only files are silently skipped.

`lore doctrine show <name>` resolves a doctrine by its filename stem (e.g., `feature-workflow` for `feature-workflow.design.md` + `feature-workflow.yaml`). The search is recursive across the full tree. If either file is missing, the command exits with a "not found" error.

Entity names are expected to be unique across the entire tree.

## Validation Rules

When a Doctrine is read, both files are validated. Validation is performed by the `doctrine.py` module (see tech-doctrine-internals (lore codex show tech-doctrine-internals)).

**YAML schema (`<name>.yaml`):**
- `id` and `steps` are required at the top level.
- `name`, `description`, `title`, and `summary` must NOT appear in the YAML — these are design file fields. Their presence is a validation error.
- The `id` value must match the filename stem exactly.
- `steps` must be a non-empty list.
- Each step must have an `id` and a `title`.
- Step `id` values must be unique within the doctrine.
- `priority`, if present, must be an integer 0–4.
- `type`, if present, must be a string.
- Every entry in a step's `needs` list must reference an existing step `id`.
- `needs` references must not form a cycle.

**Design file schema (`<name>.design.md`):**
- Must have YAML frontmatter.
- `id` is required in frontmatter and must match the filename stem exactly.
- `title` and `summary` are optional.

## Soft-Delete Semantics

Soft-delete for the two-file model is Post-MVP. There is no `lore doctrine delete` CLI command. When soft-delete is implemented, both files (`.yaml` and `.design.md`) will be renamed atomically.

## Example

**`my-workflow.design.md`:**
```markdown
---
id: my-workflow
title: My Workflow
summary: Standard development workflow.
---

# My Workflow

## Purpose

This workflow guides a developer through the standard development lifecycle.

## Phases

| Phase | Steps |
|-------|-------|
| Design | design |
| Implementation | implement |
| Review | review-design |
```

**`my-workflow.yaml`:**
```yaml
id: my-workflow
steps:
  - id: design
    title: Design the feature
    priority: 1
    type: knight
    knight: designer.md
    notes: Produce a design document with acceptance criteria
  - id: review-design
    title: Human review of design
    priority: 1
    type: human
    needs: [design]
  - id: implement
    title: Implement the feature
    priority: 1
    type: knight
    needs: [review-design]
    knight: developer.md
```

## Related

- Quest (lore codex show conceptual-entities-quest) — the live grouping of Missions that an orchestrator creates following a Doctrine
- Mission (lore codex show conceptual-entities-mission) — the individual tasks described by each step in a Doctrine
- Knight (lore codex show conceptual-entities-knight) — the persona files referenced by Doctrine steps
- Artifact (lore codex show conceptual-entities-artifact) — template files referenced by ID in Doctrine step notes
- tech-doctrine-internals (lore codex show tech-doctrine-internals) — validation pipeline and module internals
- tech-cli-commands (lore codex show tech-cli-commands) — `lore doctrine` command reference
