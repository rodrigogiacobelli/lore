---
id: codex-list-group-technical-map
lens: technical
feature: codex-list-group
title: Context Map — codex-list-group (technical)
summary: Technical-lens context map for the codex-list-group feature — covering scan_codex(), _format_table(), derive_group(), codex_list CLI handler, codex.py, paths.py.
---

# Context Map — codex-list-group (technical)

**Author:** Scout (technical lens)
**Date:** 2026-03-27
**Feature:** _Fix `lore codex list` to output ID, GROUP, TITLE, SUMMARY columns using the shared `_format_table` helper — matching all other entity list commands_
**Lens:** _technical_

---

## Relevant Documents

| ID | Title | Why relevant |
|----|-------|-------------|
| `conceptual-workflows-codex` | Codex Commands — lore codex | Documents the current `codex_list` CLI handler behaviour and current column output (ID, TYPE, TITLE, SUMMARY). The implementation deviates from `_format_table` — it uses inline f-string formatting. This document is the workflow spec being changed. |
| `tech-arch-source-layout` | Source Layout | One-line descriptions of every module in `src/lore/`. Identifies `codex.py`, `paths.py`, and `cli.py` as the three files requiring changes. Confirms `derive_group` lives in `paths.py`. |
| `tech-arch-frontmatter` | Frontmatter Module Internals | Covers `parse_frontmatter_doc` (used by `scan_codex`) — relevant because `scan_codex` will need to return `path` so `derive_group` can be called on each document. The `extra_fields` parameter is key to understanding what scan currently returns. |
| `conceptual-workflows-knight-list` | lore knight list Behaviour | Describes `list_knights` in `knight.py` as the reference implementation: calls `derive_group(filepath, base_dir)` per file, passes `group` in records, renders via `_format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows)`. This is the exact pattern to replicate in `codex_list`. |
| `tech-arch-codex-map` | Codex Map — map_documents and _read_related Internals | Covers `_scan_codex_robust` and `scan_codex` internals. Relevant because `scan_codex` currently returns records without a `group` key — the fix must add group derivation here or in the CLI handler. |

---

## How to Use This Map

Every agent that receives this map should:
1. Run `lore codex show conceptual-workflows-codex tech-arch-source-layout tech-arch-frontmatter conceptual-workflows-knight-list tech-arch-codex-map` with all IDs in the table above
2. Read every document listed before starting their mission
3. Do not explore the codex independently — this map is your entry point

---

## Scout Notes

**Current state in `cli.py` (`codex_list` handler, lines ~2226–2270):**

The handler manually computes column widths and builds f-string rows — it does NOT use `_format_table`. The columns are ID, TYPE, TITLE, SUMMARY. There is no `--json` local flag (only the global `--json`); the JSON output also lacks a `group` field.

**Current state in `codex.py` (`scan_codex`):**

`scan_codex` calls `frontmatter.parse_frontmatter_doc` which returns a dict with keys: `id`, `type`, `title`, `summary`, `path`. No `group` field is present.

**`derive_group` in `paths.py`:**

Already implemented and tested. Signature: `derive_group(filepath: Path, base_dir: Path) -> str`. Joins directory components between `base_dir` and the file with dashes. No changes needed here.

**`_format_table` in `cli.py`:**

Already implemented and used by `knight_list`, `doctrine_list`, `watcher_list`, and `artifact_list`. Signature: `_format_table(headers: list[str], rows: list[list[str]]) -> list[str]`. No changes needed here.

**Required changes:**

1. **`cli.py` — `codex_list` handler:** Replace the manual f-string table with `_format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows)`. Call `paths.derive_group(d["path"], codex_dir)` per document to compute the group. Update JSON output to include `"group"` field (and decide whether to keep or drop `"type"` from JSON — other list commands drop TYPE from JSON; doctrines keep it for validity). Add a local `--json` flag consistent with other list commands.

2. **`codex.py` — `scan_codex` (optional):** Group derivation could be pushed into `scan_codex` (requiring `base_dir` parameter), or handled in the CLI handler inline. The knight pattern keeps derivation in the CLI handler. Either approach works; the CLI handler approach is consistent.

3. **`conceptual-workflows-codex` codex document:** After implementation, the list of columns in the codex doc needs updating from ID/TYPE/TITLE/SUMMARY to ID/GROUP/TITLE/SUMMARY, and the JSON schema example needs a `group` field added.

The codex `scan_codex` returns `path` in each record, which is available to derive group in the handler — no changes to `scan_codex` are strictly required.
