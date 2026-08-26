---
id: ref-lore_cli-commands
title: Lore CLI — commands surface
summary: Reference doc for the Lore CLI — the cross-cutting conventions, exit codes,
  idempotency rules, JSON envelope contract, and per-command idiosyncrasies that
  span more than one command. Per-command flags and help text are canonical via
  `lore <command> --help` (ADR-008); the source of truth for behaviour is
  `src/lore/cli.py` plus the ADRs listed below.
binds:
- src/lore/cli.py
- tests/e2e/test_*.py
related:
- tech-cli-entity-crud-matrix
- ref-lore_db-core
- decisions-005-auto-close-toggle
- decisions-008-help-as-teaching-interface
- decisions-006-id-references
- decisions-012-multi-value-cli-param-convention
- decisions-013-toml-for-config-yaml-for-glossary
- decisions-018-overlays-are-path-discovered-config
- decisions-019-overlay-scope-stops-at-transient
- decisions-020-codex-voice-is-enforced
- decisions-021-health-reports-are-ephemeral-by-default
- conceptual-workflows-codex-map
- conceptual-workflows-codex-chaos
- conceptual-workflows-filter-list
- conceptual-workflows-health
- conceptual-workflows-help
- conceptual-workflows-stats
- conceptual-workflows-glossary
- conceptual-workflows-json-output
- conceptual-workflows-error-handling
- conceptual-workflows-impacts
- conceptual-entities-glossary
- conceptual-entities-rite
- conceptual-workflows-rite-list
- conceptual-workflows-rite-show
- conceptual-workflows-rite-search
- conceptual-workflows-rite-crud
- decisions-014-link-direction
- decisions-015-rites-writable-file-entity
- decisions-016-rite-json-envelope-omits-group
- decisions-017-constrained-flags-use-click-choice
- decisions-001-dumb-infrastructure
- tech-arch-schemas
- tech-arch-agents-md
- conceptual-workflows-lore-init
- conceptual-workflows-init-interactive
- conceptual-workflows-init-reconcile
- conceptual-entities-skill
---

# Lore CLI — commands surface

**Covers:** `lore`, `lore init`, `lore`, `lore stats`, `lore new`, `lore new quest`, `lore new mission`, `lore list`, `lore show`, `lore edit`, `lore delete`, `lore claim`, `lore done`, `lore block`, `lore unblock`, `lore needs`, `lore unneed`, `lore missions`, `lore ready`, `lore doctrine`, `lore doctrine list`, `lore doctrine show`, `lore doctrine new`, `lore knight`, `lore knight list`, `lore knight show`, `lore knight new`, `lore knight edit`, `lore knight delete`, `lore watcher`, `lore watcher list`, `lore watcher show`, `lore watcher new`, `lore watcher edit`, `lore watcher delete`, `lore artifact`, `lore artifact list`, `lore artifact show`, `lore artifact new`, `lore rite`, `lore rite list`, `lore rite show`, `lore rite search`, `lore rite new`, `lore rite edit`, `lore rite delete`, `lore codex`, `lore codex list`, `lore codex show`, `lore codex search`, `lore codex map`, `lore codex chaos`, `lore impacts`, `lore glossary`, `lore glossary list`, `lore glossary show`, `lore glossary search`, `lore board`, `lore board add`, `lore board delete`, `lore oracle`, `lore health`
**Source of truth:** `src/lore/cli.py` (Click decorators, handler bodies); `lore <command> --help` for per-command flags and prose (canonical per ADR-008).

## Why this exists

ADR-008 makes `lore <command> --help` the canonical teaching surface — every command's help text is rich, hand-written, and structurally complete. This doc does NOT mirror help. It captures the cross-cutting conventions that span commands and the idiosyncratic behaviours that are easier to find in one place than in 30 separate help texts. When in doubt, run `--help`.

## Gotchas

### ID routing

Commands that accept entity IDs (`lore show`, `lore edit`, `lore delete`, `lore done`, `lore claim`, `lore block`, `lore unblock`) dispatch on prefix:

- `q-` → quests
- `m-` or `q-.../m-` → missions
- Anything else → `Invalid ID format` (exit 1).

Quest ID regex: `q-[a-f0-9]{4,6}`. Mission ID regex: `(q-[a-f0-9]{4,6}/)?m-[a-f0-9]{4,6}`.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Application error — invalid input, validation failure, entity not found |
| 2 | CLI usage error — wrong arguments, unknown command (Click) |

Errors always go to stderr. In `--json` mode they go to stderr as JSON: `{"error": "<message>"}`.

### Global flags

`--json`, `--help`, `--version` are global. `--json` is supported on every command **except** `lore init` and `lore oracle`. The exception is permanent — both produce side-effecting human output (init prints status; oracle writes markdown reports) where JSON adds no value. The two refuse it differently: `lore oracle` rejects the flag with a usage error at exit 2, while `lore init` accepts and ignores it at exit 0, so an existing pipeline that passes the global flag to every command still initialises a project. The machine surface for `lore init` is `lore.api.plan_init()`, which returns a typed `InitPlan` describing every create, overwrite, removal and conflict without performing any of them.

### Idempotency rules

- `lore claim <id>` on an already-`in_progress` mission → no-op, exit 0.
- `lore done <id>` on an already-`closed` mission/quest → no-op, exit 0.
- `lore needs A:B` where the dep already exists → prints `Dependency already exists: A -> B`, exit 0.
- `lore needs A:B` where B is already `closed` → creates the dep but prints `Note: dependency target B is already closed. Mission A is not blocked.`, exit 0.
- `lore unblock <id>` on a mission **not** in `blocked` status → invalid-transition error, exit 1. Asymmetric with the above on purpose: unblock is a state-machine transition, not a no-op.
- `lore claim <id>` on a `closed` or `blocked` mission → invalid-transition error, exit 1.
- `lore board delete <N>` collapses "never existed" with "already deleted" — both report `Board message <N> not found`, exit 1. Deliberate divergence from `delete_mission` / `delete_quest` (which return `already_deleted: true` on success); board messages are ephemeral and the distinction has no value.

### Bulk operations

`lore claim`, `lore done`, `lore needs`, `lore unneed` accept multiple arguments. Each item processes in its own transaction. Partial failure: successful items commit; failures print to stderr. Exit code is 1 if any item failed, 0 if all succeeded. See decisions-012-multi-value-cli-param-convention.

### `lore needs` / `lore unneed` syntax

Each argument is a colon pair: `A:B` (A depends on B). Argument without exactly one colon → `Invalid dependency pair format: "<arg>". Expected "from:to".`, exit 1. Cycle detection runs inside the transaction; rejection: `Circular dependency detected: adding A -> B would create a cycle`, exit 1.

### `--no-auto-close` visibility split

Hidden on `lore new quest` (the default for new quests is already `auto_close=0`, so the flag is redundant on creation). Visible on `lore edit q-...` (used to toggle existing quests). See decisions-005-auto-close-toggle.

### `lore edit` with no flags

Click usage error, exit 2. Cannot edit an entity to its current state — every `edit` must specify at least one field to change.

### Mission `--type` / `-T` is free-form

Any string accepted. No CHECK constraint, no enum. Common values are `knight`, `constable`, `human` but custom values are valid. Omitting `-T` on `lore new mission` stores `null`; on `lore edit` leaves the existing value unchanged. Mission `null`-vs-string handling is uniform across the four output sites (text show, text list, JSON show, oracle).

### Knight / doctrine / watcher / artifact name validation

All four `new` subcommands enforce `^[a-zA-Z0-9][a-zA-Z0-9_-]*$`. Failure: `Invalid name: must be alphanumeric, hyphens, underscores only.`, exit 1.

### `--group <path>` on `new` subcommands

Validated by `lore.validators.validate_group` before any filesystem access. Rejected forms: `..`, backslash, absolute path, leading or trailing `/`, empty segments, any segment failing the name rule. Failure: `Error: invalid group '<value>': <reason>`, exit 1. The CLI and Python paths are byte-identical (ADR-011). Subtree-wide duplicate detection: a doctrine `foo` cannot coexist anywhere under `doctrines_dir`, regardless of `group`.

### `--filter <group>...` on `list` subcommands

Slash-delimited segment-prefix matching. `--filter feature-implementation` matches everything in any subtree segment starting with `feature-implementation`. Hyphen-delimited input is no longer accepted. Root-level entries are always included.

### `--from <path>` and stdin

`--from <path>` where the file does not exist: `File not found: <path>`, exit 1. Stdin path with no content (EOF): `No content provided on stdin.`, exit 1.

### Codex / artifact `show` are fail-fast on multi-arg

`lore codex show <id1> <id2>` and `lore artifact show <id1> <id2>` emit zero partial output if any ID is missing. Failure: `Document "<id>" not found` or `Artifact "<id>" not found`, exit 1. Avoid scripting on partial output — there is none. `lore rite show` follows the same fail-fast rule (failure: `Rite "<id>" not found`).

### `lore rite` surface

`lore rite {list|show|search|new|edit|delete}` manages Rites (the procedural-memory entity, lore codex show conceptual-entities-rite). Notable behaviour:

- **Recursive + grouped, like every other entity.** Rites are discovered recursively under `main/` (default) and `shared/` (selected by `--shared`), and carry a `group` derived from their subfolder path. `rite list` shows a **GROUP column** and accepts **`--filter GROUP…`**; `rite new` accepts **`--group <path>`** (placing the file at `main/<group>/<name>.yaml`). `list`/`new`/`delete` JSON envelopes **carry the `group` key** (root → `null`) — no rite carve-out (see decisions-016-rite-json-envelope-omits-group and conceptual-workflows-json-output). `rite new` also carries a `kind` field (`"main"`/`"shared"`).
- **Globally-unique ids (codex model).** A rite's identity is its `id:`, unique across the ENTIRE `main/` + `shared/` tree (every subfolder); the subfolder path is cosmetic. `rite new` duplicate detection is tree-wide; a duplicate id anywhere → `Rite "<name>" already exists.`, exit 1. Health adds a `duplicate_rite_id` error for the same id in two files.
- **`show`/`edit`/`delete`/`use:` resolve by bare id, recursively.** `rite show <id>` / `edit <id>` / `delete <id>` take the bare id and scan the whole tree for the matching `id:` (mirroring `lore codex show <id>` and watcher edit/delete rglob lookup). `use:` references a bare id and resolves across `shared/` regardless of group. `show` inlines `use:` steps flat, non-recursively; a bare shared-step id renders the step alone. Dangling `use:` at show time → `Rite "<id>": shared step "<u>" not found`, exit 1.
- **`search` is keyword browse**, case-insensitive substring over id/title/summary/trigger of main rites (recursive) — NOT a situational matcher (scoring is deferred). No match → `No rites matching "<kw>".`, exit 0.
- **Name and group validation.** Name uses the shared `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` rule (`validate_rite_id`, bare — no slashes); `--group` is validated separately by `validate_group` like the other `--group` flags. `rite edit` with no `--from`/stdin → Click UsageError, exit 2 (parity with `lore edit`). Delete is soft-delete to `<id>.yaml.deleted`. See conceptual-workflows-rite-crud, conceptual-workflows-rite-list, conceptual-workflows-rite-show, conceptual-workflows-rite-search.

### `lore codex map` flag matrix

Default output is a list-shape table — columns ID, GROUP, TITLE, SUMMARY, same renderer as `lore codex list`. Default JSON envelope key is `"codex"`. Traversal is bidirectional at depth 1 in both axes by default.

| Flags passed | Outbound budget | Inbound budget |
|--------------|-----------------|----------------|
| none | `1` | `1` |
| `--depth N` | `N` | `N` |
| `--depth-out N` only | `N` | `0` |
| `--depth-in N` only | `0` | `N` |
| `--depth-out A --depth-in B` | `A` | `B` |
| `--depth N` + `--depth-in M` or `--depth-out M` | error — Click `UsageError`, exit 2 |

All three depth flags are `click.IntRange(min=0)`. `--full` is a flag (no value); it switches the default neighbour table to the legacy full-body output and composes with directional flags. The seed is never present in the output under any flag combination.

### `lore codex map` conflict-flag error

Combining `--depth` with `--depth-in` or `--depth-out` raises a Click `UsageError` before any I/O. Exit code 2. The byte-for-byte stderr message (used in tests):

```
--depth cannot be combined with --depth-in or --depth-out. Use --depth for symmetric traversal, or --depth-in and/or --depth-out for directional traversal.
```

In `--json` mode the same wording lands inside `{"error": "..."}` to stderr, still exit 2. `--depth-in` and `--depth-out` together are valid and combine.

### `lore codex map --full` JSON envelope

Default `--json` envelope key is `"codex"` (matches `lore codex list --json`). `--full --json` keeps the legacy `"documents"` key for backward compatibility, with `group` and `related` keys added per entry (additively — existing consumers reading `id`/`title`/`summary`/`body` are unaffected).

### `lore codex chaos --threshold` range

Enforced in two places: Click `IntRange(min=30, max=100)` and `lore.validators.validate_chaos_threshold`. Both required for ADR-011 parity. The Python entry point raises `ValueError`; the CLI surfaces a Click usage error (exit 2).

### `lore codex show` glossary auto-surface

Matches against canonical keywords AND aliases (token-run, canonical-only). Surfaces a `## Glossary` block at the bottom of each shown document. `--skip-glossary` per-call suppresses it. The root-level `show-glossary-on-codex-commands = false` in `.lore/config.toml` disables it globally. See conceptual-workflows-glossary.

### `lore impacts` token classification

`lore impacts` is a **top-level command**, not a subcommand under `lore codex` — `lore codex` walks within the codex (`map`, `chaos` on the `related:` edge); `lore impacts` crosses the codex↔code boundary (the `binds:` edge). The token is classified before any I/O: a `/` or `.` in the string → path; otherwise → codex id. Codex ids match `[a-z0-9-]+` and never contain either character, so classification is unambiguous. Path tokens are normalised against `find_project_root()` — absolute paths inside the repo are accepted and normalised; absolute paths outside the repo and any `..` segment exit 1. `--direct-links` drops glob matches from path-seed output and is a silent no-op on codex-seed lookups. JSON envelope key is `"impacts"`; error envelope is the standard `{"error": "..."}` to stderr. See conceptual-workflows-impacts.

### Board

- `lore board add <entity-id> "<message>"` — entity not found (or soft-deleted) → `Quest "..." not found` or `Mission "..." not found`, exit 1.
- Empty message → `Message cannot be empty.`, exit 1.
- `--sender <value>` not matching a Lore ID format → `Invalid sender ID format`, exit 1.
- `lore board delete <N>` non-integer → Click type error, exit 2.

### `lore init`

Idempotent. Re-init overwrites Lore-shipped default assets (doctrines, knights, artifacts, gitignore) in their `default/` subtrees; user-named files in the flat parent directories are never touched. Installed skills and instruction-file blocks are reconciled instead of blindly rewritten — see conceptual-workflows-init-reconcile.

Prompts only when standard output is a terminal. Without a terminal it takes flags, then the answers recorded in `.lore/config.toml`, then built-in defaults, and never blocks.

| Flag | Type | Default | Answers |
|---|---|---|---|
| `--agent ID [ID ...]` | `SpaceSeparatedChoice` over registry ids | recorded `init-agents`, else none | which coding agents the project uses |
| `--access {cli,native}` | `click.Choice` | recorded `init-access-mode`, else `native` | whether skills use the Lore CLI or the agent's own tools |
| `--skills FAMILY [FAMILY ...]` | `SpaceSeparatedChoice` over `memory` `machinery` `workflow` `all` `none` | recorded `init-skill-families`, else all three | which skill families install |
| `--on-existing-agent-file {append,skip}` | `click.Choice` | `append` | what to do with an instruction file that has no Lore markers |
| `--skills-gitignore {lore-only,none,all}` | `click.Choice` | recorded `init-skills-gitignore`, else `lore-only` | how installed skills are tracked in git |
| `--on-conflict {skip,overwrite}` | `click.Choice` | `skip` | what to do with a file Lore did not install, sitting where Lore would write; no say over Lore's own files |
| `-y, --yes` | flag | off | accept every prompt without asking |
| `--reconfigure` | flag | off | re-prompt for the four recorded answers; needs a terminal, or all four as flags |
| `--dry-run` | flag | off | print the plan, write nothing, exit 0 |

`cli.py` reads no config key. Every unset flag arrives as `None` and `plan_init` resolves argument → `.lore/config.toml` → built-in default; the prompts preselect from the plan's own answers (ADR-011, `decisions-021-health-reports-are-ephemeral-by-default` constraint 2).

`--agent none` combined with another id is a usage error at exit 2: `--agent none cannot be combined with other agents.` The rule lives in `validators.validate_agent_selection`, which `plan_init` calls too, so a Python caller is rejected identically. A run whose *recorded* answer breaks that rule — or any other token `plan_init` refuses — exits 1 with the same message plus the config key holding it and the flag that replaces it; it is never a traceback.

`--reconfigure` without a terminal is a usage error at exit 2 unless all four recorded answers arrive as flags: there is no prompt to ask in, and resolving those four to their built-in defaults would deselect every agent and uninstall what the project has.

Does NOT support `--json` — the flag is accepted, has no effect, and the command exits 0. See conceptual-workflows-lore-init, conceptual-workflows-init-interactive, tech-arch-agents-md.

### `lore oracle`

Writes per-quest markdown reports under `.lore/codex/transient/oracle/`. Slug derivation in `lore.cli.oracle.slugify` (mirrors GitHub anchor rules). Does NOT support `--json`.

### `lore health`

Audits the eight file-based entity types, JSON-Schema-validates entity files, audits codex `binds:` and codex `rites:` reference integrity, audits canonical codex prose against the voice rules, and audits the installed skills against the install manifest. Scopes: `codex`, `artifacts`, `doctrines`, `knights`, `watchers`, `schemas`, `glossary`, `bindings`, `rites`, `voice`, `skills`. `None` (default) runs every scope. Exit code is 1 on any error, 0 otherwise. Warnings never affect exit code. `--json` returns `{"errors": [...], "warnings": [...]}`.

```
lore health --scope voice
lore health --scope codex voice
```

The `voice` scope emits warnings only — every `voice_*` row is a `warning` and none escalates, so `--scope voice` never changes the exit code (`decisions-020-codex-voice-is-enforced`). It reports five checks (`voice_past_narration`, `voice_expiry_hedge`, `voice_forward_promise`, `voice_dangling_deixis`, `voice_sales_register`) over canonical codex layers, skipping `sources/` and `vision/` outright; `lore artifact show codex-voice` is the normative rule set.
 The `bindings` scope emits `dead_binding` (error) for literal `binds:` paths missing on disk and `empty_glob_binding` (warning) for glob patterns matching zero files; both `HealthIssue` rows carry `entity_type="codex"`, `id=<codex-id>`, and `schema_id`/`rule`/`pointer` all `null`. Codex schema validation uses the overlay-merged schema for canonical and `codex/sources/**` docs and the packaged schema only for `codex/transient/**` (ADR-019), so a project's custom required field never fails health's own transient reports. The `skills` scope reads `.lore/.install-manifest.json` and walks only the paths it names: `missing_skill_file` and `missing_skill_frontmatter` are errors, `modified_skill_file` and `retired_skill_present` are warnings, and a project with no manifest emits nothing. See conceptual-workflows-health.

The command has no retention flag. Whether a markdown report is persisted to `.lore/codex/transient/health-<timestamp>.md` is decided by the root-level `health-report-retention` key in `.lore/config.toml` — `none` (default, no file), `latest` (prune prior `health-*.md`, then write), `all` (write, prune nothing). The handler always calls `health_check(write_report=True, timestamp=...)` and passes no `retention`; `health_check` reads the key, so a Python caller gets the same policy (ADR-011, `decisions-021-health-reports-are-ephemeral-by-default`). Persistence is independent of `--json` and never affects the exit code.

## Shape — command tree

```
lore                       (dashboard)
lore init
lore stats
lore new {quest|mission}
lore list
lore missions [<quest-id>]
lore show <id>
lore edit <id> [flags]
lore delete <id>
lore claim <id>...
lore done <id>...
lore block <id> "<reason>"
lore unblock <id>
lore needs <A:B>...
lore unneed <A:B>...
lore ready [<count>]
lore doctrine {list|show|new}
lore knight    {list|show|new|edit|delete}
lore watcher   {list|show|new|edit|delete}
lore artifact  {list|show|new}
lore rite      {list|show|search|new|edit|delete}
lore codex     {list|show|search|map|chaos}
lore impacts   <codex-id|path> [--direct-links]
lore glossary  {list|show|search}
lore board     {add|delete}
lore oracle
lore health   [--scope SCOPE ...]
```

## JSON envelope contract

The `--json` output contract is hand-written in CLI handlers (`src/lore/cli.py`) and the canonical reference is `lore <command> --json` against a real database. Cross-cutting rules:

- Errors always emit to stderr as `{"error": "<message>"}`. Stdout receives only the success envelope.
- `lore show <quest-id> --json` always includes a `"missions"` array, a `"board"` array (possibly empty), and per-mission `"dependencies"` with `"needs"` and `"blocks"` (always present, possibly empty). `deleted_at` is never included on board messages — soft-deleted rows are filtered at the SQL layer.
- IDs in `"dependencies"` are always fully-qualified (`q-.../m-...`). `"needs"` and `"blocks"` contain only direct neighbours; transitive chains are not pre-computed.
- `lore show <mission-id> --json` includes `knight_contents` (full knight markdown) unless `--no-knight` is passed.

For exhaustive shape, run the command. Don't hand-decode from this doc.
