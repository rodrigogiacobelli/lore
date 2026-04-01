---
id: tech-arch-frontmatter
title: Frontmatter Module Internals
summary: >
  Technical reference for src/lore/frontmatter.py. Covers parse_frontmatter_doc
  (metadata-only, for scan functions) and parse_frontmatter_doc_full (includes body,
  for show functions), the required-fields contract, and the extra_fields parameter
  used by _read_related to extract the related frontmatter field for BFS traversal.
related: ["tech-arch-source-layout", "tech-arch-knight-module", "tech-arch-validators", "tech-arch-codex-map"]
stability: stable
---

# Frontmatter Module Internals

**Source module:** `src/lore/frontmatter.py`

This module provides shared frontmatter parsing for markdown files with YAML front
matter. It ships as part of the ADR-012 refactor (REFACTOR-3 and REFACTOR-4), replacing
near-identical private parsing functions that existed separately in `codex.py`
(`_parse_doc`) and `artifact.py` (`_parse_artifact`).

## Purpose

Before this module existed, both `codex.py` and `artifact.py` independently parsed YAML
frontmatter from markdown files. The two implementations were nearly identical (INF-19
in the adversarial review). REFACTOR-3/4 extract the shared logic into a single
authoritative module, following the DRY principle (ADR-012).

Additionally, both modules previously read each file twice — once to extract metadata
for scan operations, and again to retrieve the body for show operations. The
`parse_frontmatter_doc_full` function eliminates the double-read.

## Public Interface

### `parse_frontmatter_doc(filepath, required_fields=("id","title","summary"), extra_fields=()) -> dict | None`

Reads frontmatter metadata only. Used by scan functions where the body is not needed.

- **Input:** `filepath` — path to the markdown file; `required_fields` — tuple of
  frontmatter keys that must be present (default: `("id","title","summary")`);
  `extra_fields` — tuple of additional frontmatter keys to include in the returned dict
  (default: `()`).
- **Output:** A record dict with keys `id`, `title`, `summary`, `path` if all
  required fields are present, plus any keys named in `extra_fields` that are present in
  the frontmatter. Returns `None` if required fields are missing or YAML is invalid.
- **File reads:** Reads the file once, parsing only the frontmatter block between the
  opening and closing `---` delimiters.

The `required_fields` parameter specifies which frontmatter keys must be present. The default value `("id", "title", "summary")` applies to all callers.

### `extra_fields` Parameter

When `extra_fields` is provided, the named keys are extracted from the frontmatter and included in the returned dict with their raw YAML values (not stringified). Fields listed in `extra_fields` that are absent in the frontmatter are omitted from the returned dict — callers must use `.get()`. The default `extra_fields=()` leaves all existing callers entirely unaffected.

Example usage by `_read_related` in `codex.py`:

```python
doc = parse_frontmatter_doc(filepath, extra_fields=("related",))
raw_related = doc.get("related")  # list[str] | None
```

### `parse_frontmatter_doc_full(filepath, required_fields=("id","title","summary"), extra_fields=()) -> dict | None`

Reads frontmatter metadata and the document body. Used by retrieval functions where
the full content is needed.

- **Input:** Same as `parse_frontmatter_doc`.
- **Output:** Same as `parse_frontmatter_doc` plus a `body` key containing all content
  after the second `---` delimiter, stripped of leading/trailing whitespace.
- **File reads:** Reads the file exactly once. This eliminates the double-read pattern
  (INF-17) where scan modules read metadata on one pass and the body on a separate pass.

## Required Fields

Both functions require the fields listed in the `required_fields` parameter to be present and non-empty. The default required fields are `("id", "title", "summary")`, matching the contract for codex documents, artifacts, and knights. Artifact callers use the default `required_fields=("id", "title", "summary")`.

A file missing any required field is silently skipped — the function returns `None`. This matches the existing behaviour for codex and artifact scan operations.

## Callers

| Function | Module | Uses |
|---|---|---|
| `scan_codex` | `codex.py` | `parse_frontmatter_doc` (metadata-only) |
| `search_documents` | `codex.py` | `parse_frontmatter_doc` (metadata-only) |
| `read_document` | `codex.py` | `parse_frontmatter_doc_full` (includes body) |
| `_read_related` | `codex.py` | `parse_frontmatter_doc` (metadata-only, `extra_fields=("related",)`) |
| `scan_artifacts` | `artifact.py` | `parse_frontmatter_doc` (metadata-only) |
| `read_artifact` | `artifact.py` | `parse_frontmatter_doc_full` (includes body) |
| `list_knights` | `knight.py` | `parse_frontmatter_doc` (metadata-only, `required_fields=("id","title","summary")`) |

Imported by `codex.py`, `artifact.py`, and `knight.py`.

## Why Not Inline

`_parse_doc` in `codex.py` and `_parse_artifact` in `artifact.py` were near-identical
implementations (INF-19 in the adversarial-review-code-principles report). Maintaining
two copies created a DRY violation: any bug fix or enhancement had to be applied in both
places. `frontmatter.py` is the single authoritative implementation, following ADR-012's
DRY principle.
