---
id: conceptual-workflows-validators
title: Input Validation
summary: >
  What the system does internally when input validation runs — priority range checks, entity-ID format checks, message emptiness checks, and the wiring of lore.validators into the CLI and DB layers.
related: ["tech-arch-validators", "decisions-011-api-parity-with-cli", "standards-dry", "standards-single-responsibility"]
stability: stable
---

# Input Validation

`lore.validators` is a standalone, import-free utility module that provides all format and range validation for the CLI and DB layers. Validators return an error string on failure or `None` on success.

## Validator Inventory

### `validate_priority(priority)`

Accepts integers in `[0, 4]`. `None` is explicitly accepted (means "no priority specified"). Out-of-range values return:

```
Priority <N> is out of range; must be between 0 and 4.
```

Used in `lore new quest`, `lore new mission`, and `lore edit`.

### `validate_entity_id(eid)`

Accepts any of:
- `q-<4-6 hex>` — quest ID
- `m-<4-6 hex>` — standalone mission ID
- `q-<4-6 hex>/m-<4-6 hex>` — scoped mission ID

Hex characters are `[0-9a-f]`. IDs with uppercase hex, non-hex chars, or wrong lengths are rejected. Returns `'Invalid entity ID format: "<id>"'` on failure.

Used as the general entity validator (e.g., `lore board add`).

### `validate_mission_id(mid)`

Accepts only `m-<hex>` and `q-<hex>/m-<hex>`. A bare `q-<hex>` quest ID is rejected. Returns `'Invalid mission ID format: "<id>"'` on failure.

Used by: `lore claim`, `lore done` (mission branch), `lore block`, `lore unblock`, `lore unneed`.

### `validate_quest_id_loose(quest_id)`

Accepts `q-[a-z0-9]{4,8}` — a relaxed pattern that accepts non-hex characters. Used exclusively in `lore show` and `lore delete` quest paths to accommodate test-DB-inserted IDs that do not conform to the production hex format. Must not be used for new ID creation or standard user-facing validation.

### `validate_message(message)`

Returns `"Message cannot be empty."` if the message is empty or pure whitespace. Used by `add_board_message` in `lore.db`.

### `validate_name(name)`

Pattern: `^[a-zA-Z0-9][a-zA-Z0-9_-]*$`. Used for doctrine, knight, watcher, and artifact names. Returns `"Invalid name: must start with alphanumeric and contain only letters, digits, hyphens, underscores."` on failure.

### `validate_group(group)`

Signature: `validate_group(group: str | None) -> str | None`. Used on every entity `new` path (`doctrine new`, `knight new`, `watcher new`, `artifact new`) to validate the optional `--group <path>` parameter. Lives in `lore/validators.py` with zero `lore.*` imports per the dependency-inversion standard.

Accepts:
- `None` — no group supplied; the entity lands at the entity root.
- Slash-delimited relative path (e.g., `"seo-analysis/keyword-analysers"`) where each segment independently matches `_NAME_RE` (the same pattern as `validate_name`).

Rejects, each with a specific error message:
- Empty string `""` → `Error: invalid group '': must not be empty (use None for root)`
- Any `..` segment → `Error: invalid group '<value>': path traversal ('..') not allowed`
- Backslash anywhere → `Error: invalid group '<value>': backslash not allowed`
- Absolute-path prefix (`/x`) → `Error: invalid group '<value>': absolute paths not allowed`
- Trailing `/` (or leading `/` caught above) → `Error: invalid group '<value>': leading/trailing '/' not allowed`
- Empty segment (`a//b`) → `Error: invalid group '<value>': empty segment not allowed`
- Segment failing `_NAME_RE` → `Error: invalid group '<value>': segment '<seg>' must start with alphanumeric and contain only letters, digits, hyphens, underscores`

Used by: `lore.doctrine.create_doctrine`, `lore.knight.create_knight`, `lore.watcher.create_watcher`, `lore.artifact.create_artifact`. The CLI handlers are thin wrappers — group validation happens inside the core helpers, not in `cli.py`.

### `paths.derive_group` and `paths.group_matches_filter`

The shared helpers in `paths.py` are the single source of canonical group form:

- `derive_group(filepath, base_dir) -> str` returns `"/"`-joined segments (e.g., `"a/b/c"`), empty string for files at the entity root. This is the canonical in-memory group form consumed by every list renderer and JSON envelope.
- `group_matches_filter(group, filter_groups) -> bool` performs segment-prefix matching: both the group and each filter token are split on `/`, and a token matches when its segment list is a proper prefix of the group's segment list. Root-level records (`group == ""`) always match regardless of filter tokens.

## Wiring into CLI

CLI commands call validators before making any database access. On validation failure:

- **Text mode:** the error string is printed to stderr and the command exits with code 1.
- **JSON mode:** the error string is included in an `errors` array (multi-entity commands) or `{"error": "..."}` envelope.

The CLI helper `_validate_mission_id(entity_id, ctx)` wraps `validate_mission_id` and calls `ctx.exit(1)` on failure, returning `False` so callers can check and return early.

## Wiring into DB Layer

`add_board_message` in `lore.db` calls `validate_entity_id` and `validate_message` directly, returning `{"ok": False, "error": "..."}` dicts rather than raising exceptions. This keeps the DB layer self-contained and testable without going through the CLI.

`create_mission` and `create_quest` validate `priority` with a direct range check (`if not (0 <= priority <= 4): raise ValueError`).

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Priority out of range | Error string returned; ClickException raised | 1 |
| Invalid mission ID format | Error string returned; exit 1 | 1 |
| Invalid entity ID format | Error string returned; exit 1 | 1 |
| Empty board message | Error string returned from db layer; exit 1 | 1 |
| Invalid knight/doctrine/watcher/artifact name | Error string returned; exit 1 | 1 |
| Invalid group on any `new` command | `Error: invalid group '<value>': <reason>`; exit 1 | 1 |

## Out of Scope

- Server-side validation beyond format and range — semantic validation (e.g., "the referenced knight must exist") is handled in the CLI or DB layer, not in `lore.validators`.
- Schema-level DB constraints (e.g., `NOT NULL`) — these are enforced by SQLite, not `lore.validators`.
