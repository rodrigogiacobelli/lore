---
id: standards-separation-of-concerns
title: Separation of Concerns
stability: stable
summary: The CLI is a concern. Business logic is a different concern. They live apart. cli.py formats terminal I/O, db.py enforces database rules, validators.py defines validation rules. Mixing these concerns is a structural defect even when tests pass.
related: ["decisions-011-api-parity-with-cli", "tech-arch-source-layout", "tech-arch-validators"]
---

# Separation of Concerns

The CLI is a concern. Business logic is a different concern. They live apart. A layer should know how to do its job and nothing about how the layers around it do theirs. Mixing concerns — business logic in a CLI handler, presentation logic in a database function — is a structural defect even when the tests pass.

## Layer Responsibilities

| Layer | Module | Responsibility |
|---|---|---|
| CLI | `cli.py` | Translate between the terminal and the core. Parse arguments, format output, handle exit codes. Nothing else. |
| Database / business logic | `db.py` | Enforce database rules. Run queries, apply business constraints, return result dicts. |
| Validation | `validators.py` | Define validation rules. Return an error string on failure, `None` on success. Import nothing from `lore.*`. |
| Filesystem entities | `knight.py`, `doctrine.py`, `codex.py`, `artifact.py` | Handle file-based entity operations only. |

## Rule

A CLI handler must not contain business logic. If a CLI handler is doing more than parsing input and formatting output, the extra logic belongs in `db.py` or `validators.py`.

A `db.py` function must not format terminal output. If a database function is building strings for display, that logic belongs in `cli.py`.

## Why This Matters

`db.py` functions are public API (see `decisions-010-public-api-stability`). External consumers — Realm, user scripts — call them directly, bypassing the CLI entirely. Any business logic that lives only in `cli.py` is invisible to those consumers. Any display logic that lives in `db.py` pollutes the API with terminal-specific concerns.

## Violation Pattern

The most common violation is a CLI handler that validates input before calling `db.py`. The validation belongs in `validators.py`, called by `db.py`, not in the handler. See `decisions-011-api-parity-with-cli` for the full rationale.
