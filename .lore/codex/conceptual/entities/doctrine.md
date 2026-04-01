---
id: conceptual-entities-doctrine
title: Doctrine
summary: What a Doctrine is — a reusable, passive workflow template written in YAML that describes the steps, ordering, and suggested knights for a body of work. Doctrines are read by orchestrators to guide quest and mission creation; they have no execution engine of their own.
related: ["conceptual-entities-quest", "conceptual-entities-mission", "conceptual-entities-knight", "tech-doctrine-internals"]
stability: stable
---

# Doctrine

A Doctrine is a reusable workflow template written in YAML. Doctrines are **passive documents** — there is no template engine, no variable substitution, no execution. An orchestrator reads a Doctrine and uses it as a guide when manually creating the corresponding Quests (lore codex show conceptual-entities-quest) and Missions (lore codex show conceptual-entities-mission) via CLI commands.

A Doctrine describes:

- What steps a workflow typically involves
- Their suggested order and dependencies
- Recommended Knights (lore codex show conceptual-entities-knight) for each step
- Notes about how to execute each step, including references to Artifact (lore codex show conceptual-entities-artifact) IDs where a step produces a template-derived document

Doctrines are stored in the project's `.lore/doctrines/` directory tree. For the technical schema (field names, types, required/optional) see tech-db-schema (lore codex show tech-db-schema). For CLI commands (`lore doctrine show`, `lore doctrine list`, etc.) see tech-cli-commands (lore codex show tech-cli-commands).

## Python API

`Doctrine` and `DoctrineStep` are exported from `lore.models` as typed, immutable dataclasses. Python consumers import them as:

```python
from lore.models import Doctrine, DoctrineStep
```

`Doctrine` fields: `name`, `description`, `steps` (a `tuple[DoctrineStep, ...]` — an ordered, immutable sequence). `DoctrineStep` fields: `id`, `title`, `priority`, `type`, `knight`, `notes`, `needs` (a `list[str]`, always present, empty list when the step has no dependencies).

**Construction source:** `Doctrine.from_dict()` accepts the dict returned by `load_doctrine(filepath)` — the normalised doctrine dict. It does **not** accept `list_doctrines()` output. `list_doctrines()` returns validation-status dicts containing `"valid"`, `"errors"`, and `"filename"` keys — passing these to `from_dict()` raises `KeyError: 'steps'`. The correct construction pattern is:

```python
from lore.doctrine import load_doctrine
from lore.models import Doctrine

normalized = load_doctrine(path)
doctrine_obj = Doctrine.from_dict(normalized)
```

Doctrine and DoctrineStep objects are immutable — attempting to assign to any field raises `FrozenInstanceError`. The `steps` tuple also prevents `append` — mutation attempts raise `AttributeError`.


## Discovery

`lore init` places bundled default doctrines inside `.lore/doctrines/default/`. User-created doctrines (added via `lore doctrine new`) land directly in `.lore/doctrines/`. Both `lore doctrine list` and `lore doctrine show` search the full `.lore/doctrines/` directory tree recursively — they discover doctrines regardless of which subdirectory the file lives in.

`lore doctrine list` returns a single flat merged list of all doctrines found anywhere in the tree. The list is sorted by full filesystem path. No subdirectory annotation or `(default)` label is shown; all doctrines appear identically regardless of origin. Doctrines that fail validation still appear in the list, marked with a warning.

`lore doctrine show <name>` resolves a doctrine by its filename stem (e.g., `feature-workflow` for `feature-workflow.yaml`). The search is recursive across the full tree. A name containing a path separator does not resolve — resolution is always by stem only. If no match is found, the command exits with a "not found" error. If the file is found but fails validation, the specific error is printed and the command exits with code 1.

Entity names are expected to be unique across the entire tree. If a user places two files with the same stem in different subdirectories, both appear in list output, and show returns the first match by filesystem sort order.

## Validation Rules

When a Doctrine is read, it is validated before use. Validation is performed by the `doctrine.py` module (see tech-doctrine-internals (lore codex show tech-doctrine-internals)). The rules:

- `name`, `description`, and `steps` are required at the top level.
- `steps` must be a non-empty list.
- Each step must have an `id` and a `title`.
- Step `id` values must be unique within the doctrine.
- `priority`, if present, must be an integer 0–4.
- `type`, if present, must be a string. Any string value is accepted; there is no fixed vocabulary. A non-string value (for example a number or boolean) causes validation to fail.
- Every entry in a step's `needs` list must reference an existing step `id` within the same doctrine.
- `needs` references must not form a cycle (same depth-first algorithm used for mission dependencies).
- The `name` field in the YAML must match the filename (without `.yaml` extension).
- Unknown top-level and step-level keys are silently ignored (forward-compatible).

If validation fails, `lore doctrine show` prints the specific error and exits with code 1. Doctrines with validation errors are still listed by `lore doctrine list` but are marked with a warning.

## Soft-Delete Semantics

Doctrines are soft-deleted by renaming the YAML file with a `.deleted` suffix. Glob patterns that match `*.yaml` naturally exclude `.deleted` files, so soft-deleted doctrines are invisible to all normal operations. Creating a new doctrine with the same name as a soft-deleted one succeeds; the old `.deleted` file is left as-is.

## Example

```yaml
name: feature-workflow
description: Standard feature development workflow
steps:
  - id: design
    title: Design the feature
    priority: 1
    type: worker
    knight: designer.md
    notes: Produce a design document with acceptance criteria
  - id: review-design
    title: Human review of design
    priority: 1
    type: approval
    needs: [design]
    notes: Pause for human to review and approve the design
  - id: implement
    title: Implement the feature
    priority: 1
    type: worker
    needs: [review-design]
    knight: developer.md
    notes: Write the code following the design document
  - id: commit
    title: Commit and push implementation
    priority: 2
    needs: [implement]
    notes: Stage changes and commit with a descriptive message
  - id: test
    title: Write and run tests
    priority: 1
    type: qa
    needs: [commit]
    knight: qa.md
```

## Related

- Quest (lore codex show conceptual-entities-quest) — the live grouping of Missions that an orchestrator creates following a Doctrine
- Mission (lore codex show conceptual-entities-mission) — the individual tasks described by each step in a Doctrine
- Knight (lore codex show conceptual-entities-knight) — the persona files referenced by Doctrine steps
- Artifact (lore codex show conceptual-entities-artifact) — template files referenced by ID in Doctrine step notes
- tech-doctrine-internals (lore codex show tech-doctrine-internals) — validation pipeline and module internals
- tech-cli-commands (lore codex show tech-cli-commands) — `lore doctrine` command reference
