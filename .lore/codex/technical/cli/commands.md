---
id: tech-cli-commands
title: CLI Command Reference
summary: Complete CLI reference for Lore — every command, flag, argument, output format, JSON schema, exit codes, and error behaviours. Covers all commands including lore board add/delete, lore codex list/show/search/map/chaos, and lore artifact list/show (read-only). Notes the hidden status of --no-auto-close on `lore new quest` versus its visible status on `lore edit`.
related: ["tech-cli-entity-crud-matrix", "tech-db-schema", "decisions-005", "decisions-008", "conceptual-workflows-codex-map", "conceptual-workflows-codex-chaos", "conceptual-workflows-filter-list"]
stability: stable
---

# CLI Command Reference

## Init

```
lore init
```

Initialize a Lore project in the current directory. Creates `.lore/` with the database, default Doctrines, Knights, and Artifacts. Creates or updates `AGENTS.md` at the project root. Idempotent — safe to run multiple times. On re-init, default assets (doctrines, knights, artifacts, gitignore) are overwritten with the latest versions shipped with Lore. User-created files with different names are not touched. If a non-Lore `AGENTS.md` exists, it is backed up to `AGENTS.md.old` and a fresh Lore `AGENTS.md` is written. If a Lore-marked `AGENTS.md` exists, the content between markers is refreshed. See tech-arch-agents-md (lore codex show tech-arch-agents-md) for full behaviour. `lore init` does not support `--json`.

## Top-Level

`lore --help` description:

> Lore is an agent task manager. Work is organised into Quests (bodies of work) and Missions (single executable tasks). Orchestrators plan and dispatch; workers claim, execute, and close. Knights are reusable agent personas; Doctrines are workflow templates. Run any command group with --help for details on that concept.

## Dashboard

```
lore
```

Default dashboard. Shows all open Quests with Mission counts and progress. One-glance overview. If no quests exist, the dashboard displays: `No quests yet. Run "lore new quest" to get started.`

```
lore stats
```

Aggregate numbers: total open/in_progress/blocked/closed across all Quests and Missions. Standalone missions (no quest) are included in mission counts. If no data exists, all counts are zero.

## New (Entity Creation)

`lore new --help` description:

> Create quests and missions. A Quest is a body of work (feature, bug fix, refactor). A Mission is a single executable task within a quest. Missions without a quest (-q) are standalone. Use 'lore new quest' then 'lore new mission -q <id>' to build a plan.

## Quests

```
lore list
```

List all open Quests. Sorted by priority ascending (P0 first), then `created_at` ascending.

```
lore list --all
```

List all Quests including closed. Same sort order.

```
lore show q-a1b2
```

Show a Quest with all its Missions and their statuses. Missions are rendered as a flat topologically-sorted list — parents always appear before children. Each mission line shows a status symbol, the short mission ID, the title, the mission type in brackets (omitted when no type is set), and any direct parent mission IDs after a `←` symbol (omitted when the mission has no parents). All `←` symbols are tab-aligned so they form a consistent right-hand column. Status symbols: `●` (closed), `◕` (in_progress or blocked), `○` (open). Intra-quest parents use short IDs (`m-xxxx`); cross-quest parents use fully-qualified IDs (`q-xxxx/m-xxxx`). Closed missions remain in the list — they are not hidden.

Example output:

```
Missions:
○ m-0e36 Design auth schema [knight]
○ m-a6d0 Design dashboard UI [knight]         ← q-4f5a/m-0e36
○ m-d6b3 Implement dashboard API [knight]     ← m-a6d0, q-4f5a/m-8383
○ m-9501 Deploy dashboard [constable]         ← m-d6b3, q-4f5a/m-cdf7
```

```
lore new quest "Redesign checkout flow"
lore new quest "Redesign checkout flow" -d "Full redesign of the checkout UX."
lore new quest "Redesign checkout flow" -p 0
lore new quest "Redesign checkout flow" --auto-close
```

Create a new Quest. Returns the Quest ID. Flags:

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--description` | `-d` | `""` | Quest description |
| `--priority` | `-p` | `2` | Priority 0–4 |
| `--auto-close` | | `false` | Enable auto-close when all missions done |
| `--no-auto-close` | | `false` | **Hidden flag** (`hidden=True` in cli.py line 197). Not shown in `--help` output. On `lore new quest`, `--no-auto-close` has no effect beyond the default (auto-close is already disabled by default). The visible equivalent is simply omitting `--auto-close`. |

> **Drift note:** `cli.md` (the source document) presents `--no-auto-close` as a user-visible flag for `lore new quest`. In `cli.py`, `--no-auto-close` is marked `hidden=True` on the `new quest` command (line 197) and is therefore not shown in help output. On `lore edit`, `--no-auto-close` is a visible flag (line 1331). This asymmetry is intentional: `--no-auto-close` is the default for new quests, so the flag serves no purpose on creation but is needed on edit to explicitly disable auto-close.

## Quest and Mission Edit and Delete

### Edit

```
lore edit q-a1b2 --title "New title" --description "New description" --priority 1
lore edit q-a1b2 --auto-close
lore edit q-a1b2 --no-auto-close
```

Update quest fields. Flags: `--title` / `-t`, `--description` / `-d`, `--priority` / `-p`, `--auto-close`, `--no-auto-close`. Only provided flags are applied. At least one flag is required (otherwise Click usage error, exit code 2). Updates `updated_at`. Status is not directly editable (use `lore done q-xxxx` to manually close a quest).

**Note:** On `lore edit`, `--no-auto-close` is a **visible** flag (not hidden). This is the mechanism to explicitly disable auto-close on an existing quest. Contrast with `lore new quest` where `--no-auto-close` is hidden because auto-close is already disabled by default for new quests.

```
lore edit q-a1b2/m-f3c1 --title "New title" --description "New desc" --priority 0 --knight developer.md
lore edit q-a1b2/m-f3c1 -T human
```

Update mission fields. Routes to quest or mission based on the ID prefix. Flags: `--title` / `-t`, `--description` / `-d`, `--priority` / `-p`, `--knight` / `-k`, `--no-knight` (remove knight assignment), `--type` / `-T` (set mission type: any string; omitting leaves the existing type unchanged). At least one flag is required. Updates `updated_at`. Status and block_reason are not editable here.

**`lore edit` error behaviours:**

| Error | Exit code | Message |
|-------|-----------|---------|
| Malformed entity ID | 1 | `Invalid entity ID format: "..."` |

This puts `lore edit` in line with `lore claim`, `lore done`, `lore block`, and `lore delete`, which also validate ID format before routing.

### Delete

```
lore delete q-a1b2
```

Soft-delete a quest. Without `--cascade`, only the quest row is soft-deleted — missions remain linked but effectively orphaned (they show a "(quest deleted)" annotation).

```
lore delete q-a1b2 --cascade
```

Soft-delete a quest and all its missions. Sets `deleted_at` on the quest row AND all its missions. Dependency rows referencing soft-deleted missions are also soft-deleted.

```
lore delete q-a1b2/m-f3c1
```

Soft-delete a mission. Sets `deleted_at` on the mission row and on all dependency rows where `from_id` or `to_id` matches the mission ID. Re-derives parent quest status. See tech-db-schema (lore codex show tech-db-schema).

Deleting an already soft-deleted entity is a no-op (idempotent, exit code 0 with warning). Deleting a non-existent entity fails with exit code 1.

## Missions

`lore ready --help` description:

> Show the next mission(s) to dispatch, sorted by priority with blocked and closed missions excluded. Used by orchestrators as the dispatch loop: claim the returned mission, then hand it to a worker agent (type: knight), handle it inline (type: constable), or leave it for a human (type: human). Optional COUNT argument returns multiple missions: 'lore ready 5'.

`lore missions --help` description:

> List missions across all quests, or scoped to one quest. Missions have four statuses: open, in_progress, blocked, closed. Three types: knight (worker agent), constable (orchestrator task), human (human checkpoint). Use 'lore ready' to find the next mission to dispatch.

```
lore ready
lore ready 5
```

Show the highest priority unblocked Mission(s), as determined by the priority queue. Output includes the mission type in brackets (e.g., `[sprint]`, `[review]`) when a type is set, so the orchestrator can decide how to dispatch according to the team's workflow convention. When a mission has no type assigned, the type bracket is omitted entirely. Default count is 1.

```
lore missions
lore missions --all
lore missions q-a1b2
```

List active Missions (status `open`, `in_progress`, or `blocked`). `--all` adds closed missions. Filtering by quest ID limits results to that quest. In human-readable output, missions are grouped by quest with a "Standalone" section. Sorted by priority ascending, then `created_at` ascending within each group. Each mission includes mission type in brackets when a type is set; when a mission has no type assigned (null), the type bracket is omitted entirely.

```
lore show q-a1b2/m-f3c1
```

Show full Mission detail: title, description, status, mission type (omitted when null), priority, dependencies (when present), Board section (when messages exist), and Knight file contents inline. Use `--no-knight` to omit Knight contents.

When a mission has dependencies, a `Dependencies:` section appears after the main fields (before Board), with two flat sub-sections: `Needs:` (direct upstream missions this mission depends on) and `Blocks:` (direct downstream missions that depend on this one). Each entry is a status symbol, mission ID, and title on one line. Status symbols: `●` (closed), `◕` (in_progress or blocked), `○` (open). Intra-quest missions use short IDs (`m-xxxx`); cross-quest missions use fully-qualified IDs (`q-xxxx/m-xxxx`). Closed dependencies remain visible with the `●` symbol. A sub-section is omitted when it has no entries. The entire `Dependencies:` section is omitted when the mission has no dependencies in either direction.

Example output:

```
Dependencies:
  Needs:
    ● q-4f5a/m-0e36 Design auth schema
    ○ q-4f5a/m-8383 Write auth tests
  Blocks:
    ○ m-d6b3 Implement dashboard API
```

When board messages exist, a `Board:` section appears after the `Dependencies:` section and before knight contents, with one line per message in the format `  [<created_at>] (<sender>) <message>` (when sender present) or `  [<created_at>] <message>` (when sender null). Messages are ordered by `created_at ASC`. When no active board messages exist, the `Board:` section is omitted entirely — consistent with `block_reason` (omitted when null) and `Dependencies:` (omitted when no dependencies). The same Board section applies to `lore show q-a1b2` (quest show).

```
lore new mission "Update payment API" -q q-a1b2 -d "Migrate the payment endpoint from SOAP to REST."
lore new mission "Update payment API" -q q-a1b2 -p 0 -k developer.md
lore new mission "Review PR" -q q-a1b2 -T review
lore new mission "Approve design" -q q-a1b2 -T approval
lore new mission "Fix a standalone bug"
```

Create a Mission. Flags:

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--quest` | `-q` | none | Parent quest ID (omit for standalone mission) |
| `--description` | `-d` | `""` | Mission description (strongly recommended) |
| `--priority` | `-p` | `2` | Priority 0–4 |
| `--knight` | `-k` | none | Knight filename (e.g., `developer.md`) |
| `--type` | `-T` | none | Mission type: any string. Field is null when omitted. |

**Null-type display behaviour.** When a mission has no type assigned (`mission_type` is null), the type bracket is omitted entirely from human-readable output in `lore ready`, `lore missions`, `lore show` (mission detail view), and `lore show` (quest detail missions list). The `Type:` line is also omitted from `lore show` mission detail when type is null. JSON output is unaffected — `"mission_type": null` is returned as-is and is the correct representation for consumers.

```
lore claim q-a1b2/m-f3c1 q-a1b2/m-d2e4 q-a1b2/m-ghi3
```

Claim one or more Missions. Sets status to `in_progress`. Used by the orchestrator before dispatching worker agents. Accepts multiple IDs. Does not check dependency state — claiming is unconditional on dependency status.

**`lore done` command description:**

> Close one or more missions or quests. For missions: transitions in_progress -> closed and unblocks any dependents. For quests: use only if auto_close is disabled; quests with auto_close enabled close automatically when all missions are done.

```
lore done q-a1b2/m-f3c1 q-a1b2/m-d2e4
```

Close one or more Missions. Accepts multiple IDs. Closing cascades automatically: dependencies waiting on this Mission become unblocked, and if the Quest has `auto_close` enabled and all Missions are now closed, the Quest is automatically closed. See tech-db-schema (lore codex show tech-db-schema).

```
lore done q-a1b2
```

Manually close a Quest. Sets `status` to `closed` and `closed_at` to the current timestamp. This is the mechanism for closing quests with `auto_close` disabled. Closing an already-closed quest is a no-op (exit code 0).

```
lore block q-a1b2/m-f3c1 "Waiting on API access"
```

Mark a Mission as blocked with a reason. The block reason is a required positional argument.

```
lore unblock q-a1b2/m-f3c1
```

Remove blocked status and clear `block_reason`, set back to `open`.

## Dependencies

```
lore needs q-a1b2/m-abc1:q-a1b2/m-def2
lore needs q-a1b2/m-abc1:q-a1b2/m-def2 q-a1b2/m-ghi3:q-a1b2/m-def2 q-a1b2/m-ghi3:q-a1b2/m-abc1
```

Declare that `m-abc1` needs `m-def2` to be done first. Uses colon-pair syntax: `this:that` means "this needs that." Accepts multiple pairs. Dependencies can be declared between any missions, including cross-quest and standalone-to-quest.

```
lore unneed q-a1b2/m-abc1:q-a1b2/m-def2
lore unneed q-a1b2/m-abc1:q-a1b2/m-def2 q-a1b2/m-ghi3:q-a1b2/m-def2
```

Soft-delete a dependency. Mirrors `lore needs` syntax. Removing a non-existent dependency is a no-op (idempotent, exit 0 with warning).

## Doctrines

`lore doctrine --help` description:

> Manage doctrine templates — YAML files that describe the step sequence and suggested knights for a standard body of work (e.g. a feature or bugfix workflow). Doctrines have no execution engine; an orchestrator reads them with 'lore doctrine show <name>' and uses the steps as guidance for creating quests and missions. Doctrines are passive — they do not trigger actions.

```
lore doctrine list
lore doctrine list --filter default
lore doctrine list --filter default feature-implementation
```

List available Doctrine templates as an aligned table with columns: ID, GROUP, TITLE, SUMMARY. Searches the full `.lore/doctrines/` directory tree recursively, merging results into a single alphabetically sorted flat list. GROUP is derived from the doctrine file's path relative to `.lore/doctrines/`, with directory components joined by `-`, excluding the filename. Doctrines missing `title` fall back to `id`. Doctrines missing `summary` fall back to truncated `description` (via `textwrap.shorten`, respecting word boundaries, max ~80 visible chars). Invalid doctrines show `[INVALID]` appended to the summary. No source-directory annotation is shown. Accepts `--json` as both a local flag (`lore doctrine list --json`) and the global flag (`lore --json doctrine list`). JSON output: `{"doctrines": [{id, group, title, summary, valid}]}`.

The optional `--filter GROUP...` flag limits results to doctrines in the specified group(s) using subtree matching: a token matches its exact group and all subgroups whose name starts with `token-`. For example, `--filter default` returns doctrines with group `default`, `default-feature`, `default-ops`, etc. Root-level doctrines (group == "") are always returned regardless of filter. Multiple tokens use OR logic. An unrecognised token produces no error. See conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) for full filter behaviour.

```
lore doctrine show feature-workflow
```

Print the contents of a Doctrine. Resolution is recursive: the command searches the full `.lore/doctrines/` tree using `rglob("<name>.yaml")` and returns the first match. This covers doctrines in `doctrines/default/` (Lore-seeded), doctrines at the flat parent level (user-created), and any user-created subdirectories at any depth. Per ADR-006, doctrine filenames are unique across the full tree, so there is at most one match. If no match is found, an error is raised. Validates the YAML schema.

```
lore doctrine new feature-workflow --from workflow.yaml
```

Create a new doctrine file at `.lore/doctrines/<name>.yaml`. Doctrine names must match `^[a-zA-Z0-9][a-zA-Z0-9_-]*$`. Fails if a doctrine with the same name already exists with: `Error: doctrine '<name>' already exists. Use 'lore doctrine edit <name>' to modify it.` Three input paths:

- **No `--from` and no piped stdin (TTY):** generates a skeleton YAML at `.lore/doctrines/<name>.yaml` with `id`, `title`, `summary`, `description`, and `steps` placeholders; prints `Created doctrine <name>`; exits 0. No validation is run on the skeleton.
- **`--from <file>` / `-f <file>`:** reads YAML from the named file, validates schema, then writes. The `name` field in the YAML must match the `<name>` argument. If `id` is present, it must also match.
- **stdin (default when `--from` is absent):** reads all of stdin, validates schema, then writes. Same field-match rules apply.

JSON success output (all paths): `{"name": "<name>", "filename": "<name>.yaml"}`.

```
lore doctrine edit feature-workflow --from updated-workflow.yaml
```

Replace the contents of an existing doctrine file. Validates YAML schema before writing. Fails if the doctrine does not exist.

```
lore doctrine delete feature-workflow
```

Soft-delete a doctrine file. Renames `.lore/doctrines/<name>.yaml` to `.lore/doctrines/<name>.yaml.deleted`.

## Knights

`lore knight --help` description:

> Manage knight personas — reusable markdown files that tell a worker agent how to approach work (style, constraints, authority). Assign a knight to a mission with 'lore new mission -k <name>.md'. When a worker runs 'lore show <mission-id>', the knight's content is included in the output. Knights encode the 'how'; mission descriptions encode the 'what'.

```
lore knight list
lore knight list --filter feature-implementation
lore knight list --filter feature-implementation default
```

List available Knights as an aligned table with columns: ID, GROUP, TITLE, SUMMARY. Searches the full `.lore/knights/` directory tree recursively (`rglob("*.md")`), returning all knights at any depth. ID, TITLE, and SUMMARY are read from YAML frontmatter (`---`-delimited block at file top). Knights without valid frontmatter fall back to: `id` = filename stem, `title` = filename stem, `summary` = empty string. GROUP is derived from the knight file's path relative to `.lore/knights/`, with directory components joined by `-`, excluding the filename. Results are sorted by `id`. No source-directory annotation is shown. Accepts `--json` as both a local flag (`lore knight list --json`) and the global flag (`lore --json knight list`). JSON output: `{"knights": [{id, group, title, summary}]}`.

The optional `--filter GROUP...` flag limits results to knights in the specified group(s) using subtree matching: a token matches its exact group and all subgroups whose name starts with `token-`. For example, `--filter feature-implementation` returns knights with group `feature-implementation`, `feature-implementation-sub`, etc. Root-level knights (group == "") are always returned regardless of filter. Multiple tokens use OR logic. An unrecognised token produces no error. See conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) for full filter behaviour.

```
lore knight show developer
```

Print the contents of a Knight file. Resolution is recursive: the command searches the full `.lore/knights/` tree using `rglob("<name>.md")` and returns the first match. This covers knights in `knights/default/` (Lore-seeded), knights at the flat parent level (user-created), and any user-created subdirectories at any depth. Per ADR-006, knight filenames are unique across the full tree, so there is at most one match. If no match is found, an error is raised: `Knight "<name>" not found`. Knight contents are also included automatically when viewing a Mission via `lore show`.

```
lore knight new reviewer --from instructions.md
```

Create a new knight file at `.lore/knights/<name>.md`. Reads content from `--from` / `-f` if provided, otherwise from stdin. Fails if the knight already exists. Knight names must match `^[a-zA-Z0-9][a-zA-Z0-9_-]*$`.

```
lore knight edit developer --from updated-instructions.md
```

Replace the contents of an existing knight file. Fails if the knight does not exist.

```
lore knight delete developer
```

Soft-delete a knight file. Renames `.lore/knights/<name>.md` to `.lore/knights/<name>.md.deleted`. Does NOT null out the `knight` field on missions that reference it — those missions show a "knight file not found" warning on `lore show`.

## Watchers

`lore watcher --help` description:

> Manage watcher definitions — YAML files stored in .lore/watchers/ that declare trigger conditions and map them to actions (typically doctrine names). Watchers are passive declarations; Lore stores and surfaces them but does not execute them. Use 'lore watcher list' to see all watchers and 'lore watcher show <name>' to view one.

```
lore watcher list
lore watcher list --filter default
lore watcher list --filter default custom-group
```

List available Watchers as an aligned table with columns: ID, GROUP, TITLE, SUMMARY. Searches the full `.lore/watchers/` directory tree recursively (`rglob("*.yaml")`). GROUP is derived from the watcher file's path relative to `.lore/watchers/`, with directory components joined by `-`, excluding the filename. Results are sorted by `id`. Watchers with missing required fields fall back to defaults (filename stem for `id`, `id` value for `title`, empty string for `summary`). No source-directory annotation is shown.

If no watchers are found, `No watchers found.` is printed. Exit code 0 in all cases.

The `--json` flag is accepted both as a local subcommand flag (`lore watcher list --json`) and as the global flag (`lore --json watcher list`).

JSON output: `{"watchers": [{"id": "...", "group": "...", "title": "...", "summary": "..."}]}`

The optional `--filter GROUP...` flag limits results to watchers in the specified group(s) using subtree matching: a token matches its exact group and all subgroups whose name starts with `token-`. For example, `--filter default` returns watchers with group `default`, `default-ci`, `default-ops`, etc. Root-level watchers (group == "") are always returned regardless of filter. Multiple tokens use OR logic. An unrecognised token produces no error. See conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) for full filter behaviour.

```
lore watcher show <name>
```

Print the contents of a Watcher file. Resolution is recursive: the command searches the full `.lore/watchers/` tree using `rglob("<name>.yaml")`. Raises `ValueError` for path-traversal attempts (names containing `/` or `\\`).

**Plain mode (default):** Prints the raw YAML file content byte-for-byte, including comments. This behaviour diverges from `lore knight show` (which outputs the markdown body) because watcher files are pure YAML, not markdown-with-frontmatter.

**JSON mode:** Returns a structured dict. All 8 keys are always present. Absent optional fields serialize as `null`.

JSON output shape:
```json
{"id": "...", "group": "...", "title": "...", "summary": "...", "watch_target": "...", "interval": "...", "action": "...", "filename": "..."}
```

**Not found error:**

Plain (stderr): `Watcher "<name>" not found in .lore/watchers/`
JSON (stderr): `{"error": "Watcher \"<name>\" not found in .lore/watchers/"}`
Exit code: 1

```
lore watcher new <name> [--from <file>]
```

Create a new watcher file at `.lore/watchers/<name>.yaml`. Watcher names must match `^[a-zA-Z0-9][a-zA-Z0-9_-]*$`. Fails if a watcher with the same name already exists (anywhere in `.lore/watchers/` via `rglob`).

| Flag | Short | Description |
|------|-------|-------------|
| `--from <file>` | `-f <file>` | Read content from the named file (must exist on disk) |
| (no flag) | | Read content from stdin |

Content is validated as YAML (`yaml.safe_load`) before writing to disk. Invalid YAML is rejected with an error before any write occurs.

**Success messages:**

Plain: `Created watcher <name>`.
JSON: `{"id": "<name>", "filename": "<name>.yaml"}`

**Error behaviours:**

| Error | Exit code | Message |
|-------|-----------|---------|
| Invalid name | 1 | Error to stderr |
| Duplicate watcher | 1 | `Watcher "<name>" already exists.` |
| Source file not found (`--from`) | 1 | `File not found: <path>` |
| Empty stdin content | 1 | `No content provided on stdin.` |
| Invalid YAML content | 1 | Error to stderr |

```
lore watcher edit <name> [--from <file>]
```

Replace the contents of an existing watcher file. Locates the file via `rglob` (not a flat path check) — watchers in group subdirectories can be edited by name alone. Validates YAML before writing. Fails if the watcher does not exist.

**Success messages:**

Plain: `Updated watcher <name>`.
JSON: `{"id": "<name>", "filename": "<name>.yaml"}`

**Error behaviours:**

| Error | Exit code | Message |
|-------|-----------|---------|
| Invalid name | 1 | Error to stderr |
| Watcher not found | 1 | `Watcher "<name>" not found.` |
| Source file not found (`--from`) | 1 | `File not found: <path>` |
| Empty stdin content | 1 | `No content provided on stdin.` |
| Invalid YAML content | 1 | Error to stderr |

```
lore watcher delete <name>
```

Soft-delete a watcher file. Renames `.lore/watchers/<name>.yaml` to `.lore/watchers/<name>.yaml.deleted` in place. The content is preserved. The file becomes invisible to all normal discovery operations (`rglob("*.yaml")`). Fails if the watcher does not exist.

**Success messages:**

Plain: `Deleted watcher <name>`.
JSON: `{"id": "<name>", "deleted": true}`

**Not found error:**

Plain (stderr): `Watcher "<name>" not found in .lore/watchers/`
Exit code: 1

**`--json` flag placement:** Use as a local flag after the subcommand (`lore watcher list --json`, `lore watcher show <name> --json`) or as the global flag (`lore --json watcher list`).

## Oracle

`lore oracle --help` description:

> Generate human-readable markdown reports in .lore/reports/. Produces one file per quest and mission. Wipes and recreates the reports directory on every run — do not store custom files there. Intended for human stakeholders, not for agent consumption. JSON output is not supported for this command.

```
lore oracle
```

Generate human-readable markdown reports into `.lore/reports/`. Overwrites any previous reports (deletes and recreates `.lore/reports/` on every run). `lore oracle` does not support `--json`.

The generated directory structure:

```
.lore/reports/
|- summary.md                          # Overall statistics and status
|- quests/
|  +-- q-a1b2-redesign-checkout-flow/  # Directory per quest (ID + slugified title)
|      |- index.md                     # Quest overview with mission list and progress
|      |- m-f3c1-update-payment.md     # One file per mission
|      +-- m-d2e4-write-tests.md
+-- missions/
    +-- m-b7c8-fix-standalone-bug.md   # Standalone missions (no quest)
```

**`summary.md`** contains aggregate statistics broken down by status.

**Quest `index.md`** contains the quest title, description, priority, and a table of all its missions.

**Mission `.md` files** contain the full mission detail: title, description, status, priority, knight, dependencies, and block reason if applicable.

Reports are read-only snapshots. Concurrent `lore oracle` runs are not supported.

**Empty state:** If no quests or missions exist, `lore oracle` generates only `summary.md` with zero counts. Exit code 0.

### Report Filename Slugification

Directory and file names are generated by concatenating the entity ID with a slugified version of the title:

- Lowercase the title
- Replace spaces and non-alphanumeric characters with hyphens
- Collapse consecutive hyphens into one
- Trim leading/trailing hyphens
- Truncate to 40 characters (at a word boundary if possible)

Example: quest `q-a1b2` with title `"Redesign Checkout Flow"` becomes directory `q-a1b2-redesign-checkout-flow/`.

See tech-cli-oracle-slugification (lore codex show tech-cli-oracle-slugification) for the full two-stage algorithm specification.

## Codex

`lore codex --help` description:

> Access project documentation — a set of typed markdown files maintained in .lore/codex/. Use 'lore codex list' to see all documents, 'lore codex search <keyword>' to narrow by keyword, and 'lore codex show <id>' to read one or more documents in full. Prefer 'lore codex show id1 id2' over multiple separate calls.

```
lore codex list
lore codex list --filter conceptual
lore codex list --filter conceptual decisions
lore codex list --filter conceptual --filter decisions
```

Return a table of contents: every document's ID, group, title, and summary. No body content. Human-readable output is a table with columns `ID`, `GROUP`, `TITLE`, `SUMMARY` rendered via the shared `_format_table` helper. GROUP is derived from the document's directory path under `.lore/codex/` using `derive_group`; documents at the root of `.lore/codex/` render with an empty GROUP. If `.lore/codex/` does not exist or contains no documents, output: `No codex documents found.` Exit code 0 in all cases. Does not list `TRANSIENT.md` marker files. Supports a local `--json` flag (placed at end: `lore codex list --json`).

The optional `--filter GROUP...` flag limits results to documents in the specified group(s) using subtree matching: a token matches its exact group and all subgroups whose name starts with `token-`. For example, `--filter conceptual` returns documents with group `conceptual`, `conceptual-workflows`, `conceptual-reference`, etc. Root-level documents (group == "") are always returned regardless of filter. Multiple tokens use OR logic. An unrecognised token produces no error. See conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) for full filter behaviour.

```
lore codex show <id> [id ...]
```

Return the full content of one or more documents by stable ID, concatenated in a single response. Accepts one or more IDs as positional arguments. For each ID, returns the full document body (frontmatter stripped). Human output: each document's body preceded by a separator line (`=== <id> ===`). Fail-fast on the first missing ID: no partial results are emitted; error goes to stderr, exit code 1.

```
lore codex search <keyword>
```

Filter the table of contents to documents whose `id`, `title`, or `summary` contains `keyword` (case-insensitive substring). Output format is identical to `lore codex list` (columns: `ID`, `GROUP`, `TITLE`, `SUMMARY`). If no matches: `No documents matching "<keyword>".` Exit code 0 in all cases.

```
lore codex map <id> [--depth <n>]
```

Traverse the codex document graph starting from `<id>` via BFS over the `related`
frontmatter field. Returns every discovered document in BFS order (root first,
then depth-1 neighbours, then depth-2, etc.), deduplicated. Output format matches
`lore codex show`: each document preceded by `=== <id> ===`. `--depth` defaults
to 1; depth 0 returns only the root document. Broken `related` links (IDs not
found in the codex) are silently skipped. Uses the global `--json` flag
(`lore --json codex map <id>`), not a local flag. JSON output:
`{"documents": [{"id": ..., "title": ..., "summary": ..., "body": ...}]}`.

| Flag | Default | Description |
|------|---------|-------------|
| `--depth` | `1` | BFS traversal depth (0 = root only, minimum 0). |

Error: if root document `<id>` is not found, prints `Document "<id>" not found` to
stderr and exits with code 1. In JSON mode: `{"error": "Document \"<id>\" not found"}`
to stderr, exit code 1.

```
lore codex chaos <id> --threshold <int>
```

Traverse the codex document graph from `<id>` using a probabilistic random walk,
stopping when the ratio of discovered documents to the reachable subgraph exceeds
`--threshold / 100`, or when no unvisited reachable neighbours remain.

- `<id>` — required positional argument; the seed document ID. The seed is always
  the first entry in the result.
- `--threshold` — required integer, 30–100 inclusive. Values below 30 or above 100
  are rejected with `--threshold must be between 30 and 100` to stderr, exit code 1.
- Unlike `lore codex map`, the traversal treats `related` links as bidirectional:
  `A → B` makes B a neighbour of A and A a neighbour of B for walk purposes.
- Does not support `--depth`. The `--threshold` flag is a percentage of the reachable
  subgraph, not a hop count. The two flags are intentionally distinct.
- Does not write to or modify the codex.
- Output order and subset are non-deterministic across invocations.

Output (text mode): table with columns ID, GROUP, TITLE, SUMMARY — identical column
layout to `lore codex list`. No `=== <id> ===` body separators.

JSON mode (global `--json` flag placed at end per project convention):

```json
{"codex": [{"id": "...", "group": "...", "title": "...", "summary": "..."}, ...]}
```

No `body` field in chaos JSON output.

| Flag | Default | Description |
|------|---------|-------------|
| `--threshold` | required | Walk coverage percentage, 30–100 inclusive. |

Error: if seed document `<id>` is not found, prints `Document "<id>" not found` to
stderr and exits with code 1. In JSON mode: `{"error": "Document \"<id>\" not found"}`
to stderr, exit code 1.

All five codex commands support `--json`.

## Artifacts

`lore artifact --help` description:

> Access project artifacts — reusable template files stored in .lore/artifacts/ and accessed by stable ID. Use 'lore artifact list' to see available templates and 'lore artifact show <id>' to retrieve content. Always use these commands rather than reading .lore/artifacts/ files directly. Artifacts are read-only via the CLI; maintainers create and update them on disk.

```
lore artifact list
lore artifact list --filter default-codex
lore artifact list --filter default-codex default-transient
```

Return a table of available artifact templates: every artifact's ID, group, title, and summary. No body content. Human-readable output is a table with columns `ID`, `GROUP`, `TITLE`, `SUMMARY`. GROUP is derived from the artifact file's path relative to `.lore/artifacts/`, with directory components joined by `-`, excluding the filename. If `.lore/artifacts/` does not exist or contains no indexed artifacts: `No artifacts found.` Exit code 0 in all cases.

The optional `--filter GROUP...` flag limits results to artifacts in the specified group(s) using subtree matching: a token matches its exact group and all subgroups whose name starts with `token-`. For example, `--filter default` returns artifacts with group `default`, `default-codex`, `default-transient`, etc. Root-level artifacts (group == "") are always returned regardless of filter. Multiple tokens use OR logic. An unrecognised token produces no error. See conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) for full filter behaviour.

```
lore artifact show <id> [id ...]
```

Return the full content of one or more artifacts by stable ID, concatenated in a single response. Accepts one or more IDs as positional arguments. For each ID, returns the full artifact body (frontmatter stripped). Human output: each artifact's body preceded by a separator line (`=== <id> ===`), in the order IDs were given. Fail-fast on the first missing ID: no partial results are emitted; error goes to stderr, exit code 1.

Artifact files are managed directly on disk — there are no CLI commands to create or delete artifacts.

Both artifact commands support `--json`.

## Board

```
lore board add <entity-id> "<message>" [--sender <lore-id>]
```

Post an operational note to a quest or mission board. `entity-id` may be `q-xxxx` (quest board) or `q-xxxx/m-yyyy` (mission board). The message is a positional text argument. `--sender` / `-s` is optional — a Lore ID (`q-xxxx` or `q-xxxx/m-yyyy`) identifying which mission or quest the posting agent was executing. The entity must exist and not be soft-deleted. Success output: `Board message posted (id: <N>)`.

```
lore board delete <message-id>
```

Soft-delete a board message by its integer ID. The integer ID is returned by `lore board add`. Success output: `Board message <N> deleted.`

Board messages are surfaced in `lore show` output only — they do not appear in `lore missions`, `lore ready`, `lore list`, or any other list view.

Both board commands support `--json`.

## ID Routing

Commands that accept entity IDs (`lore show`, `lore edit`, `lore delete`, `lore done`, `lore claim`, `lore block`, `lore unblock`) dispatch based on the ID prefix:

- **`q-`** routes to the quests table
- **`m-`** or **`q-.../m-`** routes to the missions table

Unknown prefixes fail format validation with the "Invalid ID format" error.

## Global Flags

All commands support these global flags:

| Flag | Description |
|------|-------------|
| `--json` | Output as JSON for programmatic consumption. Exception: `lore init` and `lore oracle` do not support `--json`. |
| `--help` | Show help text |
| `--version` | Show the installed Lore version and exit |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Application error (invalid input, validation failure, entity not found) |
| 2 | CLI usage error (wrong arguments, unknown command — handled by Click) |

All error messages are written to stderr. In `--json` mode, errors are also returned as JSON to stderr:

```json
{"error": "Mission q-a1b2/m-xxxx not found"}
```

## Error Behaviours

### Invalid IDs

- Quest IDs must match `q-[a-f0-9]{4,6}`
- Mission IDs must match `(q-[a-f0-9]{4,6}/)?m-[a-f0-9]{4,6}` (with optional quest prefix)

If the format is valid but the entity does not exist: `Quest "q-xxxx" not found` (exit code 1).

If the format is invalid: `Invalid quest ID format: "bad-id"` (exit code 1).

### Malformed Dependency Pairs

`lore needs` expects each argument in `A:B` format. An argument without exactly one colon fails with: `Invalid dependency pair format: "bad-arg". Expected "from:to".` (exit code 1).

### Duplicate Dependencies

`lore needs A:B` where the dependency already exists is a no-op. Prints `Dependency already exists: A -> B` but exits with code 0.

### Circular Dependencies

`lore needs A:B` where adding A->B would create a cycle fails with: `Circular dependency detected: adding A -> B would create a cycle` (exit code 1). See tech-db-schema (lore codex show tech-db-schema).

### Dependency on a Closed Mission

`lore needs A:B` where mission B is already `closed` is allowed. The dependency row is created, but a note is printed: `Note: dependency target B is already closed. Mission A is not blocked.` Exit code 0.

### Claiming Already-Claimed Missions

`lore claim <id>` on a mission that is already `in_progress` is a no-op (exit code 0). Claiming a `closed` or `blocked` mission fails with an error (exit code 1).

### Closing Already-Closed Missions/Quests

`lore done <id>` on a mission or quest already `closed` is a no-op (exit code 0).

### ID Generation Failure

If ID generation fails after exhausting 4, 5, and 6 character hash lengths: `ID generation failed: collision after maximum length. Please retry.` (exit code 1).

### Unblocking a Non-Blocked Mission

`lore unblock <id>` on a mission that is not in `blocked` status fails with an invalid status transition error (exit code 1).

### Listing Missions for a Nonexistent Quest

`lore missions q-xxxx` where the quest does not exist fails with: `Quest "q-xxxx" not found` (exit code 1).

### Edit With No Flags

`lore edit q-xxxx` with no flags is a Click usage error (exit code 2).

### Invalid Knight/Doctrine Name

Names not matching `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` fail with: `Invalid name: must be alphanumeric, hyphens, underscores only.` (exit code 1). Applies to `lore knight new` and `lore doctrine new`.

### File Not Found for --from

`--from <path>` where the file does not exist fails with: `File not found: <path>` (exit code 1).

### Empty Stdin Content

Reading from stdin with no content (EOF) fails with: `No content provided on stdin.` (exit code 1).

### Unknown Codex Document ID

`lore codex show <id>` where the document ID does not exist: `Document "<id>" not found` (exit code 1). Fail-fast — no partial results are emitted when multiple IDs are given and one is missing.

### Unknown Artifact ID

`lore artifact show <id>` where the artifact ID does not exist: `Artifact "<id>" not found` (exit code 1). Fail-fast — no partial results are emitted when multiple IDs are given and one is missing.

### Mission Type

`-T` / `--type` accepts any string — mission type is free-form and stored as-is. There is no validation constraint; any value (including `"knight"`, `"constable"`, `"human"`, or any custom string) is accepted. Omitting `-T` leaves the existing type unchanged on `lore edit`, or stores `null` on creation.

### Board — Entity Not Found

`lore board add <entity-id> "<message>"` where the entity does not exist (or is soft-deleted): `Quest "q-xxxx" not found` or `Mission "q-xxxx/m-yyyy" not found` (exit code 1).

### Board — Empty Message

`lore board add <entity-id> ""` with an empty message string: `Message cannot be empty.` (exit code 1).

### Board — Invalid Sender Format

`lore board add --sender <value>` where `<value>` is not a valid Lore ID format: `Invalid sender ID format: "<value>"` (exit code 1).

### Board — Message Not Found

`lore board delete <N>` where message ID `<N>` does not exist or is already soft-deleted: `Board message <N> not found.` (exit code 1). "Never existed" and "already deleted" are reported identically.

### Board — Non-Integer Message ID

`lore board delete <non-integer>` — Click built-in type error (exit code 2).

### Bulk Operation Partial Failures

For bulk commands (`lore claim`, `lore done`, `lore needs`), each argument is processed in its own transaction. If some succeed and some fail, successful operations are already committed and errors are printed to stderr. Exit code 1 if any item failed, 0 if all succeeded.

## JSON Output Schemas

When `--json` is passed, all commands return structured JSON to stdout.

### `lore --json` (Dashboard)

```json
{
  "quests": [
    {
      "id": "q-a1b2",
      "title": "Redesign checkout flow",
      "status": "in_progress",
      "priority": 1,
      "missions": {"open": 2, "in_progress": 1, "blocked": 0, "closed": 3}
    }
  ]
}
```

### `lore show <quest-id> --json`

```json
{
  "id": "q-a1b2",
  "title": "Redesign checkout flow",
  "description": "Full redesign of the checkout UX",
  "status": "in_progress",
  "priority": 1,
  "auto_close": false,
  "created_at": "2025-01-15T09:30:00Z",
  "updated_at": "2025-01-16T14:00:00Z",
  "closed_at": null,
  "missions": [
    {
      "id": "q-a1b2/m-abc1",
      "title": "Design the feature",
      "status": "closed",
      "mission_type": "knight",
      "priority": 1,
      "knight": "designer.md",
      "dependencies": {
        "needs": [],
        "blocks": [{"id": "q-a1b2/m-f3c1", "title": "Update payment API", "status": "in_progress"}]
      }
    },
    {
      "id": "q-a1b2/m-f3c1",
      "title": "Update payment API",
      "status": "in_progress",
      "mission_type": "knight",
      "priority": 1,
      "knight": "developer.md",
      "dependencies": {
        "needs": [{"id": "q-a1b2/m-abc1", "title": "Design the feature", "status": "closed"}],
        "blocks": [{"id": "q-a1b2/m-ghi3", "title": "Write tests", "status": "open"}]
      }
    },
    {
      "id": "q-a1b2/m-ghi3",
      "title": "Write tests",
      "status": "open",
      "mission_type": "knight",
      "priority": 1,
      "knight": "developer.md",
      "dependencies": {
        "needs": [{"id": "q-a1b2/m-f3c1", "title": "Update payment API", "status": "in_progress"}],
        "blocks": []
      }
    }
  ],
  "board": [
    {
      "id": 2,
      "sender": null,
      "message": "Phase 1 complete. All analysis artifacts produced.",
      "created_at": "2026-03-17T12:00:00Z"
    }
  ]
}
```

The `board` key is always present, even when no messages exist: `"board": []`. `deleted_at` is not included in board message objects. Each mission in `"missions"` includes a `"dependencies"` field with `"needs"` and `"blocks"` arrays (always present, even when empty). IDs in `"dependencies"` are always fully-qualified.

### `lore show <mission-id> --json`

```json
{
  "id": "q-a1b2/m-f3c1",
  "quest_id": "q-a1b2",
  "title": "Update payment API",
  "description": "Migrate the payment endpoint from SOAP to REST.",
  "status": "in_progress",
  "mission_type": "knight",
  "priority": 1,
  "knight": "developer.md",
  "knight_contents": "Full text of the knight file...",
  "block_reason": null,
  "created_at": "2025-01-15T09:30:00Z",
  "updated_at": "2025-01-16T14:00:00Z",
  "closed_at": null,
  "dependencies": {
    "needs": [{"id": "q-a1b2/m-abc1", "title": "Design the feature", "status": "closed"}],
    "blocks": [{"id": "q-a1b2/m-ghi3", "title": "Write tests", "status": "open"}]
  },
  "board": [
    {
      "id": 1,
      "sender": "q-a1b2/m-abc1",
      "message": "Output artifact at .lore/codex/specs/mission-board.md",
      "created_at": "2026-03-17T10:00:00Z"
    }
  ]
}
```

The `board` key is always present, even when no messages exist: `"board": []`. `deleted_at` is not included in board message objects. The `"dependencies"` key is always present (with empty arrays when there are none). IDs in `"dependencies"` are always fully-qualified. `"needs"` and `"blocks"` contain only **direct** neighbours — transitive chains are not included. To traverse the full graph, use `lore show <quest-id> --json` where all missions are present with their direct deps.

When `--no-knight` is used, `knight_contents` is `null`.

### `lore ready --json` / `lore ready 5 --json`

```json
{
  "missions": [
    {
      "id": "q-a1b2/m-f3c1",
      "quest_id": "q-a1b2",
      "title": "Update payment API",
      "status": "open",
      "mission_type": "knight",
      "priority": 0,
      "knight": "developer.md",
      "created_at": "2025-01-15T09:30:00Z"
    }
  ]
}
```

### `lore stats --json`

```json
{
  "quests": {"open": 2, "in_progress": 1, "closed": 5},
  "missions": {"open": 4, "in_progress": 2, "blocked": 1, "closed": 12}
}
```

### `lore new quest --json` / `lore new mission --json`

```json
{"id": "q-a1b2"}
```

```json
{"id": "q-a1b2/m-f3c1"}
```

### `lore done --json` (missions)

```json
{
  "updated": ["q-a1b2/m-f3c1", "q-a1b2/m-d2e4"],
  "quest_closed": ["q-a1b2"],
  "errors": []
}
```

`quest_closed` lists any quests that were auto-closed as a result of this operation (only quests with `auto_close` enabled). `errors` lists any items that failed.

### `lore done <quest-id> --json`

```json
{
  "id": "q-a1b2",
  "status": "closed",
  "closed_at": "2025-01-15T09:30:00Z"
}
```

### `lore claim --json`

```json
{
  "updated": ["q-a1b2/m-f3c1", "q-a1b2/m-d2e4"],
  "quest_status_changed": [{"id": "q-a1b2", "status": "in_progress"}],
  "errors": []
}
```

`quest_status_changed` lists any quests whose derived status changed. For standalone missions, always an empty array.

### `lore list --json` / `lore list --all --json`

```json
{
  "quests": [
    {
      "id": "q-a1b2",
      "title": "Redesign checkout flow",
      "status": "open",
      "priority": 1,
      "created_at": "2025-01-15T09:30:00Z"
    }
  ]
}
```

### `lore missions --json` / `lore missions --all --json`

```json
{
  "missions": [
    {
      "id": "q-a1b2/m-f3c1",
      "quest_id": "q-a1b2",
      "title": "Update payment API",
      "status": "in_progress",
      "mission_type": "knight",
      "priority": 1,
      "knight": "developer.md",
      "created_at": "2025-01-15T09:30:00Z"
    }
  ]
}
```

Flat array. Standalone missions have `quest_id: null`. Note: human-readable output groups missions by quest; JSON output returns a flat array.

### `lore missions <quest-id> --json`

Same schema as `lore missions --json`, filtered to missions belonging to the specified quest.

### `lore block --json`

```json
{"id": "q-a1b2/m-f3c1", "status": "blocked", "block_reason": "Waiting on API access"}
```

### `lore unblock --json`

```json
{"id": "q-a1b2/m-f3c1", "status": "open"}
```

### `lore needs --json`

```json
{
  "created": [{"from": "q-a1b2/m-abc1", "to": "q-a1b2/m-def2"}],
  "existing": [],
  "errors": []
}
```

`created` lists newly created dependencies. `existing` lists pairs that already existed (no-op). `errors` lists pairs that failed.

### `lore doctrine list --json`

```json
{
  "doctrines": [
    {"id": "feature-workflow", "group": "", "title": "Feature Workflow", "summary": "Standard design-implement-test workflow for new features", "valid": true},
    {"id": "broken-doctrine", "group": "", "title": "broken-doctrine", "summary": "", "valid": false, "errors": ["Step \"test\" references unknown dependency \"tset\""]}
  ]
}
```

The `errors` field is present only for invalid doctrines (`valid: false`). Valid doctrines omit `errors` entirely. This matches the `list_doctrines()` return shape where `errors` is conditionally added on failure.

### `lore doctrine show --json`

```json
{
  "name": "feature-workflow",
  "description": "Standard feature development workflow",
  "steps": [
    {"id": "design", "title": "Design the feature", "priority": 1, "type": "knight", "needs": [], "knight": "designer.md", "notes": "Produce a design document with acceptance criteria"}
  ]
}
```

### `lore knight list --json`

```json
{
  "knights": [
    {"id": "developer", "group": "default", "title": "Developer", "summary": "Implements features following design documents and coding standards"}
  ]
}
```

### `lore knight show --json`

```json
{
  "name": "developer",
  "filename": "developer.md",
  "contents": "Full text of the knight file..."
}
```

### `lore edit <quest-id> --json` / `lore edit <mission-id> --json`

Returns the full updated entity (same shape as `lore show --json`).

### `lore delete <quest-id> --json`

Without `--cascade`:

```json
{"id": "q-a1b2", "deleted_at": "2025-01-15T09:30:00Z"}
```

With `--cascade`:

```json
{"id": "q-a1b2", "deleted_at": "2025-01-15T09:30:00Z", "cascade": ["q-a1b2/m-f3c1", "q-a1b2/m-d2e4"]}
```

### `lore delete <mission-id> --json`

```json
{"id": "q-a1b2/m-f3c1", "deleted_at": "2025-01-15T09:30:00Z"}
```

### `lore knight new --json` / `lore knight edit --json`

```json
{"name": "developer", "filename": "developer.md"}
```

### `lore knight delete --json`

```json
{"name": "developer", "deleted": true}
```

### `lore doctrine new --json` / `lore doctrine edit --json`

```json
{"name": "feature-workflow", "filename": "feature-workflow.yaml"}
```

### `lore doctrine delete --json`

```json
{"name": "feature-workflow", "deleted": true}
```

### `lore unneed --json`

```json
{
  "removed": [{"from": "q-a1b2/m-abc1", "to": "q-a1b2/m-def2"}],
  "not_found": [],
  "errors": []
}
```

`removed` lists dependencies that were soft-deleted. `not_found` lists pairs that did not exist (no-op). `errors` lists pairs that failed.

### `lore codex list --json` and `lore codex search <keyword> --json`

```json
{
  "codex": [
    {
      "id": "tech-cli-commands",
      "group": "technical/cli",
      "title": "CLI Command Reference",
      "summary": "Complete CLI reference for Lore — every command, flag, argument, output format, JSON schema, exit codes, and error behaviours."
    }
  ]
}
```

Empty state: `{"codex": []}` (exit code 0).

### `lore codex show <id> [id ...] --json`

```json
{
  "documents": [
    {
      "id": "tech-cli-commands",
      "title": "CLI Command Reference",
      "summary": "Complete CLI reference for Lore — every command, flag, argument, output format, JSON schema, exit codes, and error behaviours.",
      "body": "# CLI Command Reference\n\n## Init\n\n..."
    }
  ]
}
```

The `body` field contains the full document content below the YAML frontmatter block. Frontmatter metadata is already exposed as structured fields and is not repeated in `body`.

#### Error — unknown document ID

To stderr, exit code 1:

```json
{"error": "Document \"bad-id\" not found"}
```

Fail-fast semantics: on the first missing ID, no partial results are emitted to stdout.

### `lore artifact list --json`

```json
{
  "artifacts": [
    {
      "id": "transient-business-spec",
      "group": "transient",
      "title": "Business Specification Template",
      "summary": "Blank scaffold for writing a new business specification."
    }
  ]
}
```

Empty state: `{"artifacts": []}` (exit code 0).

### `lore artifact show <id> [id ...] --json`

```json
{
  "artifacts": [
    {
      "id": "transient-business-spec",
      "title": "Business Specification Template",
      "summary": "Blank scaffold for writing a new business specification.",
      "body": "# {Title}\n\n## Problem\n\n..."
    },
    {
      "id": "transient-full-spec",
      "title": "Full Specification Template",
      "summary": "Blank scaffold for writing a full technical specification.",
      "body": "# {Title}\n\n..."
    }
  ]
}
```

Multiple IDs produce one entry per ID in the array, in the order given. Fail-fast semantics: on the first missing ID, no partial results are emitted to stdout.

#### Error — unknown artifact ID

To stderr, exit code 1:

```json
{"error": "Artifact \"bad-id\" not found"}
```

### `lore board add --json`

Success:

```json
{"id": 1, "entity_id": "q-a1b2/m-f3c1", "sender": "q-a1b2/m-abc1", "created_at": "2026-03-17T10:00:00Z"}
```

`sender` is `null` when `--sender` was not provided.

#### Error — entity not found

To stderr, exit code 1:

```json
{"error": "Mission \"q-a1b2/m-xxxx\" not found"}
```

### `lore board delete --json`

Success:

```json
{"id": 1, "deleted_at": "2026-03-17T10:00:00Z"}
```

#### Error — message not found

To stderr, exit code 1:

```json
{"error": "Board message 99 not found."}
```

`lore init` and `lore oracle` do not support `--json`. `lore init` is a one-time setup command. `lore oracle` generates file-based reports rather than JSON output.
