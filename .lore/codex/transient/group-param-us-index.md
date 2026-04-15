---
id: group-param-us-index
title: User Story Index — --group param for lore entity creation
summary: Index and PRD coverage map for the nine user stories covering the --group parameter feature across doctrine, knight, watcher, and artifact creation, plus list display and filter grammar migration to slash-delimited tokens.
type: user-story-index
status: final
---

# --group param for `lore new` commands — User Story Index

**Author:** Business Analyst
**Date:** 2026-04-15
**Status:** final
**PRD:** `lore codex show group-param-prd`
**Tech Spec:** `lore codex show group-param-tech-spec`

---

## Stories by Epic

### Epic 1 — Entity creation: `--group` parameter

Delivers the `--group` option (and `group=` kwarg) on the four entity `new` commands, including the brand new `lore artifact new` subcommand, with auto-mkdir and subtree duplicate detection.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-001 | Doctrine new --group nested create | final | group-param-us-001 |
| US-002 | Knight new --group nested create and create_knight extraction | final | group-param-us-002 |
| US-003 | Watcher new --group nested create | final | group-param-us-003 |
| US-004 | Artifact new subcommand with --group | final | group-param-us-004 |

### Epic 2 — Python API parity: core helpers

Delivers the `validate_group` validator as the single path-traversal chokepoint, reusable by every entity helper, with zero `lore.*` imports.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-005 | validate_group validator with zero lore imports | final | group-param-us-005 |

### Epic 3 — List display + filter migration

Migrates the canonical in-memory group form to slash-joined across `derive_group`, every list renderer (table + JSON), and the `--filter` grammar, in lock-step.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-006 | paths.derive_group slash-joined canonical form | final | group-param-us-006 |
| US-007 | List GROUP display slash-joined in table and JSON envelope | final | group-param-us-007 |
| US-008 | --filter slash-delimited tokens with segment-prefix matching | final | group-param-us-008 |

### Epic 4 — Help + teaching

Enriches `--help` on the four `new` subcommands and the five `list` subcommands so AI agents discover the new flag and the new filter grammar through the CLI itself.

| ID | Title | Status | Codex ID |
|----|-------|--------|----------|
| US-009 | Enriched --help teaches --group and slash-delimited filter | final | group-param-us-009 |

---

## PRD Coverage Map

Every functional requirement and every user workflow from `group-param-prd` maps to at least one story below.

| PRD Requirement / Workflow | Story IDs |
|----------------------------|-----------|
| FR-1: `--group <path>` option on all four `new` commands | US-001, US-002, US-003, US-004 |
| FR-2: `--group` omission writes flat at entity root | US-001, US-002, US-003, US-004 |
| FR-3: Auto-mkdir intermediate directories with `parents=True, exist_ok=True` | US-001, US-002, US-003, US-004 |
| FR-4: Reject `..`, `\`, absolute, leading/trailing `/`, empty segments | US-005 |
| FR-5: Reject segments failing `_NAME_RE` character set | US-005 |
| FR-6: Subtree-wide duplicate detection via `rglob` | US-001, US-002, US-003, US-004 |
| FR-7: New `lore artifact new` subcommand writing `.lore/artifacts/[<group>/]<name>.md` | US-004 |
| FR-8: `create_doctrine`, `create_knight`, `create_watcher`, `create_artifact` accept `group=None` kwarg | US-001, US-002, US-003, US-004 |
| FR-9: `create_knight` extracted from `cli.py`; `create_artifact` newly added | US-002, US-004 |
| FR-10: New `validate_group` in `lore/validators.py` with zero `lore.*` imports | US-005 |
| FR-11: `paths.derive_group` returns slash-joined as single canonical form | US-006 |
| FR-12: `list` GROUP column renders `/` in human table (all five list commands) | US-007 |
| FR-13: `list --json` emits `group` with `/` separator, `null` for root | US-007 |
| FR-14: `--filter` accepts slash-delimited tokens, segment-prefix match; breaking change | US-008 |
| FR-15: `codex list` switches in lock-step with other four; no `codex new` | US-007, US-008 |
| FR-16: Enriched `--help` on four `new` subcommands teaches `--group` | US-009 |
| FR-17: Enriched `--help` on five `list` subcommands reflects slash-delimited filter grammar | US-009 |
| FR-18: Codex docs updated in lock-step with code | (covered by the implementation mission per PRD; not a BA story) |
| Workflow: Create a nested doctrine — AI orchestrator | US-001 |
| Workflow: Create a knight at the entity root — human developer | US-002 |
| Workflow: Create a nested watcher — AI orchestrator | US-003 |
| Workflow: Create a nested artifact — AI orchestrator | US-004 |
| Workflow: List + filter with slash-joined groups — any user | US-006, US-007, US-008 |
| Non-Functional Security: `validate_group` single chokepoint against path traversal | US-005 |
| Non-Functional Reliability: idempotent `mkdir(parents=True, exist_ok=True)` | US-001, US-002, US-003, US-004 |

---

## Summary

| Total stories | Epics | Draft | Final |
|---------------|-------|-------|-------|
| 9 | 4 | 0 | 9 |
