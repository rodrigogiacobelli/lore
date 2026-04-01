---
id: conceptual-workflows-watcher-crud
title: Watcher CRUD Operations
summary: What the system does internally when creating, editing, and deleting watchers via the CLI — name validation, duplicate detection, YAML parse-check on write, rglob-based lookup for edit and delete, and soft-delete semantics.
related:
  - conceptual-entities-watcher
  - conceptual-workflows-knight-crud
  - tech-cli-commands
---

# Watcher CRUD Operations

Watchers are YAML files stored in `.lore/watchers/`. `lore watcher new <name>`, `lore watcher edit <name>`, and `lore watcher delete <name>` manage them.

## Preconditions

- The Lore project has been initialised.
- Watcher `name` must match the pattern `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` (same rule as knights and doctrines, enforced by `validate_name` in `lore.validators`).
- Content is provided via `--from <file>` or stdin.

## Name Validation

The same rule applies to knight, doctrine, and watcher names. `validate_name` in `lore.validators` enforces:

- Must start with an alphanumeric character.
- May contain letters, digits, hyphens, and underscores.
- No spaces, dots, or slashes.

Invalid names produce an error before any filesystem access.

## Content Validation

Watcher content must be valid YAML. `create_watcher` and `update_watcher` call `yaml.safe_load` on the content before writing to disk. Content that fails YAML parsing is rejected with an error before it reaches disk.

## Steps — Create (`lore watcher new <name>`)

### 1. Validate name

`validate_name` is applied. On failure, error to stderr, exit code 1.

### 2. Check for duplicates

`create_watcher` checks whether `<name>.yaml` already exists anywhere in `.lore/watchers/` (via `rglob`). If found, `Watcher "<name>" already exists.` is printed and exit code 1 is returned.

### 3. Read content

- `--from <file>`: the file is read from disk. If not found, `File not found: <path>` is printed.
- No flag (stdin): content is read from stdin. If stdin is empty or whitespace, `No content provided on stdin.` is printed.

### 4. Validate YAML

`yaml.safe_load` is called on the content. If parsing fails, an error is printed and exit code 1 is returned. Content is not written to disk.

### 5. Write the watcher file

The `.lore/watchers/` directory is created if absent. The content is written to `.lore/watchers/<name>.yaml`.

### 6. Report

Plain: `Created watcher <name>`. JSON: `{"id": "<name>", "filename": "<name>.yaml"}`.

## Steps — Edit (`lore watcher edit <name>`)

### 1. Validate name and find file

Name validation is applied first. Then `find_watcher(watchers_dir, name)` resolves the file via `rglob`. If not found, `Watcher "<name>" not found.` is returned (exit code 1).

Note: edit uses `rglob` lookup, not a flat path check. This means watchers placed in group subdirectories can be edited by name alone — consistent with how delete works and with the PRD requirement.

### 2. Read new content

Same stdin / `--from <file>` logic as create. Empty stdin is an error.

### 3. Validate YAML

`yaml.safe_load` is called on the new content. Invalid YAML is rejected before any write.

### 4. Overwrite the file

The file is overwritten in place. The file location (subdirectory) is preserved — the file is not moved.

### 5. Report

Plain: `Updated watcher <name>`. JSON: `{"id": "<name>", "filename": "<name>.yaml"}`.

## Steps — Delete (`lore watcher delete <name>`)

### 1. Validate name and find file

If the watcher file does not exist, `Watcher "<name>" not found in .lore/watchers/` is printed to stderr and exit code 1 is returned.

### 2. Soft-delete by rename

The file is renamed to `<name>.yaml.deleted` in place. The content is preserved. The file becomes invisible to all normal discovery operations (`rglob("*.yaml")`).

### 3. Report

Plain: `Deleted watcher <name>`. JSON: `{"id": "<name>", "deleted": true}`.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---------------|-----------|-----------|
| Invalid name (create/edit/delete) | Error to stderr | 1 |
| Duplicate name (create) | Error message | 1 |
| Source file not found (--from) | Error to stderr | 1 |
| Empty stdin content | Error to stderr | 1 |
| Invalid YAML content (create/edit) | Error to stderr | 1 |
| Watcher not found (edit/delete) | Error to stderr | 1 |

## Related

- conceptual-entities-watcher (lore codex show conceptual-entities-watcher) — what a Watcher is
- conceptual-workflows-knight-crud (lore codex show conceptual-workflows-knight-crud) — mirrors this pattern for knights
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
