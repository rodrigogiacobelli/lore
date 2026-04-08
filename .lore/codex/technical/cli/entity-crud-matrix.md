---
id: tech-cli-entity-crud-matrix
title: CLI Entity CRUD Matrix
summary: Maps every Lore entity to its available CLI CRUD and traversal operations with the exact command for each. Highlights gaps — Codex and Artifact have no CLI write path; Board has no standalone list or update; Quest/Mission have no search; lore deps is documented but unimplemented. All five list commands (codex, artifact, knight, doctrine, watcher) support --filter GROUP... for namespace scoping.
related: ["tech-api-surface", "tech-cli-commands", "tech-arch-codex-map", "tech-arch-codex-chaos", "conceptual-workflows-filter-list"]
stability: stable
---

# CLI Entity CRUD Matrix

| Entity | Create | Read/Show | List | Search | Traverse | Update | Delete |
|--------|--------|-----------|------|--------|----------|--------|--------|
| **Quest** | `lore new quest <title>` | `lore show <id>` | `lore list [--all]` | — | — | `lore edit <id>` | `lore delete <id> [--cascade]` |
| **Mission** | `lore new mission <title>` | `lore show <id> [--no-knight]` | `lore missions [quest_id] [--all]` | — | — | `lore edit <id>` | `lore delete <id>` |
| **Knight** | `lore knight new <name>` | `lore knight show <name>` | `lore knight list [--filter GROUP...]` | — | — | `lore knight edit <name>` | `lore knight delete <name>` |
| **Doctrine** | `lore doctrine new <name>` | `lore doctrine show <name>` | `lore doctrine list [--filter GROUP...]` | — | — | `lore doctrine edit <name>` | `lore doctrine delete <name>` |
| **Watcher** | `lore watcher new <name>` | `lore watcher show <name>` | `lore watcher list [--filter GROUP...]` | — | — | `lore watcher edit <name>` | `lore watcher delete <name>` |
| **Codex** | ✗ (disk only) | `lore codex show <id> [id2…]` | `lore codex list [--filter GROUP...]` | `lore codex search <kw>` | `lore codex map <id> [--depth n]`<br>`lore codex chaos <id> --threshold <int>` | ✗ (disk only) | ✗ (disk only) |
| **Artifact** | ✗ (disk only) | `lore artifact show <id> [id2…]` | `lore artifact list [--filter GROUP...]` | — | — | ✗ (disk only) | ✗ (disk only) |
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

## Gaps

| Entity | Missing | Notes |
|--------|---------|-------|
| **Codex** | Create, Update, Delete | No CLI write path. Authoring is on-disk. Intentional — Codex is the human/agent record layer. |
| **Artifact** | Create, Update, Delete | Read-only via CLI by design. Maintainers author on disk. |
| **Board Message** | Update, standalone List | Append-only by design (ADR-009). Only visible inside `lore show`. |
| **Quest / Mission** | Search | No keyword search across titles or descriptions. |
| **Mission** | `lore deps` | CLI command is not implemented. Dependency info is embedded inside `lore show`. The shipped `AGENTS.md` template no longer references `lore deps` (removed in ADR-012 refactor). |
