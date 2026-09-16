---
id: conceptual-workflows-doctrine-list
title: lore doctrine list Behaviour
summary: What the system does internally when `lore doctrine list` runs — recursive discovery of doctrine directories under `.lore/doctrines/`, the skip rule for `.`-prefixed and `.deleted` path segments, metadata extraction from design frontmatter, group derivation from the parent of the doctrine directory, and table or JSON output.
binds:
- src/lore/doctrine.py
- src/lore/cli.py
- tests/e2e/test_doctrine_list.py
- tests/unit/test_doctrine.py
related: ["conceptual-entities-doctrine", "conceptual-workflows-doctrine-new", "conceptual-workflows-doctrine-show", "ref-lore_cli-commands", "conceptual-workflows-filter-list", "conceptual-workflows-health", "tech-arch-schemas"]
---

# `lore doctrine list` Behaviour

`lore doctrine list` discovers and displays every doctrine directory found recursively under `.lore/doctrines/`. A directory `D` is a doctrine if and only if `D/<D.name>.design.md` exists. A directory whose design file carries no `id` frontmatter is silently skipped. The silent skips are not silent at audit time: `lore health --scope schemas` validates every design file's frontmatter against `lore://schemas/doctrine-design-frontmatter` and every mission file's against `lore://schemas/doctrine-mission-frontmatter`, and surfaces the skipped files as errors.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- `.lore/doctrines/` may or may not exist. If it does not exist, the command returns an empty result.

## Steps

### 1. Locate the doctrines directory

The path `.lore/doctrines/` is derived from the project root. If the directory does not exist, an empty list is returned immediately.

### 2. Discover doctrine directories

All files matching `*.design.md` are found recursively (`rglob`) under `.lore/doctrines/`, in sorted order. A design file is kept only when its name equals `<parent directory name>.design.md` — that equality is what makes the parent directory a doctrine.

**The skip rule.** Any path segment beginning with `.` or ending `.deleted` hides everything at and below it. One rule makes a soft-deleted doctrine and the staging directory `lore doctrine new` builds equally invisible, and a design file sitting directly in `.lore/doctrines/` identifies no doctrine because its relative path has no directory part.

### 3. Read each design file's frontmatter

Parse the design file frontmatter to extract `id`, `title`, `summary` using `frontmatter.parse_frontmatter_doc(filepath, required_fields=("id",), extra_fields=("title", "summary"))`. If frontmatter parsing fails or `id` is absent, skip this directory silently.

**Skip silently:** design files not named for their parent directory, design files with unparseable frontmatter, and anything under a skipped path segment do not appear in output in any form.

### 4. Build the listing entry

For each doctrine directory, the entry dict contains:

| Field | Source | Fallback |
|---|---|---|
| `id` | design frontmatter `id` | (none — required) |
| `title` | design frontmatter `title` | value of `id` |
| `summary` | design frontmatter `summary` | `""` (empty string) |
| `group` | derived from subdirectory path between `.lore/doctrines/` and the file | `""` |
| `filename` | design file name (e.g., `feature-implementation.design.md`) — the stem a read resolves the directory by | (always present) |
| `valid` | always `True` | (always `True`) |

Note: `valid` is always `True` in the listing because invalid entries are skipped rather than surfaced.

### 5. Derive the group

The directory components between `.lore/doctrines/` and the **doctrine directory**, joined with `/`. The doctrine directory itself is excluded. Example: a doctrine at `.lore/doctrines/feature-implementation/my-doctrine/my-doctrine.design.md` has group `feature-implementation`; one at `.lore/doctrines/seo-analysis/keyword-analysers/ranker/ranker.design.md` has group `seo-analysis/keyword-analysers`. A doctrine directly under `.lore/doctrines/` has `group == ""` (rendered as the existing empty sentinel in the table and `null` in JSON).

Deriving the group from the parent of the doctrine *directory* is what makes `--filter` behave over the directory model exactly as it does for every other entity.

### 6. Apply filter (when `--filter` is provided)

When one or more `--filter GROUP` tokens are supplied, the parsed doctrine list is post-filtered using segment-prefix matching on the slash-delimited group form:

- Each supplied token is split on `/`. A doctrine's `group` is split on `/`. The token matches when its segments are a proper prefix of the doctrine's segments. For example, `--filter seo-analysis` matches `seo-analysis` and `seo-analysis/keyword-analysers`; `--filter seo-analysis/keyword-analysers` matches the nested form exactly.
- The hyphen-delimited input grammar (`default-feature`) is no longer accepted — this is a breaking change. See conceptual-workflows-filter-list for the full specification.
- Doctrines with `group == ""` (root-level files, directly under `.lore/doctrines/`) are **always** included regardless of filter tokens.
- Unrecognised tokens produce no error — they match nothing.
- When `--filter` is not provided, all doctrines are returned.

See conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) for the full filter behaviour specification.

### 7. Render output

**Table mode (default):**

A fixed-width table is printed with four columns: `ID`, `GROUP`, `TITLE`, `SUMMARY`. No `[INVALID]` suffix is shown.

Example:
```
feature-implementation          default/feature-implementation  Feature Implementation      E2E spec-driven pipeline...
update-changelog                default                         Update Changelog            Single-mission doctrine...
```

If no doctrines are found, the single message `No doctrines found.` is printed.

**JSON mode (`--json`):**

The `--json` flag is accepted both as a local subcommand flag (`lore doctrine list --json`) and as the global flag (`lore --json doctrine list`). Both produce identical output.

```json
{
  "doctrines": [
    {"id": "feature-implementation", "group": "feature-implementation", "title": "Feature Implementation", "summary": "E2E spec-driven pipeline...", "valid": true},
    {"id": "keyword-ranker", "group": "seo-analysis/keyword-analysers", "title": "Keyword Ranker", "summary": "...", "valid": true},
    {"id": "update-changelog", "group": null, "title": "Update Changelog", "summary": "Single-step doctrine...", "valid": true}
  ]
}
```

The `group` key is slash-joined when the doctrine lives in a subdirectory and `null` when it sits at the doctrines root. All entries have `"valid": true` — invalid entries are skipped, not surfaced. The `filename` key is not included in the JSON output. Exit code 0 in all cases.

## Failure Modes

`lore doctrine list` has no documented failure modes that produce a non-zero exit code. A design file not named for its parent directory, and one with invalid frontmatter, are silently skipped. A non-existent doctrines directory produces an empty result, not an error.

## Working With JSON Output

To get a list of doctrine IDs:

```
$ lore doctrine list --json | jq -r '.doctrines[].id'
```

To get doctrines in a specific group:

```
$ lore doctrine list --json | jq -r '.doctrines[] | select(.group == "feature-implementation") | .id'
```

`valid` is always `True`. No validity check is needed at the caller.

## Out of Scope

- Surfacing a skipped directory with `valid=False` — a directory that is not a readable doctrine does not appear.
- Filtering by validity — all returned doctrines are valid by construction.
- Showing doctrine step details — use `lore doctrine show <name>` for that.

## Related

- conceptual-workflows-doctrine-show (lore codex show conceptual-workflows-doctrine-show) — how `lore doctrine show` works
- conceptual-workflows-doctrine-new (lore codex show conceptual-workflows-doctrine-new) — how doctrine creation works
- conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) — full --filter flag behaviour specification
- ref-lore_cli-commands (lore codex show ref-lore_cli-commands) — full CLI reference
