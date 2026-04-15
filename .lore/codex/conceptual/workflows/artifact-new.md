---
id: conceptual-workflows-artifact-new
title: lore artifact new Behaviour
summary: What the system does internally when `lore artifact new <name> [--group <path>] --from <body-file>` runs — name and group validation, subtree-wide duplicate detection, strict frontmatter re-check, auto-mkdir of the target group directory, and atomic write of the single `.md` file to `.lore/artifacts/`.
related: ["conceptual-entities-artifact", "conceptual-workflows-artifact-list", "conceptual-workflows-doctrine-new", "conceptual-workflows-knight-crud", "conceptual-workflows-validators", "conceptual-workflows-filter-list", "tech-cli-commands"]
---

# `lore artifact new` Behaviour

`lore artifact new <name> [--group <path>] --from <body-file>` creates a new artifact template file under `.lore/artifacts/`. Before this feature artifact was read-only via the CLI; this is the first CLI write path for artifacts. Creation delegates to `lore.artifact.create_artifact` — the CLI handler is a thin wrapper and the Python API is identical.

## Preconditions

- The Lore project has been initialised (`.lore/` directory and `lore.db` exist).
- The name argument is a valid identifier per `validate_name`.
- The `--group <path>` value (when provided) is a slash-delimited relative path. Each segment must independently satisfy the name rule. Rejected: `..`, backslash, absolute path, leading/trailing `/`, empty segment, bad-char segment.
- No existing artifact with the given name exists anywhere under `.lore/artifacts/` — duplicate detection is subtree-wide regardless of `--group`.
- The `--from <body-file>` source exists on disk and contains a valid artifact body: a YAML frontmatter block with the required fields `id`, `title`, `summary` (the same strict rule enforced by `scan_artifacts`).

## Steps

### 1. Validate the name

`validate_name(name)` runs first. On failure, `ValueError` is raised, the CLI prints the message to stderr, and exits 1. No filesystem access has happened.

### 2. Validate the group (when `--group` is provided)

`validate_group(group)` runs next. `None` is accepted. Any of `..`, backslash, absolute path, leading/trailing `/`, empty segment, or bad-char segment raises `ValueError` with `Error: invalid group '<value>': <reason>` and exits 1.

### 3. Check for duplicates across the whole subtree

`create_artifact` runs `artifacts_dir.rglob(f"{name}.md")`. An artifact named `<name>` anywhere under `.lore/artifacts/` — at the root or in any group — blocks the create. If found, the command aborts with `Error: artifact '<name>' already exists at <existing path>` and exits 1.

### 4. Read the body source

`--from <file>` is required. If the file does not exist, `File not found: <path>` is printed and the command exits 1.

### 5. Validate frontmatter strictly

The body is parsed via the shared frontmatter helper. The file must contain a YAML frontmatter block with all three required fields (`id`, `title`, `summary`), matching the strict rule used by `scan_artifacts`. A body missing required fields is rejected before any write.

### 6. Create the target directory and write the file atomically

Target directory is `.lore/artifacts/` when `group is None`, or `.lore/artifacts/<group>` (using `Path(group)` for filesystem joins) when supplied. `mkdir(parents=True, exist_ok=True)` creates intermediate directories idempotently. The body content is then written to `<target_dir>/<name>.md`.

### 7. Print confirmation

On success:

```
Created artifact <name>
```

Or, when `--group` was supplied:

```
Created artifact <name> (group: <group>)
```

Exit code 0.

## Failure Modes

| Failure point | Message | Exit code |
|---|---|---|
| Invalid name | `Invalid name: must start with alphanumeric and contain only letters, digits, hyphens, underscores.` | 1 |
| Invalid group | `Error: invalid group '<value>': <reason>` | 1 |
| Duplicate artifact (anywhere in subtree) | `Error: artifact '<name>' already exists at <existing path>` | 1 |
| Missing `--from` flag | Click usage error | 2 |
| `--from` file not found | `File not found: <path>` | 1 |
| Missing required frontmatter field in body | Frontmatter validation error | 1 |

## JSON Mode

When `--json` is set, success output is:

```json
{"id": "<name>", "group": "<group>|null", "filename": "<name>.md", "path": ".lore/artifacts/[<group>/]<name>.md"}
```

The `group` key is slash-joined when nested, `null` when the artifact lands at the artifacts root. Errors are returned as `{"error": "<message>"}` to stderr with exit code 1.

## Example

Create a nested artifact under `codex/templates/`:

```
$ lore artifact new fi-review --group codex/templates --from /tmp/review.md
Created artifact fi-review (group: codex/templates)
```

The target directory `.lore/artifacts/codex/templates/` is auto-created. The resulting artifact is listed with `group: codex/templates` and filters with `--filter codex/templates`.

## Out of Scope

- `lore artifact edit` or `lore artifact delete` — still CLI-unavailable. Artifacts remain maintained-on-disk for update and delete.
- Moving an existing artifact between groups. Artifacts stay where they were created.

## Related

- conceptual-entities-artifact (lore codex show conceptual-entities-artifact) — what an Artifact is
- conceptual-workflows-artifact-list (lore codex show conceptual-workflows-artifact-list) — how artifact listing and filtering work
- conceptual-workflows-doctrine-new (lore codex show conceptual-workflows-doctrine-new) — sibling two-file create flow
- conceptual-workflows-knight-crud (lore codex show conceptual-workflows-knight-crud) — sibling single-file create flow
- conceptual-workflows-validators (lore codex show conceptual-workflows-validators) — `validate_group` rules
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
