---
id: conceptual-workflows-knight-crud
title: Knight CRUD Operations
summary: >
  What the system does internally when creating, editing, and deleting knights via the CLI, including name validation rules shared with doctrines.
related: ["conceptual-entities-knight", "conceptual-workflows-knight-list"]
stability: stable
---

# Knight CRUD Operations

Knights are markdown files stored in `.lore/knights/`. They encode the "how" of a mission — the style, constraints, and authority a worker agent should apply. `lore knight new <name>`, `lore knight edit <name>`, and `lore knight delete <name>` manage them.

## Preconditions

- The Lore project has been initialised.
- Knight `name` must match the pattern `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` (starts with alphanumeric, then letters, digits, hyphens, or underscores).
- Content is provided via `--from <file>` or stdin.

## Name Validation

The same rule applies to knight and doctrine names. `validate_name` in `lore.validators` enforces:

- Must start with an alphanumeric character.
- May contain letters, digits, hyphens, and underscores.
- No spaces, dots, or slashes.

Invalid names produce an error before any file system access.

## Steps — Create (`lore knight new <name>`)

### 1. Validate name

`_validate_name` in the CLI validates the name. On failure, an error is printed and the command exits with code 1.

### 2. Check for duplicates

The CLI checks whether `<name>.md` already exists at `.lore/knights/<name>.md` or anywhere in its subdirectories (via `rglob`). If found, `Knight "<name>" already exists.` is printed and the command exits.

### 3. Read content

- `--from <file>`: the file is read from disk. If not found, `File not found: <path>` is printed.
- No flag (stdin): content is read from stdin. If stdin is empty or whitespace, `No content provided on stdin.` is printed.

### 4. Write the knight file

The `.lore/knights/` directory is created if absent. The content is written to `.lore/knights/<name>.md`.

### 5. Report

Text: `Created knight <name>`. JSON: `{"name": "<name>", "filename": "<name>.md"}`.

## Steps — Edit (`lore knight edit <name>`)

### 1. Validate name and existence

Name validation is applied first. Then the knight file is looked up at `.lore/knights/<name>.md`. If absent, `Knight "<name>" not found.` is returned.

### 2. Read new content

Same stdin / `--from <file>` logic as create. Empty stdin is an error.

### 3. Overwrite the file

`knight_path.write_text(content)` replaces the entire file.

### 4. Report

Text: `Updated knight <name>`. JSON: `{"name": "<name>", "filename": "<name>.md"}`.

## Steps — Delete (`lore knight delete <name>`)

### 1. Validate name and existence

If the knight file does not exist, `Knight "<name>" not found in .lore/knights/` is printed to stderr and exit code 1 is returned.

### 2. Soft-delete by rename

The file is renamed to `<name>.md.deleted` in place. This preserves the content without exposing it through `lore knight list`.

### 3. Report

Text: `Deleted knight <name>`. JSON: `{"name": "<name>", "deleted": true}`.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Invalid name (create/edit/delete) | Error to stderr | 1 |
| Duplicate name (create) | Error message; not written | 1 |
| Source file not found (--from) | Error to stderr | 1 |
| Empty stdin content | Error to stderr | 1 |
| Knight not found (edit/delete) | Error to stderr | 1 |

## Out of Scope

- Subdirectory organisation of knight files — all knights live flat in `.lore/knights/`.
- Restoring a deleted knight via the CLI — rename `<name>.md.deleted` back manually.
