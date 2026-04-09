---
id: conceptual-workflows-doctrine-new
title: lore doctrine new Behaviour
summary: What the system does internally when `lore doctrine new <name> -f <yaml> -d <design>` runs — name validation, duplicate detection, validation of both source files, and atomic write of both files to disk. Both -f and -d flags are required; no scaffold path exists.
related: ["conceptual-entities-doctrine", "conceptual-workflows-doctrine-list", "conceptual-workflows-doctrine-show", "tech-cli-commands"]
---

# `lore doctrine new` Behaviour

`lore doctrine new <name> -f <yaml-file> -d <design-file>` creates a new doctrine by writing both a `.yaml` steps file and a `.design.md` documentation file to `.lore/doctrines/`. The command is **not idempotent** — if a doctrine with the same name already exists anywhere in the tree, it aborts with an error. Both `-f` and `-d` flags are required. There is no scaffold path.

## Preconditions

- The Lore project has been initialised (`.lore/` directory and `lore.db` exist).
- The name argument is a valid identifier: starts with an alphanumeric character and contains only letters, digits, hyphens, and underscores.
- No existing doctrine with the given name exists anywhere under `.lore/doctrines/`.
- Both source files (`-f` and `-d`) exist on disk.
- The YAML source file has `id` and `steps` fields; `id` must match `<name>`. It must not contain `name` or `description` fields.
- The design file has YAML frontmatter with an `id` field that matches `<name>`.

## Steps

### 1. Validate the name

The name is checked against the pattern `^[a-zA-Z0-9][a-zA-Z0-9_-]*$`. If the name is empty or contains invalid characters, the command aborts with:

```
Invalid name: must start with alphanumeric and contain only letters, digits, hyphens, underscores.
```

No file is written. Exit code 1.

### 2. Check for duplicates

A recursive search (`rglob`) checks for `<name>.yaml` or `<name>.design.md` anywhere under `.lore/doctrines/`. If either is found, the command aborts with:

```
Error: doctrine '<name>' already exists.
```

Exit code 1.

### 3. Read both source files

- `-f <yaml-file>`: the YAML source file is read from disk. If the file does not exist, the command aborts with `File not found: <path>`. Exit code 1.
- `-d <design-file>`: the design source file is read from disk. If the file does not exist, the command aborts with `File not found: <path>`. Exit code 1.

If either flag is omitted entirely:
- Missing `-f`: `Error: -f/--from is required`. Exit code 1.
- Missing `-d`: `Error: -d/--design is required`. Exit code 1.

### 4. Validate both files

All validation happens before any write. If either file fails validation, no files are written.

**YAML validation (`_validate_yaml_schema`):**
1. Must be valid YAML and a mapping.
2. `id` must be present.
3. `steps` must be present and a non-empty list.
4. `id` must match the `<name>` argument.
5. `name` must NOT be present (`Unexpected field in YAML: name`).
6. `description` must NOT be present (`Unexpected field in YAML: description`).
7. Each step must have `id` and `title`; step IDs must be unique; dependency references valid; no cycles.

**Design file validation (`_validate_design_frontmatter`):**
1. Must have YAML frontmatter.
2. `id` must be present in frontmatter.
3. `id` must match the `<name>` argument.

### 5. Write both files atomically

If all checks pass, both files are written to `.lore/doctrines/`:
- `<name>.yaml` — copy of the YAML source content
- `<name>.design.md` — copy of the design source content

The `.lore/doctrines/` directory is created if it does not exist.

Both files are written before the command considers itself done. Either both files are written, or neither is.

### 6. Print confirmation

On success:

```
Created doctrine <name>
```

Exit code 0.

## Failure Modes

| Failure point | Message | Exit code |
|---|---|---|
| Invalid name | `Invalid name: must start with alphanumeric and contain only letters, digits, hyphens, underscores.` | 1 |
| Duplicate doctrine | `Error: doctrine '<name>' already exists.` | 1 |
| Missing `-f` flag | `Error: -f/--from is required` | 1 |
| Missing `-d` flag | `Error: -d/--design is required` | 1 |
| `-f` file not found | `File not found: <path>` | 1 |
| `-d` file not found | `File not found: <path>` | 1 |
| YAML parse error | `YAML parsing error: <details>` | 1 |
| YAML is not a mapping | `Doctrine must be a YAML mapping` | 1 |
| Missing `id` in YAML | `Missing required field: id` | 1 |
| Missing `steps` in YAML | `Missing required field: steps` | 1 |
| YAML `id` mismatch | `Doctrine id "<value>" does not match command argument "<name>"` | 1 |
| `name` in YAML | `Unexpected field in YAML: name` | 1 |
| `description` in YAML | `Unexpected field in YAML: description` | 1 |
| Design frontmatter `id` mismatch | `Design file id "<value>" does not match command argument "<name>"` | 1 |
| Missing `id` in design frontmatter | `Design file missing required frontmatter field: id` | 1 |
| Invalid step structure | Step-specific error message | 1 |
| Dependency cycle | `Dependency cycle detected involving step "<step_id>"` | 1 |

## JSON Mode

When the global `--json` flag is set, success output is:

```json
{"name": "<name>", "yaml_filename": "<name>.yaml", "design_filename": "<name>.design.md"}
```

Errors are returned as `{"error": "<message>"}` to stderr with exit code 1.

## Orchestrator Guidance

### Edit vs Create?

Before creating a new doctrine, check whether an existing one covers the same workflow:

```
$ lore doctrine list
```

If an existing doctrine covers 80% of the workflow you need, use `lore doctrine edit` rather than creating a parallel doctrine. Only create a new doctrine when no existing one covers the workflow you are documenting.

### Authoring a New Doctrine

Both files must be prepared before running `lore doctrine new`. Write them to a temporary location, then register them:

```
$ lore doctrine new my-workflow -f /tmp/my-workflow.yaml -d /tmp/my-workflow.design.md
```

The YAML must have `id` and `steps` only at the top level. The design file must have YAML frontmatter with at least `id`. Both `id` values must match the `<name>` argument and the target filename stem.

### Minimal YAML example

```yaml
id: my-workflow
steps:
  - id: step-one
    title: Do the first thing
    priority: 2
    type: knight
    knight: default/developer.md
  - id: step-two
    title: Do the second thing
    priority: 2
    type: knight
    needs: [step-one]
    knight: default/qa.md
```

### Minimal design file example

```markdown
---
id: my-workflow
title: My Workflow
summary: One-line description for lore doctrine list.
---

# My Workflow

Brief description of this workflow and when to use it.
```

### Post-Creation Verification

After creating a doctrine, verify it with:

```
$ lore doctrine show my-workflow
```

Then confirm it appears in the list:

```
$ lore doctrine list
```

## Out of Scope

- Scaffold generation — the scaffold path has been removed. Both `-f` and `-d` are required.
- Interactive editing — there is no `$EDITOR` invocation.
- Overwriting an existing doctrine — use `lore doctrine edit` for that.
- Creating a doctrine from existing YAML only — a `.design.md` file must be authored first.

## Related

- conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list) — how doctrine listing works
- conceptual-workflows-doctrine-show (lore codex show conceptual-workflows-doctrine-show) — how doctrine show works
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
