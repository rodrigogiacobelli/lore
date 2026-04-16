---
id: conceptual-workflows-error-handling
title: CLI Error Handling
summary: 'What the system does when CLI commands encounter errors — exit codes, stderr
  vs stdout routing, JSON error format, and exception paths.

  '
related:
- conceptual-workflows-json-output
- tech-cli-commands
---

# CLI Error Handling

Lore's CLI follows consistent conventions for surfacing errors to callers. Understanding these conventions is essential for writing correct E2E tests.

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success (including idempotent no-ops) |
| 1 | At least one error occurred |

Idempotent successes always return 0, even when no database write occurred (e.g., claiming an already-`in_progress` mission).

## stdout vs stderr Routing

- **Successful output** goes to **stdout**.
- **Error messages** go to **stderr** (`click.echo(..., err=True)`).
- In JSON mode, error envelopes are also written to **stderr**.

This allows callers to capture stdout for structured data parsing while checking stderr for errors independently.

## JSON Error Format

All error output in JSON mode uses one of two shapes:

Single-entity error (command processes one entity at a time):

```json
{"error": "<message>"}
```

Some commands extend the error envelope:

```json
{"error": "<message>", "deleted_at": "<timestamp>"}
```

Multi-entity commands (`claim`, `done`, `needs`, `unneed`) collect errors in an `errors` array within the success envelope:

```json
{"updated": [...], "errors": ["<message1>", "<message2>"]}
```

Exit code is `1` if `errors` is non-empty.

## `ClickException` vs Manual Exit

- `raise click.ClickException(message)`: formats `Error: <message>` to stderr, exits with code 1. Used for programmer-error-level failures (bad priority value).
- `click.UsageError(message)`: formats `Error: <message>` to stderr with usage hint, exits with code 2. Used for invalid option combinations.
- `click.echo(message, err=True); ctx.exit(1)`: used for entity-not-found and status-transition errors (allows multi-entity commands to continue processing).

## Project-Not-Found Error

If `lore` is run outside an initialised project directory (and the command is not `init`), the error is:

```
Not a Lore project: no .lore/ directory found.
```

In JSON mode: `{"error": "Not a Lore project: no .lore/ directory found."}` to stderr. Exit code 1.

## Multi-Entity Error Handling

Commands that accept multiple IDs (`claim`, `done`, `needs`, `unneed`) process each ID independently:

1. If an ID fails, its error is printed to stderr (text mode) or added to `errors` (JSON mode).
2. Processing continues for remaining IDs.
3. After all IDs are processed, exit code is set to 1 if any failed.

## Soft-Deleted Entity Annotations

When a requested entity exists in the database but has been soft-deleted, the error message includes the deletion timestamp:

```
Mission "q-xxxx/m-yyyy" not found (deleted on 2026-03-24T12:00:00Z)
```

JSON: `{"error": "...", "deleted_at": "2026-03-24T12:00:00Z"}`.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Project not initialised | Error to stderr | 1 |
| Invalid option combination | `UsageError` to stderr | 2 |
| Entity not found | Error to stderr | 1 |
| Wrong status for operation | Error to stderr | 1 |
| DB integrity error | Exception propagates; unhandled error | 1 |

## Out of Scope

- Retry logic — errors are surfaced immediately; callers decide whether to retry.
- Error codes beyond 0/1/2 — Lore does not use error codes to distinguish error types.
