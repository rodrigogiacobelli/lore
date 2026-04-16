---
id: conceptual-workflows-codex
title: Codex Commands — lore codex
summary: 'What the system does internally when lore codex list, lore codex search,
  lore codex show, lore codex map, and lore codex chaos run — document discovery,
  keyword search, multi-ID retrieval with deduplication, BFS graph traversal, probabilistic
  random-walk traversal, and JSON output.

  '
related:
- tech-arch-initialized-project-structure
- conceptual-workflows-codex-map
- conceptual-workflows-codex-chaos
- conceptual-workflows-filter-list
---

# Codex Commands — `lore codex`

The codex is the agent-facing documentation store. All codex documents live under `.lore/codex/` as markdown files with YAML frontmatter. The `lore codex` command group provides read-only access.

## Preconditions

- The Lore project has been initialised.
- Codex documents must have `id`, `title`, and `summary` frontmatter fields for full display.

## Steps — List (`lore codex list`)

### 1. Scan the codex directory

`scan_codex` in `lore.codex` walks `.lore/codex/` recursively, parsing YAML frontmatter from every `.md` file. Documents without valid frontmatter are skipped or shown with fallback values.

### 2. Apply filter (when `--filter` is provided)

When one or more `--filter GROUP` tokens are supplied, the scanned document list is post-filtered using subtree (prefix) matching:

- Documents whose `group` exactly equals a supplied token **or** starts with `token + "-"` are included. For example, `--filter conceptual` returns documents with group `conceptual` as well as `conceptual-workflows`, `conceptual-reference`, and any other subgroup whose name starts with `conceptual-`.
- Documents with `group == ""` (root-level files, directly under `.lore/codex/`) are **always** included regardless of filter tokens.
- Unrecognised tokens produce no error — they simply match nothing.
- When `--filter` is not provided, all documents are returned (existing behaviour preserved).

See conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) for the full filter behaviour specification.

### 3. Render

A table with columns `ID`, `GROUP`, `TITLE`, `SUMMARY` is printed using the shared `_format_table` helper. GROUP is derived from the document's directory path under `.lore/codex/` via `derive_group`. Documents at the root of `.lore/codex/` (no subdirectory) render with an empty GROUP. If no documents are found, `No codex documents found.` is printed.

### 4. JSON mode

```json
{
  "codex": [
    {"id": "...", "group": "...", "title": "...", "summary": "..."}
  ]
}
```

## Steps — Search (`lore codex search <keyword>`)

### 1. Scan and filter

`search_documents` in `lore.codex` scans the codex directory (same as list) then filters documents where the keyword appears (case-insensitive) in the `id`, `title`, or `summary` fields.

### 2. Render

Same table format as list. If no documents match, `No documents matching "<keyword>".` is printed.

### 3. JSON mode

Same `{"documents": [...]}` envelope with only matching documents.

## Steps — Show (`lore codex show <id> [<id> ...]`)

### 1. Accept multiple IDs

The command accepts one or more IDs as positional arguments. Duplicate IDs in the argument list are deduplicated (via `dict.fromkeys`): each document is shown at most once even if its ID is repeated.

### 2. Fetch each document

`read_document` in `lore.codex` looks up each document by its frontmatter `id`. If a document with the given ID is not found, an error is returned for that ID and the command exits immediately without printing any output.

### 3. Render

Text mode: each document is printed with a `=== <id> ===` separator followed by the document body (content after frontmatter).

```
=== conceptual-workflows-claim ===
# `lore claim` Behaviour
...
```

### 4. JSON mode

```json
{
  "documents": [
    {"id": "...", "title": "...", "summary": "...", "body": "..."}
  ]
}
```

## Steps — Map (`lore codex map <id> --depth <n>`)

`lore codex map` performs BFS traversal of the `related` frontmatter field starting
from a root document, returning every discovered document in BFS order up to the
requested depth. For the complete workflow, see
`conceptual-workflows-codex-map` (`lore codex show conceptual-workflows-codex-map`).

Output format matches `lore codex show` exactly in both text and JSON modes.

## Steps — Chaos (`lore codex chaos <id> --threshold <int>`)

`lore codex chaos` performs a random-walk traversal of the `related` frontmatter
field starting from a seed document, returning a non-deterministic subset of
connected documents. The walk terminates when the ratio of discovered documents to
the total reachable subgraph exceeds `--threshold / 100`, or when no unvisited
reachable neighbours remain. For the complete workflow, see
`conceptual-workflows-codex-chaos` (`lore codex show conceptual-workflows-codex-chaos`).

Output format is a table with columns ID, GROUP, TITLE, SUMMARY — identical to
`lore codex list` in both text and JSON modes. The seed document is always the
first row. Output order is non-deterministic.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Document not found (show) | `Document "<id>" not found` to stderr | 1 |
| Document not found (map) | `Document "<id>" not found` to stderr | 1 |
| Seed not found (chaos) | `Document "<id>" not found` to stderr | 1 |
| `--threshold` out of range (chaos) | `--threshold must be between 30 and 100` to stderr | 1 |
| No documents in codex (list) | `No codex documents found.` | 0 |
| No matching documents (search) | `No documents matching "<keyword>".` | 0 |

## Out of Scope

- Writing or updating codex documents via the CLI — codex is read-only through the CLI.
- Full-text search within document bodies — search matches `id`, `title`, and `summary` only.
- Graph traversal output showing which document linked to which — `lore codex map` returns a flat list in BFS order.

All five codex commands support `--json`.
