---
id: conceptual-workflows-watcher-crud
title: Watcher CRUD Operations
summary: What the system does internally when creating, editing, and deleting watchers via the CLI — name validation, duplicate detection, YAML parse-check on write, rglob-based lookup for edit and delete, and soft-delete semantics.
related:
  - conceptual-entities-watcher
  - conceptual-workflows-knight-crud
  - tech-cli-commands
  - tech-arch-schemas
  - conceptual-workflows-health
---

# Watcher CRUD Operations

Watchers are YAML files stored in `.lore/watchers/` (optionally nested in subdirectory groups). `lore watcher new <name> [--group <path>]`, `lore watcher edit <name>`, and `lore watcher delete <name>` manage them. Creation goes through `lore.watcher.create_watcher` — the CLI is a thin wrapper around the Python API, and `--group` / `group=` behave identically.

## Preconditions

- The Lore project has been initialised.
- Watcher `name` must match the pattern `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` (same rule as knights and doctrines, enforced by `validate_name` in `lore.validators`).
- Content is provided via `--from <file>` or stdin.
- The `--group <path>` value (when provided) is a slash-delimited relative path. Each segment must satisfy the name rule independently. Rejected: `..`, backslash, absolute path, leading/trailing `/`, empty segment, bad-char segment.

## Name Validation

The same rule applies to knight, doctrine, and watcher names. `validate_name` in `lore.validators` enforces:

- Must start with an alphanumeric character.
- May contain letters, digits, hyphens, and underscores.
- No spaces, dots, or slashes.

Invalid names produce an error before any filesystem access.

## Content Validation

Watcher content must be valid YAML. `create_watcher` and `update_watcher` call `yaml.safe_load` on the content before writing to disk. Content that fails YAML parsing is rejected with an error before it reaches disk.

## Steps — Create (`lore watcher new <name> [--group <path>]`)

The CLI handler parses `--from`/stdin and `--group` and then calls `create_watcher(watchers_dir, name, content, group=group)`. All validation, duplicate detection, mkdir, and writing happen inside the core helper.

### 1. Validate name

`validate_name` is applied. On failure, error to stderr, exit code 1.

### 2. Validate the group (when `--group` is provided)

`validate_group` checks the group. `None` is accepted. Any of `..`, backslash, absolute path, leading/trailing `/`, empty segment, bad-char segment → `ValueError` with `Error: invalid group '<value>': <reason>` to stderr, exit 1.

### 3. Check for duplicates across the whole subtree

`create_watcher` runs `watchers_dir.rglob(f"{name}.yaml")`. A watcher named `<name>` anywhere under `.lore/watchers/` blocks the create regardless of the supplied group.

### 4. Read content

- `--from <file>`: the file is read from disk. If not found, `File not found: <path>` is printed.
- No flag (stdin): content is read from stdin. If stdin is empty or whitespace, `No content provided on stdin.` is printed.

### 5. Validate YAML

`yaml.safe_load` is called on the content. If parsing fails, an error is printed and exit code 1 is returned. Content is not written to disk.

### 6. Create the target directory and write the watcher file

Target directory is `.lore/watchers/` when `group is None`, or `.lore/watchers/<group>` when supplied. `mkdir(parents=True, exist_ok=True)` is idempotent — pre-existing group directories never fail the create. The content is written to `<target_dir>/<name>.yaml`.

### 7. Report

Plain (root group): `Created watcher <name>`.
Plain (nested): `Created watcher <name> (group: <group>)`.
JSON: `{"id": "<name>", "group": "<group>|null", "filename": "<name>.yaml", "path": ".lore/watchers/[<group>/]<name>.yaml"}`. The `group` key is slash-joined when nested, `null` at the root.

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
| Invalid group (create) | `Error: invalid group '<value>': <reason>` to stderr | 1 |
| Duplicate name (create, anywhere in subtree) | Error message | 1 |
| Source file not found (--from) | Error to stderr | 1 |
| Empty stdin content | Error to stderr | 1 |
| Invalid YAML content (create/edit) | Error to stderr | 1 |
| Watcher not found (edit/delete) | Error to stderr | 1 |

## Schema Validation

Watcher YAML shape is validated at create/edit time via `lore.schemas.validate_entity("watcher", data)` — the authoritative schema is `lore://schemas/watcher-yaml`. Required fields (`id`, `title`, `summary`, `watch_target`, `interval`, `action`), the `interval` enum, the `watch_target` array shape, and the per-action `doctrine` XOR `bash` `oneOf` rule all live in the schema. A basic YAML parse-check still runs first so parse errors surface before schema validation. `lore health --scope schemas` enforces the same contract across every watcher already on disk.

## Related

- conceptual-entities-watcher (lore codex show conceptual-entities-watcher) — what a Watcher is
- conceptual-workflows-knight-crud (lore codex show conceptual-workflows-knight-crud) — mirrors this pattern for knights
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
