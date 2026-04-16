---
id: conceptual-workflows-json-output
title: JSON Output Mode
summary: 'What the system does when the --json flag is applied to any command — envelope
  structure, field contracts, error JSON format, and global vs local flag position.

  '
related:
- conceptual-workflows-error-handling
- tech-cli-commands
---

# JSON Output Mode

Passing `--json` before any subcommand switches Lore's output to structured JSON. This is the primary interface for programmatic consumers (orchestrators, scripts).

## Flag Position

`--json` is a **global flag** on the `lore` root command and must appear before the subcommand:

```bash
lore --json claim q-xxxx/m-yyyy    # correct
lore claim --json q-xxxx/m-yyyy    # incorrect — not recognised
```

Several subcommands also accept a local `--json` flag at the subcommand level. The following subcommands support `lore <subcommand> --json`:

- `lore show`
- `lore unneed`
- `lore artifact list`
- `lore knight list`
- `lore doctrine list`

For these commands, the local flag and the global flag produce identical output. Double-declaration (`lore --json knight list --json`) is harmless.

## Success Envelopes

Each command documents its own JSON shape. Common patterns:

| Command | Success envelope |
|---|---|
| `lore new quest` | `{"id": "q-xxxx"}` |
| `lore new mission` | `{"id": "q-xxxx/m-yyyy"}` |
| `lore claim` | `{"updated": [...], "quest_status_changed": [...], "errors": []}` |
| `lore done` | `{"updated": [...], "quest_closed": [...], "errors": []}` |
| `lore block` | `{"id": "...", "status": "blocked", "block_reason": "..."}` |
| `lore list` | `{"quests": [{id, title, status, priority, created_at}]}` |
| `lore missions` | `{"missions": [{id, quest_id, title, status, priority, mission_type, knight, created_at}]}` |
| `lore ready` | `{"missions": [{id, quest_id, title, status, priority, mission_type, knight, created_at}]}` |
| `lore stats` | `{"quests": {...}, "missions": {...}}` |
| `lore show <quest>` | Full quest object with nested missions and board |
| `lore show <mission>` | Full mission object with dependencies and board |
| `lore needs` | `{"created": [...], "existing": [...], "errors": []}` |
| `lore unneed` | `{"removed": [...], "not_found": [...], "errors": [...]}` |
| `lore board add` | `{"id": N, "entity_id": "...", "sender": "...", "created_at": "..."}` |
| `lore board delete` | `{"id": N, "deleted_at": "..."}` |
| `lore edit` | Full updated entity object |
| `lore delete` | `{"id": "...", "deleted_at": "..."}` |
| `lore artifact list` | `{"artifacts": [{id, group, title, summary}]}` — `group` is slash-joined when nested, `null` for root-level artifacts |
| `lore knight list` | `{"knights": [{id, group, title, summary}]}` — `group` is slash-joined when nested, `null` for root-level knights |
| `lore doctrine list` | `{"doctrines": [{id, group, title, summary, valid}]}` — `group` is slash-joined when nested, `null` for root-level doctrines |
| `lore watcher list` | `{"watchers": [{id, group, title, summary}]}` — `group` is slash-joined when nested, `null` for root-level watchers |
| `lore codex list` | `{"codex": [{id, group, title, summary}]}` — `group` is slash-joined when nested, `null` for root-level documents |
| `lore doctrine new` | `{"name", "group", "yaml_filename", "design_filename", "path"}` — `group` slash-joined or `null` |
| `lore knight new` | `{"name", "group", "filename", "path"}` — `group` slash-joined or `null` |
| `lore watcher new` | `{"id", "group", "filename", "path"}` — `group` slash-joined or `null` |
| `lore artifact new` | `{"id", "group", "filename", "path"}` — `group` slash-joined or `null` |

## Error JSON Format

Errors are written to **stderr** (not stdout). The standard error envelope is:

```json
{"error": "<human-readable message>"}
```

Some commands extend the error envelope with additional fields. For example:

- Soft-deleted entity on edit: `{"error": "...", "deleted_at": "..."}`
- Quest not found with deletion timestamp: `{"error": "...", "deleted_at": "..."}`

## Exit Codes

The exit code contract is the same in JSON mode as in text mode:

- `0` — success (or idempotent no-op).
- `1` — at least one error occurred.

For multi-entity commands (`claim`, `done`, `needs`, `unneed`), exit code `1` is used if the `errors` array in the JSON envelope is non-empty.

## Field Presence Contracts

All fields in documented envelopes are always present, even when the value is `null`. Consumers should not treat absent fields as `null` — absence means the field was not part of the contract for that command version.

### Group key canonical form

For every entity with a `group` field in the JSON envelope (the five `list` commands plus the four `new` commands), the canonical form is:

- `null` — entity lives directly at the entity root (`.lore/<entity>/<name>.*`).
- slash-joined string (e.g., `"seo-analysis/keyword-analysers"`) — entity lives in a nested subdirectory under the entity root.

JSON never emits an empty string `""` for `group`, and never emits the legacy hyphen-joined form (e.g., `"default-codex"`). Consumers must treat the hyphen form as invalid input.

## Commands That Do Not Support JSON

`lore oracle` does not produce JSON output. The `--json` flag is accepted but has no effect.

`lore init` always produces text output regardless of the flag.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Flag placed after subcommand | Flag silently ignored for most commands; accepted and acts correctly for `lore show`, `lore unneed`, `lore artifact list`, `lore knight list`, and `lore doctrine list` | varies |
| Oracle with --json | Flag ignored; text output produced | 0 |
