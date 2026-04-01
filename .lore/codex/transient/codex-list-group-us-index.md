---
id: codex-list-group-us-index
feature: codex-list-group
status: final
title: codex-list-group User Story Index
summary: Index of all user stories for the codex-list-group feature, covering tabular GROUP column output and JSON group field with codex envelope key.
---

# codex-list-group — User Story Index

**Author:** Business Analyst
**Date:** 2026-03-27
**Status:** final
**PRD:** `lore codex show codex-list-group-prd`
**Tech Spec:** `lore codex show codex-list-group-tech-spec`

---

## Stories by Epic

### codex-list-group

Align `lore codex list` with all other entity list commands by replacing the TYPE column with GROUP in tabular output and adding `group` to JSON output with the correct `"codex"` envelope key.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-1 | Display GROUP instead of TYPE in `lore codex list` tabular output | final | _(to be filled after `lore codex list --json`)_ |
| US-2 | Include `group` field and `"codex"` envelope key in `lore codex list --json` | final | _(to be filled after `lore codex list --json`)_ |

---

## PRD Coverage Map

| PRD Requirement | Story IDs |
|-----------------|-----------|
| FR-1: `lore codex list` renders via `_format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows)` | US-1 |
| FR-2: GROUP derived by calling `derive_group(d["path"], codex_dir)` | US-1, US-2 |
| FR-3: TYPE column not shown in tabular output | US-1 |
| FR-4: Column widths determined automatically by `_format_table` | US-1 |
| FR-5: `lore codex list --json` includes `"group"` field per record | US-2 |
| FR-6: JSON structure uses `{"codex": [...]}` envelope pattern | US-2 |
| FR-7: Behaviour of `lore codex list` matches `lore knight list` / `lore doctrine list` / `lore watcher list` | US-1 |
| FR-8: No changes to `derive_group` in `paths.py` or `_format_table` in `cli.py` | US-1, US-2 |
| Workflow: Listing codex documents — Developer | US-1 |
| Workflow: Consuming codex list output programmatically — Automation script | US-2 |

---

## Summary

| Total stories | Epics | Draft | Final |
|---------------|-------|-------|-------|
| 2 | 1 | 0 | 2 |
