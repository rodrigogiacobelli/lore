---
id: conceptual-workflows-watcher-list
title: lore watcher list Behaviour
summary: What the system does internally when `lore watcher list` and `lore watcher show` run — recursive YAML discovery under .lore/watchers/, field extraction with fallbacks, group derivation, sorted table or JSON output, and raw-YAML or structured-JSON show behaviour.
related:
  - conceptual-entities-watcher
  - conceptual-workflows-knight-list
  - conceptual-workflows-filter-list
  - tech-cli-commands
---

# `lore watcher list` Behaviour

`lore watcher list` discovers and displays all watcher YAML files found recursively under `.lore/watchers/`. It never fails due to a single malformed file — files that cannot be parsed fall back to defaults rather than being skipped or causing an error.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- `.lore/watchers/` may or may not exist. If it does not exist, the command returns an empty result.

## Steps — `lore watcher list`

### 1. Locate the watchers directory

The path `.lore/watchers/` is derived from the project root via `watchers_dir(root)` in `paths.py`. If the directory does not exist, an empty list is returned immediately.

### 2. Discover watcher files

All files matching `*.yaml` are found recursively (`rglob`) under `.lore/watchers/`. Soft-deleted files (`.yaml.deleted` suffix) are not matched and are excluded automatically.

### 3. Parse each file

Each discovered `.yaml` file is read via `yaml.safe_load`. Required fields (`id`, `title`, `summary`) fall back to the filename stem or empty string when absent or unparseable. Optional fields (`watch_target`, `interval`, `action`) default to `None` when absent.

**Field extraction and fallback rules:**

| Field | Source | Fallback |
|-------|--------|----------|
| `id` | `yaml["id"]` (stringified) | filename stem |
| `title` | `yaml["title"]` (stringified) | value of `id` |
| `summary` | `yaml["summary"]` (stringified) | empty string |
| `group` | derived from subdirectory path | empty string (file is in watchers root) |
| `watch_target` | `yaml["watch_target"]` | `None` |
| `interval` | `yaml["interval"]` | `None` |
| `action` | `yaml["action"]` | `None` |

### 4. Derive the group

The `group` for each watcher is derived from the subdirectory path between `.lore/watchers/` and the file. Directory components are joined with `/`.

Examples:
- `.lore/watchers/run-tests-on-push.yaml` → group: `""` (empty; rendered as the sentinel in the table and `null` in JSON)
- `.lore/watchers/default/change-log-updates.yaml` → group: `default`
- `.lore/watchers/feature-implementation/on-prd-ready.yaml` → group: `feature-implementation`

### 5. Apply filter (when `--filter` is provided)

When one or more `--filter GROUP` tokens are supplied, the parsed watcher list is post-filtered using segment-prefix matching on the slash-delimited group form:

- Each supplied token is split on `/`; the watcher's `group` is split on `/`. The token matches when its segments are a proper prefix of the watcher's segments. For example, `--filter feature-implementation` matches both `feature-implementation` and any nested subgroup like `feature-implementation/ci`.
- The hyphen-delimited input grammar (`default-ci`) is no longer accepted — see conceptual-workflows-filter-list for the breaking-change specification.
- Watchers with `group == ""` (root-level files, directly under `.lore/watchers/`) are **always** included regardless of filter tokens.
- Unrecognised tokens produce no error — they simply match nothing.
- When `--filter` is not provided, all watchers are returned (existing behaviour preserved).

Optional fields (`watch_target`, `interval`, `action`) are unaffected by filtering — the same fallback rules apply to all returned watchers.

See conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) for the full filter behaviour specification.

### 6. Sort results

All collected records are sorted alphabetically by the `id` field (ascending, case-sensitive).

### 7. Render output

**Table mode (default):**

A fixed-width table with four columns: `ID`, `GROUP`, `TITLE`, `SUMMARY`. Columns padded to the widest value.

```
  ID                    GROUP    TITLE                    SUMMARY
  change-log-updates    default  Update Changelog         Watches for merges to main and triggers the update-changelog doctrine
```

If no watchers are found, `No watchers found.` is printed.

**JSON mode (`--json`):**

```json
{"watchers": [
  {"id": "...", "group": "feature-implementation", "title": "...", "summary": "..."},
  {"id": "...", "group": null, "title": "...", "summary": "..."}
]}
```

The `group` key is slash-joined when the watcher lives in a subdirectory and `null` when it sits at the watchers root.

The `--json` flag is accepted both as a local subcommand flag (`lore watcher list --json`) and as the global flag (`lore --json watcher list`). Exit code 0 in all cases.

## Steps — `lore watcher show <id>`

### 1. Resolve the watcher

`find_watcher(watchers_dir, id)` searches recursively via `rglob(f"{id}.yaml")`. Returns `Path` or `None`. Raises `ValueError` for path-traversal attempts (names containing `/` or `\\`).

### 2. Plain mode — raw YAML output

The file content is read and printed byte-for-byte, including comments. This preserves the human-authored YAML exactly as written. This behaviour diverges from `lore knight show` (which outputs the markdown body) because watcher files are pure YAML, not markdown-with-frontmatter.

```yaml
id: change-log-updates
title: Update Changelog
summary: Watches for merges to main and triggers the update-changelog doctrine

watch_target: main
# Canonical interval examples: on_merge | on_file_change | daily
interval: on_merge
action: update-changelog
```

### 3. JSON mode — structured dict

`load_watcher(filepath)` is called to produce a structured dict. All 8 keys are always present. Absent optional fields serialize as `null`.

```json
{"id": "change-log-updates", "group": "default", "title": "Update Changelog", "summary": "Watches for merges to main and triggers the update-changelog doctrine", "watch_target": "main", "interval": "on_merge", "action": "update-changelog", "filename": "change-log-updates.yaml"}
```

The `group` key is slash-joined for watchers in a subdirectory and `null` for root-level watchers.

### 4. Not found

If the watcher is not found, an error is printed to stderr and exit code 1 is returned.

```
Watcher "nonexistent" not found in .lore/watchers/
```

JSON mode error (stderr): `{"error": "Watcher \"nonexistent\" not found in .lore/watchers/"}`

## Failure Modes

`lore watcher list` has no documented failure modes that produce a non-zero exit code. Files that cannot be parsed silently fall back to default field values. A non-existent watchers directory produces an empty result, not an error.

`lore watcher show` exits with code 1 if the watcher is not found.

## Related

- conceptual-entities-watcher (lore codex show conceptual-entities-watcher) — what a Watcher is
- conceptual-workflows-knight-list (lore codex show conceptual-workflows-knight-list) — mirrors this behaviour for knights
- conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) — full --filter flag behaviour specification
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
