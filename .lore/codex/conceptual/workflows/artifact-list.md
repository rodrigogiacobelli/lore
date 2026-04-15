---
id: conceptual-workflows-artifact-list
title: lore artifact list Behaviour
summary: What the system does internally when `lore artifact list` runs — recursive discovery of `.md` files under `.lore/artifacts/`, strict frontmatter validation (files missing required fields are silently skipped), group derivation, and table or JSON output.
related: ["conceptual-entities-artifact", "conceptual-workflows-artifact-new", "tech-cli-commands", "conceptual-workflows-knight-list", "conceptual-workflows-doctrine-list", "conceptual-workflows-filter-list"]
stability: stable
---

# `lore artifact list` Behaviour

`lore artifact list` discovers and displays all artifact template files found recursively under `.lore/artifacts/`. Unlike knights (which fall back to defaults for missing metadata), artifacts are **strict**: any file missing one or more required frontmatter fields is silently skipped and does not appear in the output.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- `.lore/artifacts/` may or may not exist. If it does not exist, the command returns an empty result.

## Steps

### 1. Locate the artifacts directory

The path `.lore/artifacts/` is derived from the project root. If the directory does not exist, an empty list is returned immediately.

### 2. Discover artifact files

All files matching `*.md` are found recursively (`rglob`) under `.lore/artifacts/`. Soft-deleted files (`.md.deleted` suffix) are not matched and are excluded automatically.

### 3. Parse and validate frontmatter for each file

Each `.md` file is read and split on `---` delimiters. A file is included in the output only if **all** of the following conditions are met:

1. The file contains at least three `---`-separated parts.
2. The second part (between the first and second `---`) is valid YAML.
3. The parsed YAML is a mapping (dict).
4. All three required fields are present and non-null: `id`, `title`, `summary`.

If any condition fails, the file is silently skipped — no error, no warning, no output for that file.

### 4. Derive the group

For each included artifact, the group is derived from the subdirectory path between `.lore/artifacts/` and the file. Directory components are joined with `/`.

Examples:
- `.lore/artifacts/my-template.md` → group: `""` (empty; rendered as the sentinel in the table and `null` in JSON)
- `.lore/artifacts/default/codex/overview.md` → group: `default/codex`
- `.lore/artifacts/codex/templates/fi-review.md` → group: `codex/templates`
- `.lore/artifacts/feature-implementation/fi-user-story.md` → group: `feature-implementation`

### 5. Apply filter (when `--filter` is provided)

When one or more `--filter GROUP` tokens are supplied, the validated artifact list is post-filtered using segment-prefix matching on the slash-delimited group form:

- Each supplied token is split on `/`; the artifact's `group` is split on `/`. The token matches when its segments are a proper prefix of the artifact's segments. For example, `--filter default` matches `default`, `default/codex`, and `default/transient`; `--filter codex/templates` matches only the `codex/templates` subtree.
- The hyphen-delimited input grammar (`default-codex`) is no longer accepted — see conceptual-workflows-filter-list for the breaking-change specification.
- Artifacts with `group == ""` (root-level files, directly under `.lore/artifacts/`) are **always** included regardless of filter tokens.
- Unrecognised tokens produce no error — they simply match nothing.
- When `--filter` is not provided, all validated artifacts are returned (existing behaviour preserved).

The `valid` count and skipped-file behaviour are unaffected by the filter — validation runs on all discovered files before the filter is applied.

See conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) for the full filter behaviour specification.

### 6. Sort results

All included records are sorted alphabetically by `id` (ascending, case-sensitive).

### 7. Render output

**Table mode (default):**

A fixed-width table is printed with four columns: `ID`, `GROUP`, `TITLE`, `SUMMARY`.

If no artifacts are found (or all files were skipped), the message `No artifacts found.` is printed.

**JSON mode (`--json` or global `--json`):**

```json
{
  "artifacts": [
    {"id": "fi-review", "group": "codex/templates", "title": "...", "summary": "..."},
    {"id": "overview", "group": "default/codex", "title": "...", "summary": "..."},
    {"id": "transient-note", "group": null, "title": "...", "summary": "..."}
  ]
}
```

The `group` key is slash-joined when the artifact lives in a subdirectory and `null` when it sits at the artifacts root.

Note: `lore artifact list` accepts `--json` as a **local** flag in addition to the global `--json` on the `lore` command. Both have the same effect.

## Key Difference from Knight and Doctrine List

- **Knights:** missing fields fall back to defaults (id → stem, title → id, summary → ""). The file always appears.
- **Doctrines:** missing fields fall back to defaults; invalid YAML shows as `[INVALID]`. The file always appears.
- **Artifacts:** missing required fields → file is silently skipped. No fallbacks.

## Failure Modes

`lore artifact list` has no documented failure modes that produce a non-zero exit code. A non-existent artifacts directory produces an empty result, not an error.

## Out of Scope

- Filtering by fields other than group (title, tags, etc.) — only group filtering via `--filter` is supported.
- Showing artifact content — use `lore artifact show <id>` for that.

## Related

- conceptual-workflows-knight-list (lore codex show conceptual-workflows-knight-list) — lenient fallback behaviour for knights
- conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list) — doctrine listing with validation marking
- conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) — full --filter flag behaviour specification
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
