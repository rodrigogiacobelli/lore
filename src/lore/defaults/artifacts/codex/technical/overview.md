---
id: example-tech-overview
title: Technical Overview
related: []
stability: stable
summary: >
  Technology stack, project structure, and key architectural patterns.
  Start here before navigating to any other technical documentation.
---

# Technical Overview

_One paragraph. What kind of system is this (CLI tool, web app, API, library, etc.)? What does it run on? What are the key architectural properties (local-first, stateless, event-driven, etc.)?_

## Stack

| Component | Technology | Version | Notes |
|-----------|-----------|---------|-------|
| Language | _e.g. Python_ | _≥ 3.11_ | _Key language features in use_ |
| Framework | _e.g. Click, FastAPI_ | _≥ x.y_ | _What it provides_ |
| Database | _e.g. SQLite, PostgreSQL_ | _version_ | _Key configuration_ |
| Testing | _e.g. pytest_ | _≥ x.y_ | _Test isolation approach_ |
| Package manager | _e.g. uv, pip_ | _latest_ | _Lock file location_ |

> Add, remove, or rename rows to match the actual stack. Remove rows for components that do not exist (e.g. remove Database if the project has no persistence layer).

## Project Structure

```
{project-root}/
├── {config-file}          # _description_
├── {lock-file}            # _description_
├── {source-dir}/
│   ├── __init__.py
│   ├── {entry-point}      # _description_
│   └── {key-module}/
│       └── {file}         # _description_
└── tests/
    ├── {conftest}         # _description_
    └── {test-file}        # _description_
```

> Replace with the actual project structure. Keep it at the level of directories and key files — not exhaustive.

## Key Architectural Patterns

_Describe two or three patterns that cut across the codebase. Examples: "all database access goes through db.py", "errors are raised as click.ClickException", "all writes use BEGIN IMMEDIATE transactions"._

### {Pattern 1}

_Description. Why it exists. Where to find examples._

### {Pattern 2}

_Description._

## {Other Important Concept}

_Add a section for any architectural property that doesn't fit above: concurrency model, caching strategy, offline behaviour, etc._
