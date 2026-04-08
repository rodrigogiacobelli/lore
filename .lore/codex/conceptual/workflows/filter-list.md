---
id: conceptual-workflows-filter-list
title: "lore * list --filter Behaviour"
summary: "What the system does when --filter GROUP... is passed to the list subcommand of codex, artifact, knight, doctrine, or watcher commands — subtree token-to-group matching (exact or prefix), root-level file inclusion, Python API parity, and unchanged unfiltered behaviour."
related:
  - conceptual-workflows-artifact-list
  - conceptual-workflows-knight-list
  - conceptual-workflows-doctrine-list
  - conceptual-workflows-watcher-list
  - conceptual-workflows-codex
  - tech-cli-commands
  - decisions-011-api-parity-with-cli
stability: stable
---

# `lore * list --filter` Behaviour

The `--filter GROUP...` flag is available on the `list` subcommand of all five entity list commands: `lore codex list`, `lore artifact list`, `lore knight list`, `lore doctrine list`, and `lore watcher list`. It limits output to entities in the specified namespace group(s) while always including root-level files.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- The caller knows the group token(s) to filter on. Group tokens correspond to subdirectory names joined with hyphens (e.g., `technical-api` maps to `technical/api/`). A token also matches all deeper subgroups — `technical` matches `technical-api`, `technical-reference`, etc.

## Steps (applied identically across all five list commands)

### 1. Discover all entities (unchanged)

The command performs its normal recursive discovery (e.g., `rglob("*.md")` for knights, `rglob("*.yaml")` for doctrines and watchers). No change to discovery or validation logic — the full entity list is assembled exactly as without `--filter`.

### 2. Derive groups (unchanged)

Each entity's `group` is derived from its subdirectory path using `derive_group` in `paths.py`. Directory components between the base directory and the file are joined with hyphens. Files directly in the base directory have `group == ""` (empty string).

### 3. Apply filter (post-discovery)

When `--filter` is provided with one or more tokens, the assembled list is filtered using subtree (prefix) matching:

**Key rules:**
- A record is included if its `group` exactly equals any supplied token **or** starts with `token + "-"` (subtree match).
- Records where `group == ""` (root-level files) are **always** included regardless of filter tokens.
- If a token matches no entity group, no entities from that token are returned — no error is raised.
- Multiple tokens use OR logic: an entity matching any token is included.
- An empty list `[]` for `filter_groups` is treated identically to `None` — no filtering.
- The hyphen boundary is critical: token `technical` matches `technical-api` but does not match a hypothetical group `technicalstuff`.

### 4. Render output (unchanged)

Filtered output uses the same table and JSON schema as unfiltered output. No new fields, no structural changes. The command renders only the filtered records.

For `doctrine list` and `artifact list`, the valid/invalid counts and `[INVALID]` suffix apply only to the filtered records returned.

## Token Format

A group token is a string where hyphens represent path separators. A token matches the named group **and all of its subgroups** (subtree semantics):

| Token | Matches groups | Matches files in |
|-------|---------------|-----------------|
| `conceptual` | `conceptual`, `conceptual-workflows`, `conceptual-reference`, … | `.lore/codex/conceptual/` and all subdirectories |
| `technical-api` | `technical-api`, `technical-api-v2`, … | `.lore/codex/technical/api/` and all subdirectories |
| `default-codex` | `default-codex`, `default-codex-sub`, … | `.lore/artifacts/default/codex/` and all subdirectories |
| `feature-implementation` | `feature-implementation`, `feature-implementation-sub`, … | `.lore/knights/feature-implementation/` and all subdirectories |

Matching is case-sensitive: `Conceptual` does not match `conceptual`. The hyphen boundary prevents accidental partial matches: `technical` does not match a group named `technicalstuff`.

## Root-Level File Inclusion

Files directly under the base directory (e.g., `.lore/codex/CODEX.md`) have `group == ""` and are **always returned** when `--filter` is provided, regardless of the filter tokens. Root-level files carry cross-cutting metadata (e.g., `CODEX.md`) that is globally relevant regardless of namespace.

## Unfiltered Behaviour (unchanged)

When `--filter` is **not** provided, all entities are returned — identical to pre-feature behaviour. The absence of `--filter` is a no-op: output is byte-for-byte identical to the output before this feature was introduced.

## CLI Flag Placement

`--filter` is a local flag at the subcommand level, placed at the end of the command following the same convention as `--json`:

```
lore codex list --filter conceptual
lore codex list --filter conceptual --json
lore artifact list --filter default-codex
lore knight list --filter feature-implementation
lore doctrine list --filter default
lore watcher list --filter default
```

Multiple tokens are supplied by repeating the flag or as separate arguments:

```
lore codex list --filter conceptual --filter decisions
lore codex list --filter conceptual technical-api
```

## Python API Parity

Per ADR-011, the filtering logic lives in each Python module function — not in `cli.py`. All five list functions accept a `filter_groups` keyword argument:

```python
scan_codex(codex_dir, filter_groups=None)
scan_artifacts(artifacts_dir, filter_groups=None)
list_knights(knights_dir, filter_groups=None)
list_doctrines(doctrines_dir, filter_groups=None)
list_watchers(watchers_dir, filter_groups=None)
```

`filter_groups=None` (or omitted) returns all entities — existing callers are unaffected. `filter_groups=["conceptual"]` returns all entities whose group is `conceptual` or starts with `conceptual-` (e.g., `conceptual-workflows`, `conceptual-reference`), plus root-level entities.

## Example Output

**Filtered, table mode (`lore codex list --filter conceptual`):**

Returns documents in group `conceptual` (files in `.lore/codex/conceptual/`) **and** all subgroups (e.g., `conceptual-workflows`, `conceptual-reference`) plus root-level files:

```
  ID                                    GROUP                    TITLE                              SUMMARY
  CODEX.md                                                       Codex Index                        Master index of all codex documents
  conceptual-entities-task              conceptual               Task Entity                        Describes the Task entity model
  conceptual-workflows-filter-list      conceptual-workflows     lore * list --filter Behaviour     What the system does when --filter is passed
```

**Filtered, JSON mode (`lore codex list --filter conceptual --json`):**

```json
{
  "codex": [
    {"id": "CODEX.md", "group": "", "title": "Codex Index", "summary": "Master index of all codex documents"},
    {"id": "conceptual-entities-task", "group": "conceptual", "title": "Task Entity", "summary": "Describes the Task entity model"},
    {"id": "conceptual-workflows-filter-list", "group": "conceptual-workflows", "title": "lore * list --filter Behaviour", "summary": "What the system does when --filter is passed"}
  ]
}
```

**Filter token matches nothing (only root-level files returned):**

```
  ID        GROUP    TITLE         SUMMARY
  CODEX.md           Codex Index   Master index of all codex documents
```

If no root-level files exist and no tokens match: `No codex documents found.` (same empty-state message as an unfiltered empty codex).

## Failure Modes

No new failure modes are introduced by this feature:
- An unrecognised filter token produces no error — the command returns only root-level files (plus any matching-group files) and exits 0.
- An empty `--filter` list (if achievable via the CLI) behaves identically to no filter.
- All existing failure modes (non-existent base directory, invalid frontmatter) are unchanged.

## Related

- conceptual-workflows-artifact-list (lore codex show conceptual-workflows-artifact-list)
- conceptual-workflows-knight-list (lore codex show conceptual-workflows-knight-list)
- conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list)
- conceptual-workflows-watcher-list (lore codex show conceptual-workflows-watcher-list)
- conceptual-workflows-codex (lore codex show conceptual-workflows-codex)
- tech-cli-commands (lore codex show tech-cli-commands)
- decisions-011-api-parity-with-cli (lore codex show decisions-011-api-parity-with-cli)
