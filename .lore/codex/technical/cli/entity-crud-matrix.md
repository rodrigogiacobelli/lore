---
id: tech-cli-entity-crud-matrix
title: CLI Entity CRUD Matrix
summary: Maps every Lore entity to its available CLI CRUD and traversal operations with the exact command for each. Highlights gaps — Codex has no CLI write path; Artifact gained a `new` write path (first CLI write for artifacts); Board has no standalone list or update; Quest/Mission have no search; lore deps is documented but unimplemented. All five list commands (codex, artifact, knight, doctrine, watcher) support --filter GROUP... (slash-delimited segment-prefix matching) and all four entity `new` commands (doctrine, knight, watcher, artifact) support --group GROUP for nested creation.
related: ["tech-api-surface", "tech-cli-commands", "tech-arch-codex-map", "tech-arch-codex-chaos", "conceptual-workflows-filter-list", "conceptual-workflows-health"]
stability: stable
---

# CLI Entity CRUD Matrix

| Entity | Create | Read/Show | List | Search | Traverse | Update | Delete |
|--------|--------|-----------|------|--------|----------|--------|--------|
| **Quest** | `lore new quest <title>` | `lore show <id>` | `lore list [--all]` | — | — | `lore edit <id>` | `lore delete <id> [--cascade]` |
| **Mission** | `lore new mission <title>` | `lore show <id> [--no-knight]` | `lore missions [quest_id] [--all]` | — | — | `lore edit <id>` | `lore delete <id>` |
| **Knight** | `lore knight new <name> [--group <path>]` | `lore knight show <name>` | `lore knight list [--filter GROUP...]` | — | — | `lore knight edit <name>` | `lore knight delete <name>` |
| **Doctrine** | `lore doctrine new <name> [--group <path>] -f <yaml> -d <design>` | `lore doctrine show <name>` | `lore doctrine list [--filter GROUP...]` | — | — | `lore doctrine edit <name>` | `lore doctrine delete <name>` |
| **Watcher** | `lore watcher new <name> [--group <path>]` | `lore watcher show <name>` | `lore watcher list [--filter GROUP...]` | — | — | `lore watcher edit <name>` | `lore watcher delete <name>` |
| **Codex** | ✗ (disk only) | `lore codex show <id> [id2…]` | `lore codex list [--filter GROUP...]` | `lore codex search <kw>` | `lore codex map <id> [--depth n]`<br>`lore codex chaos <id> --threshold <int>` | ✗ (disk only) | ✗ (disk only) |
| **Artifact** | `lore artifact new <name> [--group <path>] --from <body>` | `lore artifact show <id> [id2…]` | `lore artifact list [--filter GROUP...]` | — | — | ✗ (disk only) | ✗ (disk only) |
| **Board Message** | `lore board add <entity_id> "<msg>" [-s sender]` | (inside `lore show`) | (inside `lore show`) | — | — | ✗ (immutable) | `lore board delete <int_id>` |

## Lifecycle Operations

Quest and Mission have additional lifecycle commands beyond CRUD.

| Operation | Quest | Mission |
|-----------|-------|---------|
| Claim (→ in_progress) | `lore claim <id>` | `lore claim <id>` |
| Close | `lore done <id>` | `lore done <id>` |
| Block | — (status is derived) | `lore block <id> "<reason>"` |
| Unblock | — | `lore unblock <id>` |
| Top priority unblocked | — | `lore ready [count]` |

## Dependency Operations (Mission only)

| Operation | Command |
|-----------|---------|
| Declare dependency | `lore needs <id>:<dep_id> [more pairs…]` |
| Remove dependency | `lore unneed <id>:<dep_id> [more pairs…]` |
| Show dependencies | embedded in `lore show <mission_id>` |
| Standalone `lore deps` | ✗ not implemented — dependency info embedded in `lore show` |

## `--group` parameter on entity `new`

| Entity | `new` accepts `--group`? | Helper called | Notes |
|--------|--------------------------|---------------|-------|
| **Doctrine** | yes | `lore.doctrine.create_doctrine(..., group=...)` | Subtree-wide duplicate check via `rglob`; mkdir before write. |
| **Knight** | yes | `lore.knight.create_knight(knights_dir, name, content, group=...)` | `create_knight` introduced this release — previously inline in `cli.py`. |
| **Watcher** | yes | `lore.watcher.create_watcher(watchers_dir, name, content, group=...)` | YAML parse-check still runs before write. |
| **Artifact** | yes | `lore.artifact.create_artifact(artifacts_dir, name, content, group=...)` | New helper; first artifact write path. Strict frontmatter required. |

`--group` is slash-delimited (`a/b/c`), validated by `lore.validators.validate_group`, and omitted means the entity root. Duplicate detection is always subtree-wide regardless of group. CLI handlers are thin wrappers — all validation, mkdir, and writing happens inside the core helpers, giving identical behaviour to the Python API (`group=` kwarg).

## Diagnostic Operations

| Command | Description |
|---------|-------------|
| `lore health [--scope TYPE [TYPE ...]] [--json]` | Audit all five file-based entity types (or a subset via `--scope`) and report errors/warnings. Exits `1` on any error, `0` on clean or warnings-only. Writes a markdown report to `.lore/codex/transient/` on every run. |

## Gaps

| Entity | Missing | Notes |
|--------|---------|-------|
| **Codex** | Create, Update, Delete | No CLI write path. Authoring is on-disk. Intentional — Codex is the human/agent record layer. The feature's list display and `--filter` grammar change applies to codex in lock-step, but no write path is introduced. |
| **Artifact** | Update, Delete | `Create` landed via `lore artifact new` — first CLI write path for artifacts. Update and delete remain on-disk. |
| **Board Message** | Update, standalone List | Append-only by design (ADR-009). Only visible inside `lore show`. |
| **Quest / Mission** | Search | No keyword search across titles or descriptions. |
| **Mission** | `lore deps` | CLI command is not implemented. Dependency info is embedded inside `lore show`. The shipped `AGENTS.md` template no longer references `lore deps` (removed in ADR-012 refactor). |
