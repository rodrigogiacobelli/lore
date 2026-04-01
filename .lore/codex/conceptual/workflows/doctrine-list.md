---
id: conceptual-workflows-doctrine-list
title: lore doctrine list Behaviour
summary: What the system does internally when `lore doctrine list` runs — recursive discovery of `.yaml` files under `.lore/doctrines/`, validation with INVALID suffix for failing doctrines, metadata fallback rules, group derivation, and table or JSON output.
related: ["conceptual-entities-doctrine", "conceptual-workflows-doctrine-new", "conceptual-workflows-knight-list", "tech-cli-commands"]
stability: stable
---

# `lore doctrine list` Behaviour

`lore doctrine list` discovers and displays all doctrine YAML files found recursively under `.lore/doctrines/`. Unlike `lore knight list`, it validates each doctrine against the schema and visually marks invalid ones in the table output. It never aborts due to a single malformed file.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- `.lore/doctrines/` may or may not exist. If it does not exist, the command returns an empty result.

## Steps

### 1. Locate the doctrines directory

The path `.lore/doctrines/` is derived from the project root. If the directory does not exist, an empty list is returned immediately.

### 2. Discover doctrine files

All files matching `*.yaml` are found recursively (`rglob`) under `.lore/doctrines/`. This includes files in subdirectories such as `default/`. Files are discovered in sorted filesystem order (by path).

### 3. Validate and parse each file

For each discovered `.yaml` file, two independent parse passes are performed:

**Pass A — raw YAML read:** The file is read and parsed as YAML. If this fails or produces a non-dict, an empty dict is used for metadata extraction.

**Pass B — doctrine validation:** `load_doctrine()` is called, which validates the full schema (required fields, name-matches-filename, step structure, no cycles). If validation succeeds, `valid = True` and the `description` field comes from the loaded doctrine. If validation fails with a `DoctrineError`, `valid = False`, the error message is stored in `errors`, and `description` falls back to the raw YAML `description` field (or empty string). If YAML parsing itself fails, `valid = False` and `errors = ["Failed to parse YAML"]`.

**Field extraction and fallback rules:**

| Field | Source | Fallback |
|---|---|---|
| `id` | `raw["id"]` (stringified) | filename stem |
| `title` | `raw["title"]` (stringified) | value of `id` |
| `summary` | `raw["summary"]` if present; else `description` truncated to ~80 chars | empty string |
| `group` | derived from subdirectory path | empty string |
| `valid` | result of schema validation | `False` |

The `summary` truncation: if `description` is used as fallback and is longer than 80 characters, it is trimmed at a word boundary and `...` is appended.

### 4. Derive the group

Identical to `lore knight list`: directory components between `.lore/doctrines/` and the file are joined with dashes.

### 5. Render output

**Table mode (default):**

A fixed-width table is printed with four columns: `ID`, `GROUP`, `TITLE`, `SUMMARY`. For invalid doctrines, the SUMMARY cell has ` [INVALID]` appended.

Example row for an invalid doctrine:
```
  broken-doctrine  default  broken-doctrine  Missing required field: steps [INVALID]
```

If no doctrines are found, the single message `No doctrines found.` is printed.

**JSON mode (`--json`):**

The `--json` flag is accepted both as a local subcommand flag (`lore doctrine list --json`) and as the global flag (`lore --json doctrine list`). Both produce identical output. The local flag is declared at the `doctrine list` subcommand level, matching the pattern of `lore artifact list --json`.

```json
{
  "doctrines": [
    {"id": "...", "group": "...", "title": "...", "summary": "...", "valid": true},
    ...
  ]
}
```

Invalid doctrines appear in the array with `"valid": false`. Their summary does not include `[INVALID]` in JSON mode (that suffix is table-only). Exit code 0 in all cases.

## Failure Modes

`lore doctrine list` has no documented failure modes that produce a non-zero exit code. Invalid YAML files appear with `valid: false`. A non-existent doctrines directory produces an empty result, not an error.

## Working With JSON Output

To filter only valid doctrines using `jq`:

```
$ lore doctrine list --json | jq '.doctrines[] | select(.valid == true)'
```

To get a list of valid doctrine IDs only:

```
$ lore doctrine list --json | jq -r '.doctrines[] | select(.valid) | .id'
```

Always check the `valid` field before using a doctrine programmatically — an invalid doctrine may have incomplete or missing step data.

For human review, use the table mode (`lore doctrine list`) — the `[INVALID]` suffix is immediately visible without needing to parse JSON.

## Out of Scope

- Filtering by validity, group, or id at the CLI level — use `jq` in the consuming process.
- Showing doctrine step details — use `lore doctrine show <name>` for that.

## Related

- conceptual-workflows-knight-list (lore codex show conceptual-workflows-knight-list) — mirrors this behaviour for knights (no validation step)
- conceptual-workflows-artifact-list (lore codex show conceptual-workflows-artifact-list) — stricter: skips files missing required fields
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
