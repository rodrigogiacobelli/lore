---
id: technical-test-guidelines
title: Test Authorship Guidelines
summary: >
  Defines the two-tier test model (unit vs E2E), naming conventions, codex
  anchoring rules for E2E tests, prohibited patterns, and how to add new tests.
  This is the source of truth for all test authorship in this project.
related: ["tech-arch-source-layout", "tech-overview", "decisions-006-no-seed-content-tests"]
stability: stable
---

## 1. Purpose

This project uses a two-tier test model:

- **Unit tests** verify internal module logic in isolation.
- **E2E tests** verify user-visible CLI behaviour end-to-end.

The two tiers are physically separated into `tests/unit/` and `tests/e2e/`. They serve different purposes and follow different conventions — mixing them degrades the signal of both.

The codex is the spec for E2E tests. Before writing an E2E test, the workflow it covers must already exist as a `conceptual-workflows-*` codex document. Write the doc first, then write the test.

## 2. The Two Tiers

### Unit tests (`tests/unit/`)

- Import from `lore.*` modules directly — never from `lore.cli`.
- No `CliRunner`, no `project_dir` fixture, no `lore init`.
- Test functions, methods, and classes in isolation.
- May use the `bare_lore_dir` fixture (defined in `tests/unit/conftest.py`) for modules that interact with the file system.

### E2E tests (`tests/e2e/`)

- Invoke the CLI via `CliRunner`, or call `lore.db` functions against a real project directory.
- Each file tests exactly one workflow.
- Require the `project_dir` fixture from the root `tests/conftest.py`.

## 3. Codex Anchoring Rule

Every `tests/e2e/test_*.py` file must:

1. Cite exactly one `conceptual-workflows-*` codex ID in its module docstring.
2. Only test behaviour described by that codex document.
3. Be written **after** its codex document exists.

Module docstring template:

```python
"""E2E tests for <behaviour description>.

Spec: <codex-id> (lore codex show <codex-id>)
"""
```

To add a new E2E test, first run:

```
lore codex search workflow
```

If no doc exists for the behaviour, write the codex document first, then write the test.

## 4. File Naming

- **Unit:** `tests/unit/test_<module_name>.py` — one file per source module in `src/lore/`.
- **E2E:** `tests/e2e/test_<slug>.py` where slug is the codex ID with the `conceptual-workflows-` prefix stripped.

Examples:

| Codex ID | Test file |
|---|---|
| `conceptual-workflows-claim` | `tests/e2e/test_claim.py` |
| `conceptual-workflows-python-api` | `tests/e2e/test_python_api.py` |

## 5. Class and Method Naming

- **Unit class:** `TestFunctionName` or `TestClassName` — named after the thing under test.
- **E2E class:** `TestBehaviorDescription` — describes the scenario.
- **Test methods:** `test_<what_it_does>` in both tiers.

**Prohibited in all names and docstrings:**

- `SCENARIO-NNN` — no scenario numbers.
- `TestAC<N>_*` — no acceptance criteria numbers.
- `US-N` references — no user story numbers.
- File names starting with `test_us<N>_`.

## 6. Prohibited Patterns

The following patterns are forbidden across the entire test suite:

| Location | Forbidden pattern |
|---|---|
| File names | `test_us<N>_*.py` |
| Class names | `TestAC<N>_*`, `TestUS<N>*` |
| Comments / docstrings | `SCENARIO-NNN`, `US-N`, `AC-N`, "Tests for US-N", "covers US-N" |
| Unit test files | `from lore.cli import main` |
| Any test file | Locally defined `runner` or `project_dir` fixtures (use root conftest) |
| Any test file | Asserting specific field values from seed default files (`src/lore/defaults/`) — only existence, parseability, and structural presence of required keys are valid targets (see ADR 006) |

## 7. conftest.py Layout

```
tests/conftest.py          # shared: runner, project_dir, db_conn, insert_*, assert_exit_*, parse_json_id, extract_*
tests/unit/conftest.py     # bare_lore_dir fixture for file-system module testing
tests/e2e/conftest.py      # scenario-level fixtures (pre-populated quests/missions) as needed
```

No other `conftest.py` files are permitted. All helper functions in the root conftest are importable as `from tests.conftest import ...`.

## 8. How to Add New Tests

### Adding a unit test

1. Identify the source module (e.g., `src/lore/graph.py`).
2. Create or edit `tests/unit/test_graph.py`.
3. If the test needs to invoke the CLI, it belongs in `tests/e2e/` — move it there.

### Adding an E2E test

1. Run `lore codex search workflow`.
2. If no doc exists for the behaviour, write a `conceptual-workflows-<slug>.md` codex document first.
3. Create `tests/e2e/test_<slug>.py` with the module docstring citing the codex ID.
4. Name classes after the behaviour, not after SCENARIO or US numbers.
