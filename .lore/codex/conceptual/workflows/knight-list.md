---
id: conceptual-workflows-knight-list
title: lore knight list Behaviour
summary: What the system does internally when `lore knight list` runs — recursive discovery of `.md` files under `.lore/knights/`, frontmatter parsing with graceful fallbacks for missing fields, group derivation from subdirectory path, sorted output as a table or JSON.
related: ["conceptual-entities-knight", "tech-arch-knight-module", "tech-cli-commands", "conceptual-workflows-filter-list"]
stability: stable
---

# `lore knight list` Behaviour

`lore knight list` discovers and displays all knight markdown files found recursively under `.lore/knights/`. It never fails due to a single malformed file — files that cannot be parsed fall back to defaults rather than being skipped or causing an error.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- `.lore/knights/` may or may not exist. If it does not exist, the command returns an empty result.

## Steps

### 1. Locate the knights directory

The path `.lore/knights/` is derived from the project root. If the directory does not exist, an empty list is returned immediately.

### 2. Discover knight files

All files matching `*.md` are found recursively (`rglob`) under `.lore/knights/`. This includes files in subdirectories such as `default/` and any user-created subdirectory groups. The order of discovery is filesystem order; the final list is sorted alphabetically by the resolved `id` field.

Soft-deleted files (`.md.deleted` suffix) are not matched by the `*.md` pattern and are excluded automatically.

### 3. Parse frontmatter for each file

Each discovered `.md` file is read and split on `---` delimiters. If the file contains valid YAML frontmatter (three or more `---`-separated parts, valid YAML in the second part, and the YAML is a mapping), the following fields are extracted. If the file has no frontmatter, invalid YAML, or non-mapping YAML, an empty dict is used and all fields fall back to defaults.

**Field extraction and fallback rules:**

| Field | Source | Fallback |
|---|---|---|
| `id` | `frontmatter["id"]` (stringified) | filename stem |
| `title` | `frontmatter["title"]` (stringified) | value of `id` |
| `summary` | `frontmatter["summary"]` (stringified) | empty string |
| `group` | derived from subdirectory path | empty string (file is in knights root) |

### 4. Derive the group

The `group` for each knight is derived from the subdirectory path between `.lore/knights/` and the file. Directory components are joined with dashes.

Examples:
- `.lore/knights/tech-lead.md` → group: `""` (empty)
- `.lore/knights/default/tech-lead.md` → group: `default`
- `.lore/knights/feature-implementation/architect.md` → group: `feature-implementation`

### 5. Apply filter (when `--filter` is provided)

When one or more `--filter GROUP` tokens are supplied, the collected knight list is post-filtered using subtree (prefix) matching:

- Knights whose `group` exactly equals a supplied token **or** starts with `token + "-"` are included. For example, `--filter feature-implementation` returns knights with group `feature-implementation` as well as `feature-implementation-sub`, and any other subgroup starting with `feature-implementation-`.
- Knights with `group == ""` (root-level files, directly under `.lore/knights/`) are **always** included regardless of filter tokens.
- Unrecognised tokens produce no error — they simply match nothing.
- When `--filter` is not provided, all knights are returned (existing behaviour preserved).

Fallback values (`id` = stem, `summary` = "") apply to the full list before filtering; filtering does not affect how individual knight metadata is resolved.

See conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) for the full filter behaviour specification.

### 6. Sort results

All collected records are sorted alphabetically by the `id` field (ascending, case-sensitive).

### 7. Render output

**Table mode (default):**

A fixed-width table is printed with four columns: `ID`, `GROUP`, `TITLE`, `SUMMARY`. Columns are separated by two spaces. Each column is padded to the width of the widest value across all rows and the header. The last column is not right-padded.

If no knights are found, the single message `No knights found.` is printed.

**JSON mode (`--json`):**

The `--json` flag is accepted both as a local subcommand flag (`lore knight list --json`) and as the global flag (`lore --json knight list`). Both produce identical output. The local flag is declared at the `knight list` subcommand level, matching the pattern of `lore artifact list --json`.

```json
{
  "knights": [
    {"id": "...", "group": "...", "title": "...", "summary": "..."},
    ...
  ]
}
```

The array is in the same sorted order as the table. Exit code 0 in all cases (including empty).

## Failure Modes

`lore knight list` has no documented failure modes that produce a non-zero exit code. Files that cannot be parsed silently fall back to default field values. A non-existent knights directory produces an empty result, not an error.

## Working With JSON Output

To filter knights by group using `jq`:

```
$ lore knight list --json | jq '.knights[] | select(.group == "feature-implementation")'
```

To get only knight IDs:

```
$ lore knight list --json | jq -r '.knights[].id'
```

`lore knight list --json` returns only metadata. To retrieve the full markdown content of a specific knight, use `lore knight show <name> --json`.

## Out of Scope

- Filtering by fields other than group (id, title, etc.) — only group filtering via `--filter` is supported. Use `jq` for further client-side filtering.
- Showing knight file contents in bulk — there is no "show all" command; call `lore knight show` per knight.

## Related

- conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list) — mirrors this behaviour for doctrines
- conceptual-workflows-artifact-list (lore codex show conceptual-workflows-artifact-list) — stricter: skips files missing required fields
- conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) — full --filter flag behaviour specification
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
