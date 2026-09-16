---
id: conceptual-workflows-doctrine-new
title: lore doctrine new Behaviour
summary: What the system does internally when `lore doctrine new <name> -d <design> -m <mission>...` runs — the ten-rule validation order, then a staged directory build moved into place with one os.replace so no partial doctrine is ever left on disk. `-d` is required and at least one `-m` is required.
binds:
- src/lore/doctrine.py
- src/lore/cli.py
- tests/e2e/test_doctrine_new.py
- tests/unit/test_doctrine.py
related: ["conceptual-entities-doctrine", "conceptual-workflows-doctrine-list", "conceptual-workflows-doctrine-show", "conceptual-workflows-doctrine-edit", "ref-lore_cli-commands", "tech-arch-schemas", "conceptual-workflows-health", "decisions-031-staged-multi-file-entity-write"]
---

# `lore doctrine new` Behaviour

`lore doctrine new <name> -d <design-file> -m <mission-file>... [--group <path>]` creates a complete doctrine directory in one call: `<name>/<name>.design.md` plus one `<name>/missions/<stem>.md` per `-m` file. The optional `--group <path>` places the directory in a nested subdirectory (auto-created); without it the directory lands at the doctrines root.

The command is **not idempotent** — a doctrine of the same name anywhere in the subtree aborts it. `-d` is required and at least one `-m` is required. There is no scaffold path.

The whole directory is created or nothing is.

## Preconditions

- The Lore project has been initialised (`.lore/` directory and `lore.db` exist).
- The name argument is a valid identifier: starts with an alphanumeric character and contains only letters, digits, hyphens, and underscores.
- The `--group <path>` value (when provided) is a slash-delimited relative path where each segment independently satisfies the same character rule as a name. It must not contain `..`, backslashes, an absolute path prefix, a leading or trailing `/`, or any empty segment.
- No existing doctrine with the given name exists anywhere under `.lore/doctrines/` — duplicate detection is subtree-wide regardless of `--group`.
- Every source file exists on disk.
- The design file has YAML frontmatter carrying exactly `id`, `title` and `summary`, and its `id` matches `<name>`.
- Each mission file has YAML frontmatter carrying exactly `id`, `title` and `summary`, and its `id` matches its filename stem.

## Validation Order

Every rule below runs before anything reaches disk, in this order. The first failure aborts with its message on stderr and exit code 1, and nothing is written.

| # | Rule | Message |
|---|------|---------|
| 0 | The name is not origin-qualified | `ForeignEntityError` — a foreign doctrine is never writable |
| 1 | Name format | `Invalid name: must start with alphanumeric and contain only letters, digits, hyphens, underscores.` |
| 2 | Group format | `Error: invalid group '<value>': <reason>` |
| 3 | No duplicate anywhere in the subtree | `Error: doctrine '<name>' already exists at <path>` |
| 4 | Design frontmatter present, and its `id` matches the command argument | `Design file id "<id>" does not match command argument "<name>"` |
| 5 | Design frontmatter validates against its schema | the schema's own message |
| 6 | At least one mission file supplied | `At least one mission file is required (-m)` |
| 7 | Each mission id is a valid name | `Invalid mission id "<id>": <reason>` |
| 8 | Each mission's frontmatter `id` equals its filename stem | `Mission file id "<declared>" does not match filename stem "<stem>"` |
| 9 | Each mission's frontmatter validates against its schema | `Mission "<id>": <message>` |

Rules 7, 8 and 9 each run across every mission before the next one starts, so the first failure a caller sees is the earliest *rule* rather than the earliest file.

Two `-m` files sharing a filename stem are rejected before any of this, when the path list is turned into the `{id: content}` mapping: `Duplicate mission id "<stem>": two -m files share a filename stem`.

A missing `-d` fails with `Error: -d/--design is required`. A missing source file fails with `File not found: <path>`.

## The Staged Write

Once every rule passes, `create_doctrine`:

1. Builds the complete tree inside `.lore/doctrines/.<name>.lore-tmp/<name>/`, writing each file through `safewrite.atomic_write_text`.
2. Creates the target's parent directory.
3. Moves the whole tree into place with one `os.replace`.
4. Removes the staging root, whether or not the move succeeded.

The staging directory's name begins with `.`, and discovery skips any path segment beginning with `.` or ending `.deleted`, so it is invisible to every listing, every read and `lore health` while it exists. No partial doctrine is ever left on disk, a crash mid-write included (lore codex show decisions-031-staged-multi-file-entity-write).

## Output

```
$ lore doctrine new tdd-feature-lite --group default -d design.md -m recon.md feature-spec.md scribe.md
Created doctrine tdd-feature-lite with 3 missions in group default
```

Without `--group` the `in group <name>` suffix is absent. With one mission the noun is singular:

```
$ lore doctrine new tdd-feature-lite -d design.md -m recon.md
Created doctrine tdd-feature-lite with 1 mission
```

**JSON mode (`--json`):**

```json
{"created": "tdd-feature-lite", "group": "default", "missions": ["feature-spec", "recon", "scribe"], "path": ".lore/doctrines/default/tdd-feature-lite/"}
```

`group` is `null` and `path` is `.lore/doctrines/tdd-feature-lite/` when `--group` is absent. `missions` is sorted by id. Exit code 0.

## Python API

```python
from pathlib import Path
from lore.api import create_doctrine

create_doctrine(
    Path("."),
    "tdd-feature-lite",
    design_content,                       # str
    {"recon": recon_body, "scribe": scribe_body},   # {mission id: content}
    group="default",
)
```

The Python caller passes a mapping, which physically cannot express two files sharing a stem — the duplicate-stem rule exists only on the path-list side, and `load_mission_sources` is where it lives.

## Schema Validation

The design frontmatter is validated against `lore://schemas/doctrine-design-frontmatter` and each mission's against `lore://schemas/doctrine-mission-frontmatter`, both through `lore.schemas.validate_entity`. These are the same authoritative schemas `lore health --scope schemas` enforces at audit time, so drift between create-time and audit-time is impossible by construction. Cross-field rules — id against the command argument, id against the filename stem — remain inline; everything else lives in the schema.

## Minimal Example

**`design.md`:**
```markdown
---
id: my-workflow
title: My Workflow
summary: One-line description for lore doctrine list.
---

# My Workflow

## Doctrine

| Phase | Mission | Type | Depends On | Input | Output |
|-------|---------|------|------------|-------|--------|
| 0 | step-one | agent | — | Feature request | First output |
| 0 | step-two | agent | step-one | First output | Second output |

## Missions

- **step-one** — does the first thing.
- **step-two** — does the second thing.
```

**`step-one.md`:**
```markdown
---
id: step-one
title: Do the first thing
summary: What this mission produces.
---

# Developer

You are the Developer. …
```

Retrieve the two templates before authoring: `lore artifact show doctrine-design` and `lore artifact show mission-design`.

### Post-Creation Verification

```
$ lore doctrine show my-workflow
$ lore doctrine list
```

## Out of Scope

- Scaffold generation — `-d` and at least one `-m` are required.
- Interactive editing — there is no `$EDITOR` invocation.
- Overwriting an existing doctrine — use `lore doctrine edit`.
- Creating a doctrine with no missions — a doctrine always has at least one.

## Related

- conceptual-workflows-doctrine-edit (lore codex show conceptual-workflows-doctrine-edit) — how doctrine editing works
- conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list) — how doctrine listing works
- conceptual-workflows-doctrine-show (lore codex show conceptual-workflows-doctrine-show) — how doctrine show works
- ref-lore_cli-commands (lore codex show ref-lore_cli-commands) — full CLI reference
