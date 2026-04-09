---
id: conceptual-workflows-doctrine-list
title: lore doctrine list Behaviour
summary: What the system does internally when `lore doctrine list` runs — recursive discovery of `.design.md` files under `.lore/doctrines/`, pairing with matching `.yaml` files, silent skip of orphaned or unpaired files, metadata extraction from design frontmatter, group derivation, and table or JSON output.
related: ["conceptual-entities-doctrine", "conceptual-workflows-doctrine-new", "conceptual-workflows-doctrine-show", "conceptual-workflows-knight-list", "tech-cli-commands", "conceptual-workflows-filter-list"]
---

# `lore doctrine list` Behaviour

`lore doctrine list` discovers and displays all valid doctrine pairs found recursively under `.lore/doctrines/`. Discovery is driven by `.design.md` files — a `.yaml` with no design file counterpart is invisible. Only complete, valid pairs are shown. No `[INVALID]` suffix is applied — invalid or incomplete pairs are silently skipped.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- `.lore/doctrines/` may or may not exist. If it does not exist, the command returns an empty result.

## Steps

### 1. Locate the doctrines directory

The path `.lore/doctrines/` is derived from the project root. If the directory does not exist, an empty list is returned immediately.

### 2. Discover design files

All files matching `*.design.md` are found recursively (`rglob`) under `.lore/doctrines/`. Files are processed in sorted order.

### 3. Pair each design file with its YAML counterpart

For each `<name>.design.md` found:
- Parse the design file frontmatter to extract `id`, `title`, `summary` using `frontmatter.parse_frontmatter_doc(filepath, required_fields=("id",), extra_fields=("title", "summary"))`.
- If frontmatter parsing fails or `id` is absent, skip this file silently.
- Check for `<name>.yaml` in the **same directory** as the design file.
- If the YAML counterpart is absent, skip this file silently.
- If both files are present, build a listing entry dict.

**Skip silently:** Orphaned design files (missing YAML), YAML-only files (no design file), and design files with unparseable frontmatter do not appear in output in any form.

### 4. Build the listing entry

For each valid pair, the entry dict contains:

| Field | Source | Fallback |
|---|---|---|
| `id` | design frontmatter `id` | (none — required) |
| `title` | design frontmatter `title` | value of `id` |
| `summary` | design frontmatter `summary` | `""` (empty string) |
| `group` | derived from subdirectory path between `.lore/doctrines/` and the file | `""` |
| `filename` | design file name (e.g., `feature-implementation.design.md`) | (always present) |
| `valid` | always `True` | (always `True`) |

Note: `valid` is always `True` in the listing because invalid entries are skipped rather than surfaced.

### 5. Derive the group

Identical to `lore knight list`: directory components between `.lore/doctrines/` and the file, joined with dashes. The filename itself is excluded. Example: a doctrine at `.lore/doctrines/feature-implementation/my-doctrine.design.md` has group `feature-implementation`.

### 6. Apply filter (when `--filter` is provided)

When one or more `--filter GROUP` tokens are supplied, the parsed doctrine list is post-filtered using subtree (prefix) matching:

- Doctrines whose `group` exactly equals a supplied token **or** starts with `token + "-"` are included. For example, `--filter default` returns doctrines with group `default` as well as `default-feature`, `default-ops`, and any other subgroup starting with `default-`.
- Doctrines with `group == ""` (root-level files, directly under `.lore/doctrines/`) are **always** included regardless of filter tokens.
- Unrecognised tokens produce no error — they simply match nothing.
- When `--filter` is not provided, all doctrines are returned.

See conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) for the full filter behaviour specification.

### 7. Render output

**Table mode (default):**

A fixed-width table is printed with four columns: `ID`, `GROUP`, `TITLE`, `SUMMARY`. All entries shown are valid pairs. No `[INVALID]` suffix is shown.

Example:
```
feature-implementation          feature-implementation  Feature Implementation          E2E spec-driven pipeline...
update-changelog                                        Update Changelog                Single-step doctrine...
```

If no doctrines are found, the single message `No doctrines found.` is printed.

**JSON mode (`--json`):**

The `--json` flag is accepted both as a local subcommand flag (`lore doctrine list --json`) and as the global flag (`lore --json doctrine list`). Both produce identical output.

```json
{
  "doctrines": [
    {"id": "feature-implementation", "group": "feature-implementation", "title": "Feature Implementation", "summary": "E2E spec-driven pipeline...", "valid": true},
    {"id": "update-changelog", "group": "", "title": "Update Changelog", "summary": "Single-step doctrine...", "valid": true}
  ]
}
```

All entries have `"valid": true` — invalid entries are skipped, not surfaced. The `filename` key is not included in the JSON output. Exit code 0 in all cases.

## Failure Modes

`lore doctrine list` has no documented failure modes that produce a non-zero exit code. Unpaired files, orphaned design files, and files with invalid frontmatter are silently skipped. A non-existent doctrines directory produces an empty result, not an error.

## Working With JSON Output

To get a list of doctrine IDs:

```
$ lore doctrine list --json | jq -r '.doctrines[].id'
```

To get doctrines in a specific group:

```
$ lore doctrine list --json | jq -r '.doctrines[] | select(.group == "feature-implementation") | .id'
```

All entries returned are valid pairs. No validity check is needed at the caller.

## Out of Scope

- Surfacing incomplete pairs with `valid=False` — only complete pairs appear.
- Filtering by validity — all returned doctrines are valid by construction.
- Showing doctrine step details — use `lore doctrine show <name>` for that.

## Related

- conceptual-workflows-doctrine-show (lore codex show conceptual-workflows-doctrine-show) — how `lore doctrine show` works
- conceptual-workflows-doctrine-new (lore codex show conceptual-workflows-doctrine-new) — how doctrine creation works
- conceptual-workflows-knight-list (lore codex show conceptual-workflows-knight-list) — mirrors this behaviour for knights (no validation step)
- conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) — full --filter flag behaviour specification
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
