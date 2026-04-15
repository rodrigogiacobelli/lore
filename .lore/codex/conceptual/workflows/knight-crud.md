---
id: conceptual-workflows-knight-crud
title: Knight CRUD Operations
summary: >
  What the system does internally when creating, editing, and deleting knights via the CLI, including name validation rules shared with doctrines.
related: ["conceptual-entities-knight", "conceptual-workflows-knight-list"]
stability: stable
---

# Knight CRUD Operations

Knights are markdown files stored in `.lore/knights/` (optionally nested in subdirectory groups). They encode the "how" of a mission — the style, constraints, and authority a worker agent should apply. `lore knight new <name> [--group <path>]`, `lore knight edit <name>`, and `lore knight delete <name>` manage them. Creation goes through `lore.knight.create_knight` — the same core helper the Python API exposes — so `--group` and the Python `group=` kwarg are strictly identical in behaviour.

## Preconditions

- The Lore project has been initialised.
- Knight `name` must match the pattern `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` (starts with alphanumeric, then letters, digits, hyphens, or underscores).
- Content is provided via `--from <file>` or stdin.
- The `--group <path>` value (when provided) is a slash-delimited relative path. Each segment must independently satisfy the name rule. Rejected patterns: `..`, backslash, absolute path, leading/trailing `/`, empty segment, bad-char segment.

## Name Validation

The same rule applies to knight and doctrine names. `validate_name` in `lore.validators` enforces:

- Must start with an alphanumeric character.
- May contain letters, digits, hyphens, and underscores.
- No spaces, dots, or slashes.

Invalid names produce an error before any file system access.

## Steps — Create (`lore knight new <name> [--group <path>]`)

The CLI handler is a thin wrapper: it parses `--from`/stdin and `--group`, then calls `create_knight(knights_dir, name, content, group=group)`. All validation, duplicate detection, mkdir, and writing happens inside the core helper — the Python API is identical.

### 1. Validate name

`validate_name` runs first. On failure, `ValueError` is raised, the CLI prints the message to stderr, and exits 1.

### 2. Validate the group (when `--group` is provided)

`validate_group` checks the group value. `None` is accepted. Any of `..`, backslash, absolute path, leading/trailing `/`, empty segment, bad-char segment → raises `ValueError` with `Error: invalid group '<value>': <reason>`. No filesystem access has happened yet.

### 3. Check for duplicates across the whole subtree

`create_knight` runs `knights_dir.rglob(f"{name}.md")`. A knight named `<name>` anywhere under `.lore/knights/` — at the root or inside any group — blocks the create. If found, `Knight "<name>" already exists.` is raised and the command exits 1.

### 4. Read content

- `--from <file>`: the file is read from disk. If not found, `File not found: <path>` is printed.
- No flag (stdin): content is read from stdin. If stdin is empty or whitespace, `No content provided on stdin.` is printed.

### 5. Create the target directory and write the knight file

Target directory is `.lore/knights/` when `group is None`, or `.lore/knights/<group>` (using `Path(group)` for filesystem joins) when supplied. `mkdir(parents=True, exist_ok=True)` creates intermediate directories idempotently. The content is written to `<target_dir>/<name>.md`.

### 6. Report

Text (root group): `Created knight <name>`.
Text (nested): `Created knight <name> (group: <group>)`.
JSON: `{"name": "<name>", "group": "<group>|null", "filename": "<name>.md", "path": ".lore/knights/[<group>/]<name>.md"}`. The `group` key is slash-joined when nested, `null` at the root.

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
| Invalid group (create) | `Error: invalid group '<value>': <reason>` to stderr | 1 |
| Duplicate name (create, anywhere in subtree) | Error message; not written | 1 |
| Source file not found (--from) | Error to stderr | 1 |
| Empty stdin content | Error to stderr | 1 |
| Knight not found (edit/delete) | Error to stderr | 1 |

## Out of Scope

- Moving an existing knight between groups (`edit --group`, `mv`). Knights stay where they were created; `lore knight edit` preserves the file's location.
- Restoring a deleted knight via the CLI — rename `<name>.md.deleted` back manually.
