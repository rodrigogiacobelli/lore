---
id: conceptual-workflows-doctrine-new
title: lore doctrine new Behaviour
summary: What the system does internally when `lore doctrine new <name>` runs — name validation, duplicate detection, content sourcing (stdin or --from file), YAML validation against the doctrine schema, and atomic write to disk.
related: ["conceptual-entities-doctrine", "conceptual-workflows-doctrine-list", "tech-cli-commands"]
stability: stable
---

# `lore doctrine new` Behaviour

`lore doctrine new <name>` creates a new doctrine YAML file at `.lore/doctrines/<name>.yaml`. The command is **not idempotent** — if a doctrine with the same name already exists (either in the flat directory or any subdirectory), it aborts with an error.

## Preconditions

- The Lore project has been initialised (`.lore/` directory and `lore.db` exist).
- The name argument is a valid identifier: starts with an alphanumeric character and contains only letters, digits, hyphens, and underscores.
- No existing doctrine with the given name exists at `.lore/doctrines/<name>.yaml` or in any subdirectory of `.lore/doctrines/`.
- Content is available either on stdin or via `--from <file>`. When invoked with no `--from` file and no piped stdin (TTY stdin), the command generates a skeleton YAML rather than reading content from stdin.

## Steps

### 1. Validate the name

The name is checked against the pattern `^[a-zA-Z0-9][a-zA-Z0-9_-]*$`. If the name is empty or contains invalid characters (e.g. spaces, slashes), the command aborts immediately with:

```
Error: Invalid name: must start with alphanumeric and contain only letters, digits, hyphens, underscores.
```

No file is written. Exit code 1.

### 2. Check for duplicates

The command checks whether `.lore/doctrines/<name>.yaml` already exists. It also performs a recursive search (`rglob`) for `<name>.yaml` anywhere under `.lore/doctrines/`. If either check matches, the command aborts with:

```
Error: doctrine '<name>' already exists. Use 'lore doctrine edit <name>' to modify it.
```

Exit code 1.

### 3. Source the content or generate scaffold

Content is sourced from one of three places:

- **`--from <file>`** (or `-f <file>`): the named file is read from disk. If the file does not exist, the command aborts with `File not found: <file>`. Exit code 1.
- **stdin** (default, when `--from` is absent or is `-`): the command reads all of stdin. If stdin is empty or contains only whitespace, the command aborts with `No content provided on stdin.` Exit code 1.
- **No stdin + TTY** (new): When `--from` is `None` and `sys.stdin.isatty()` is `True`, `scaffold_doctrine(name)` is called to produce a YAML skeleton. Steps 4 (validation) and the "No content provided on stdin" failure are bypassed — the skeleton is written directly to disk.

### 4. Validate the content

> **Note:** This step is skipped on the scaffold path. The skeleton is written without validation because it intentionally lacks fields required by the strict validator (`name`, `steps[].id`, `steps[].title`). It is a human-editable template.

The content is parsed as YAML and validated against doctrine schema rules:

1. Must be a valid YAML mapping (not a list or scalar).
2. Must contain the required fields: `name`, `description`, `steps`.
3. The `name` field in the YAML must exactly match the `<name>` argument given on the command line.
4. If an `id` field is present, it must also match the `<name>` argument.
5. `steps` must be a non-empty list.
6. Each step must be a mapping with at least `id` and `title` fields.
7. Step IDs must be unique within the doctrine.
8. If `priority` is present on a step, it must be an integer between 0 and 4 inclusive.
9. All `needs` references must point to step IDs that exist within the same doctrine.
10. No dependency cycles are permitted (validated via DFS).

If any validation rule fails, the command aborts with a descriptive error message. Exit code 1. No file is written.

### 5. Write the file

The `.lore/doctrines/` directory is created if it does not exist (including any intermediate parents) — `doctrines_dir.mkdir(parents=True, exist_ok=True)` is called on both the scaffold path and the stdin/`--from` path. The validated content (or scaffold skeleton) is written to `.lore/doctrines/<name>.yaml`.

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
| Duplicate doctrine | `Error: doctrine '<name>' already exists. Use 'lore doctrine edit <name>' to modify it.` | 1 |
| `--from` file not found | `File not found: <path>` | 1 |
| Empty stdin | `No content provided on stdin.` | 1 |
| YAML parse error | `YAML parsing error: <details>` | 1 |
| Content is not a mapping | `Doctrine must be a YAML mapping` | 1 |
| Missing required field | `Missing required field: <field>` | 1 |
| Name mismatch | `Doctrine name "<value>" does not match command argument "<name>"` | 1 |
| id mismatch | `Doctrine id "<value>" does not match command argument "<name>"` | 1 |
| Invalid step structure | Step-specific error message | 1 |
| Dependency cycle | `Dependency cycle detected involving step "<step_id>"` | 1 |

## JSON Mode

When the global `--json` flag is set, success output is:

```json
{"name": "<name>", "filename": "<name>.yaml"}
```

This format applies to all three input paths (scaffold, stdin, `--from`).

Errors are returned as `{"error": "<message>"}` to stdout (not stderr) with exit code 1.

## Orchestrator Guidance

### Edit vs Create?

Before creating a new doctrine, check whether an existing one covers the same workflow:

```
$ lore doctrine list
```

If an existing doctrine covers 80% of the workflow you need, extend it with `lore doctrine edit` rather than creating a parallel doctrine. Duplicate doctrines cause confusion for orchestrators. Only create a new doctrine when no existing one covers the workflow you are documenting.

### Scaffold vs Write From Scratch?

Use the scaffold path (`lore doctrine new <name>` with no stdin and no `--from`) when you do not have YAML ready. Lore generates a skeleton at `.lore/doctrines/<name>.yaml`. Open the file, fill in the steps, then verify with `lore doctrine show <name>`.

Use `--from` when your YAML is already written and version-controlled.

### Complete YAML Example

A minimal valid doctrine with steps, priorities, knight assignments, and dependencies:

```yaml
name: my-flow
id: my-flow
title: My Workflow
summary: One-line description for lore doctrine list.
description: Full description of this workflow and when to use it.
steps:
  - id: step-one
    title: Do the first thing
    priority: 0
    type: knight
    knight: default/developer.md
    notes: Instructions for the worker performing this step.

  - id: step-two
    title: Do the second thing
    priority: 1
    type: knight
    needs: [step-one]
    knight: default/qa.md
    notes: Verify what step-one produced.
```

The `id`, `title`, and `summary` top-level fields are optional but recommended — without them, `lore doctrine list` falls back to the filename stem for both `id` and `title`, and truncates `description` as the summary.

### Stdin vs `--from`?

Use `--from` for repeatable workflows where the YAML file is version-controlled. Use stdin for one-off or generated content.

### Post-Creation Verification

After creating a doctrine, verify it with:

```
$ lore doctrine show my-flow
```

Then confirm it appears in the list:

```
$ lore doctrine list
```

If anything needs changing, use `lore doctrine edit my-flow`.

## Out of Scope

- Modifying the scaffold template — the skeleton is fixed in `scaffold_doctrine()` in `doctrine.py`. Use `lore doctrine edit` after creation to replace it.
- Interactive editing — there is no `$EDITOR` invocation.
- Overwriting an existing doctrine — use `lore doctrine edit` for that.
- Copying an existing doctrine as a starting point — read the existing one with `lore doctrine show <name> --json`, modify the YAML, change the `name` field, then pipe to `lore doctrine new`.

## Related

- conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list) — how doctrine listing works
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
