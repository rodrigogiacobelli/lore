---
id: example-standards-testing
title: Testing Standards
summary: Test types, scope, file location conventions, fixture and mock policy, and
  coverage requirements. Read before writing any test.
---

# Testing Standards

## Test Types and Scope

| Type | Scope | What it tests |
|------|-------|--------------|
| Unit | Single function or class | _Logic in isolation. No I/O, no database, no network._ |
| Integration | Multiple modules together | _Real database, real file system. No network._ |
| E2E | Full command or request | _The complete path: CLI entry point → database → output. Asserts exact output strings._ |

_Remove rows that don't apply. Add rows for other test types (e.g. snapshot, contract, load)._

## What to Test at Which Layer

_Be explicit about the boundary between test types for this project._

- **Unit tests cover:** _e.g. validation logic, ID generation, status transition rules, output formatting_
- **Integration tests cover:** _e.g. database queries, migration application, cross-module workflows_
- **E2E tests cover:** _e.g. every CLI command with its options, every user workflow in the conceptual docs_

> If behaviour is specified in a workflow or user story, there must be an E2E test for it. No exceptions.

## File Location Conventions

```
tests/
├── unit/       # Unit tests — mirror src/ structure
│   └── {module}/
│       └── test_{file}.py
├── integration/  # Integration tests
│   └── test_{feature}.py
└── e2e/        # E2E tests — one file per command group or domain
    └── test_{domain}.py
```

_Adjust to match the actual test directory structure._

## Fixture and Mock Policy

_What fixtures are provided? What is allowed to be mocked?_

> Example: An in-memory database fixture is provided in `conftest.py`. Never mock the database — use the in-memory fixture. External HTTP calls may be mocked. File system operations use `tmp_path`.

| What | Policy |
|------|--------|
| Database | _e.g. In-memory SQLite via conftest fixture. Never mock._ |
| External APIs | _e.g. Mock with responses library._ |
| File system | _e.g. Use tmp_path fixture._ |
| Time | _e.g. Freeze with freezegun where needed._ |

## Coverage Requirements

_What coverage is required? Where is it configured?_

> Example: 80% line coverage required. Run with `uv run pytest --cov=src --cov-fail-under=80`.

| Scope | Requirement |
|-------|------------|
| Overall | _e.g. ≥ 80% line coverage_ |
| New code | _e.g. 100% for new modules_ |
| Critical paths | _e.g. every CLI command must have an E2E test_ |
