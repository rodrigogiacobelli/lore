---
id: example-standards-code-conventions
title: Code Conventions
related: []
stability: stable
summary: >
  Language style guide, naming conventions, file organisation, import order,
  and comment policy for this project. All agents and contributors must follow these.
---

# Code Conventions

_These conventions are enforced on all code in this project. They are not suggestions._

## Language and Version

_State the language and the minimum supported version. Note any language features that are in use or explicitly forbidden._

> Example: Python ≥ 3.11. `match` statements and `tomllib` are in use. `walrus operator` is permitted. `exec` and `eval` are forbidden.

## Style Guide

_Name the style guide and linter configuration. Where is the linter config file?_

> Example: PEP 8 enforced by `ruff`. Configuration in `pyproject.toml` under `[tool.ruff]`. Run with `uv run ruff check .`.

| Rule | Value |
|------|-------|
| Line length | _e.g. 88 characters_ |
| Quote style | _e.g. double quotes_ |
| Import style | _e.g. absolute imports only_ |
| Trailing comma | _e.g. required in multi-line structures_ |

## Naming Conventions

| Concept | Convention | Example |
|---------|-----------|---------|
| Functions | _e.g. snake_case_ | `get_task_by_id` |
| Classes | _e.g. PascalCase_ | `TaskRepository` |
| Constants | _e.g. UPPER_SNAKE_CASE_ | `MAX_RETRIES` |
| Files | _e.g. snake_case_ | `task_commands.py` |
| Test files | _e.g. test_{module}.py_ | `test_task_commands.py` |
| Test functions | _e.g. test_{behaviour}_ | `test_task_new_rejects_empty_title` |

## File and Module Organisation

_How is the source tree organised? One class per file, or grouped by domain? What goes in `__init__.py`?_

> Example: One command group per module in `commands/`. `__init__.py` files are empty. Shared utilities go in `utils.py`.

## Import Order

_What is the required import order? Is there a tool that enforces it?_

> Example: stdlib → third-party → local. Blank line between groups. Enforced by `ruff --select I`.

## Comment and Docstring Policy

_When are comments required? What format for docstrings?_

> Example: Docstrings required on all public functions. One-line docstrings for simple functions; multi-line for complex ones. Inline comments only where logic is non-obvious. No comments that restate what the code does.
