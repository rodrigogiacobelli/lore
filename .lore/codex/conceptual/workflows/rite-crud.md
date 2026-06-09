---
id: conceptual-workflows-rite-crud
title: Rite CRUD Operations
summary: What the system does internally when creating, editing, and deleting rites via the CLI — name and --group validation, schema validation before write, whole-tree (recursive main+shared) id-uniqueness detection, the --group placement on new, the --shared switch, id-based recursive resolution for edit/delete, soft-delete by .yaml.deleted rename, the group-bearing JSON envelopes, and the exact success/error messages and exit codes.
binds:
- src/lore/rite.py
- src/lore/cli.py
- src/lore/validators.py
- tests/e2e/test_rite_crud.py
- tests/unit/test_rite.py
related:
  - conceptual-entities-rite
  - conceptual-workflows-rite-list
  - conceptual-workflows-rite-show
  - conceptual-workflows-watcher-crud
  - conceptual-workflows-error-handling
  - conceptual-workflows-json-output
  - decisions-011-api-parity-with-cli
  - decisions-015-rites-writable-file-entity
  - decisions-016-rite-json-envelope-omits-group
  - tech-arch-schemas
  - ref-lore_cli-commands
---

# Rite CRUD Operations

Rites are a **writable** file entity with full CRUD (unlike the read-only codex —
see decisions-015-rites-writable-file-entity). `lore rite new`, `lore rite edit`,
and `lore rite delete` manage them, mirroring the watcher CRUD pattern
(conceptual-workflows-watcher-crud). Each CLI command is a thin wrapper over a
self-contained `lore.api` function (ADR-011); `--shared` selects the shared-step
subfolder instead of the default `main/`.

## Preconditions

- The Lore project has been initialised.
- Rite `name` must match `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` (same rule as
  knight/doctrine/watcher/artifact, enforced by `validate_rite_id` in
  `lore.validators`).
- For `new`/`edit`, body content is provided via `--from <path>` or stdin.

## Name and Content Validation

- **Name** — `validate_rite_id(name)`: must start alphanumeric; letters, digits,
  hyphens, underscores only; no spaces, dots, or slashes (the id is BARE — never
  path-qualified). Failure: `Invalid name: must be alphanumeric, hyphens,
  underscores only.`, exit 1. Checked before any filesystem access.
- **Group** — `validate_group(group)` validates the optional `--group` path
  separately (slash-delimited segments, no `..`, no leading/trailing slash),
  exactly like the other `--group` flags. Failure: `invalid group '<g>': …`, exit 1.
- **Body** — validated against the JSON Schema before write: `main-rite` for a
  main rite, `shared-step` for a shared step (tech-arch-schemas). Both schemas are
  `additionalProperties: false`, so an outbound `related`/`binds` key, or a
  shared step carrying `nodes`/`then`/`conclusions`, is rejected as a schema
  error.

## Steps — Create (`lore rite new <name> [--shared] [--group <path>] --from <path>`)

The CLI parses `--from`/stdin, `--shared`, and `--group`, then calls
`create_rite(rites_dir, name, content, shared=shared, group=group)`. All
validation, duplicate detection, and writing happen inside the core helper.

1. **Validate name and group** — `validate_rite_id` (bare id) and
   `validate_group` (the `--group` path). On failure, error to stderr, exit 1.
2. **Read content** — `--from <file>` (missing → `File not found: <path>`, exit
   1) or stdin (empty → `No content provided on stdin.`, exit 1).
3. **Validate the YAML body** against `main-rite` (default) or `shared-step`
   (`--shared`) before any write. Schema-invalid → error, exit 1; content is not
   written.
4. **Whole-tree id-uniqueness detection** — the id must be unique across the
   ENTIRE `main/` + `shared/` tree, every subfolder (a duplicate id anywhere
   would make `use: x` ambiguous). A clash → `Rite "<name>" already exists.`,
   exit 1.
5. **Write** the body to `.lore/rites/main/[<group>/]<name>.yaml` (default) or
   `.lore/rites/shared/[<group>/]<name>.yaml` (`--shared`); `--group` is optional
   (root if omitted).

**Success (text):** `Created rite main/[<group>/]<name>.yaml` / `Created shared
step shared/[<group>/]<name>.yaml`.
**JSON:** `{"id": "<name>", "kind": "main", "group": <group-or-null>, "filename":
"<name>.yaml", "path": ".lore/rites/main/[<group>/]<name>.yaml"}` (`kind` is
`"shared"` and path under `shared/` with `--shared`). The `group` key **IS**
carried (root → `null`), like every other entity
(decisions-016-rite-json-envelope-omits-group).

## Steps — Edit (`lore rite edit <id> [--shared] [--from <path>]`)

`update_rite(rites_dir, id, content, shared=shared)` replaces an existing rite's
body. It **refuses create-via-edit** — the rite must already exist. The target is
located by its **bare id** via a recursive scan of the whole tree (mirroring how
watcher edit does an rglob lookup, conceptual-workflows-watcher-crud); `--shared`
selects the schema, not the lookup.

1. **Validate id and find file by id** (recursive). Not found → `Rite "<id>" not
   found`, exit 1.
2. **Read new content** — same `--from`/stdin logic as create.
3. **Re-validate** the body against the relevant schema before write.
4. **Overwrite in place** — the file stays in its original subfolder.

**Success (text):** `Updated rite <id>` / `Updated shared step <id>`.
**JSON:** the full updated entity object (the parsed rite/step dict), matching
`lore edit`'s "full updated entity object" envelope.
**No source provided:** Click `UsageError`: `No content provided: pass --from
<path> or pipe via stdin.`, **exit 2** (parity with `lore edit`'s no-flags rule).

## Steps — Delete (`lore rite delete <id>`)

`delete_rite(rites_dir, id)` locates the rite by its **bare id** via a recursive
scan, then soft-deletes by renaming `<id>.yaml` to `<id>.yaml.deleted` (watcher
precedent, ADR-003). The deleted rite becomes invisible to
scan/list/show/search/health. `--shared` is accepted for parity but does not
affect the id-based lookup.

**Success (text):** `Deleted rite <id>` / `Deleted shared step <id>`.
**JSON:** `{"id": "<id>", "group": <group-or-null>, "deleted_at": "<ts>"}`
(mirrors `lore delete`, plus the resolved `group`).
**Idempotency:** deleting an already-deleted or absent rite → `Rite "<id>" not
found`, exit 1. There is no "already deleted" success path for rites (parity with
watcher delete).

## Python API

```python
from lore.api import create_rite, update_rite, delete_rite, RiteError
from pathlib import Path

rites_dir = Path(".lore/rites")
create_rite(rites_dir, "issue-refund", body_yaml)               # main rite
create_rite(rites_dir, "read-contact-info", step_yaml, shared=True)
update_rite(rites_dir, "issue-refund", new_body_yaml)
delete_rite(rites_dir, "issue-refund")
```

Each raises `RiteError` (subclass of `ValueError`) on bad input. CLI and Python
behaviour are byte-identical (ADR-011).

## Failure Modes

| Failure point | Message (stderr) | Exit code |
|---|---|---|
| Invalid name (new/edit/delete) | `Invalid name: must be alphanumeric, hyphens, underscores only.` | 1 |
| Invalid `--group` path (new) | `invalid group '<g>': <reason>` | 1 |
| Duplicate id (anywhere in the tree, on new) | `Rite "<name>" already exists.` | 1 |
| `--from` file missing | `File not found: <path>` | 1 |
| Empty stdin | `No content provided on stdin.` | 1 |
| Schema-invalid body | `Invalid rite: <rule> at <pointer> — <message>` (first violation) | 1 |
| Shared step with branching/conclusions | `Invalid shared step: additionalProperties at /<key> — unknown key` (a schema-invalid case) | 1 |
| Rite not found (edit/delete) | `Rite "<name>" not found` | 1 |
| Edit with no source given | `No content provided: pass --from <path> or pipe via stdin.` (Click UsageError) | 2 |

JSON form of every error: `{"error": "<the message>"}` to stderr.

## Out of Scope

- Hard delete — delete is always a soft-delete rename.
- Moving a rite between subfolders via edit — edit overwrites in place and does
  not move files; reorganise by hand and rely on id-based resolution.

## Related

- conceptual-entities-rite (lore codex show conceptual-entities-rite) — what a Rite is and its lifecycle
- conceptual-workflows-watcher-crud (lore codex show conceptual-workflows-watcher-crud) — the CRUD pattern this mirrors
- decisions-015-rites-writable-file-entity (lore codex show decisions-015-rites-writable-file-entity) — why rites are writable
- decisions-016-rite-json-envelope-omits-group (lore codex show decisions-016-rite-json-envelope-omits-group) — recursive grouping + the group-bearing envelope
- tech-arch-schemas (lore codex show tech-arch-schemas) — the main-rite / shared-step schema contract
- ref-lore_cli-commands (lore codex show ref-lore_cli-commands) — full CLI reference
