---
id: conceptual-workflows-nested-projects
title: Nested Projects — reading across a tree of Lore projects
summary: 'The ancestor/descendant model a directory of several Lore projects forms
  — two independent axes (unconditional upward inheritance, opt-in downward federation),
  the --project read selector, origin-qualified addressing, the ORIGIN column and
  origin JSON field, and the read-only rule at a project boundary.

  '
binds:
- src/lore/projects.py
- src/lore/scoped.py
- src/lore/cli.py
- tests/e2e/test_nested_projects.py
- tests/e2e/test_nested_projects_cost.py
- tests/unit/test_cli_project_gate.py
- tests/unit/test_cli_origin_table.py
related:
- tech-arch-projects-module
- conceptual-workflows-codex
- conceptual-workflows-codex-map
- conceptual-workflows-glossary
- conceptual-entities-glossary
- conceptual-workflows-impacts
- conceptual-workflows-filter-list
- conceptual-workflows-help
- conceptual-workflows-error-handling
- conceptual-workflows-json-output
- tech-arch-initialized-project-structure
- ref-lore_cli-commands
- ref-lore_api-core
- decisions-006-id-references
- decisions-013-toml-for-config-yaml-for-glossary
- decisions-014-link-direction
- decisions-022-config-toml-tables-for-repeating-records
- decisions-023-export-boundary-excludes-transient-and-sources
- decisions-024-default-group-is-seeded-boundary
- decisions-025-cross-boundary-reads-are-read-only
- decisions-026-project-naming-and-addressing
- decisions-027-glossary-collision-resolves-local-first
- decisions-028-inheritance-unconditional-federation-opt-in
---

# Nested Projects

A directory that contains several Lore projects is itself a Lore project once its own `.lore/` exists. It gains two capabilities over that tree: it reads any project beneath it, and it exports selected authored entities down to the projects it names.

```
camelot/                      project-name = "camelot"
├── .lore/config.toml
├── lore/                      no project-name → "lore"
│   └── .lore/
├── realm/                     no project-name → "realm"
│   └── .lore/
└── citadel/                   no project-name → "citadel"
    └── .lore/
```

`camelot` is the **ancestor** of `lore`, `realm` and `citadel`; each of those is a **descendant** of `camelot`. A project may be an ancestor to some projects and a descendant of another at the same time — the relation is asymmetric per pair, not a global rank.

## Two independent axes

**Inheritance (upward) is unconditional.** A project always sees what its ancestors export to it, in the commands it already runs, with no flag. **Federation (downward) is opt-in.** Nothing walks the filesystem below a project unless a command asks for it with `--project`. `default-project-scope` governs the downward axis only — it never turns inheritance off, and it never turns federation on by default beyond what it names.

This split is why a project with no tree above or below it pays nothing for the feature: no ancestor probe finds anything to inherit, and no descendant walk runs unless `--project` names one. It is also why a descendant needs no configuration of its own to see what it inherits — nothing it can set turns inheritance off.

## Project naming

A project's name is its own `project-name` config key, or its directory name when that key is empty. No ancestor can rename a descendant — a `[[descendants]]` block's `name` field is a label for `lore health` messages and human readers, and has no resolving power. `--project <name>` and every origin qualifier use the project's own resolved name.

## Configuration — `.lore/config.toml`

Two root keys and two tables, all optional:

```toml
project-name = "camelot"
default-project-scope = "self"    # "self" | "all"

[shared]
exports = ["standards-*"]         # literal entity ids or glob patterns
glossary = true                   # export the whole glossary file

[[descendants]]
name = "lore"                     # a label; identity is `path`
path = "lore"                     # resolved beneath this project's root
exports = ["camelot-dispatch-contract"]
```

`[shared].exports` reaches every descendant discovered beneath the project; a `[[descendants]]` block's `exports` reaches only the one descendant whose `path` resolves to it. A project sees the union of both when it is that descendant. Neither table is seeded by `lore init` — `project-name` and `default-project-scope` are, at their defaults, because every known flat key is (`tech-arch-initialized-project-structure`).

An export entry is a literal entity id or a glob pattern, matched with `fnmatch.fnmatchcase` — never a path. No seeded default (a `default/` group) is ever exportable, and neither is a document under `.lore/codex/transient/` or `.lore/codex/sources/`: a transient document is deleted when its feature ships, and exporting one would guarantee a future dangling reference in a repository its owner cannot see.

## The `--project` read selector

`--project <name>` (or `all`, or `self`) is a global option accepted on 19 read commands: `codex list|show|search|map`, `doctrine list|show`, `knight list|show`, `artifact list|show`, `watcher list|show`, `rite list|show|search`, `glossary list|search|show`, and `impacts`. It is rejected — a usage error, exit 2 — on every write command and on every quest or mission command:

```
Error: --project is a read selector; it is not accepted on "codex new".
```

Omitting `--project` resolves `default-project-scope` (default `"self"`). The three forms:

| Scope | Reads |
|-------|-------|
| `self` | This project's own entities, plus what its ancestors export to it. |
| `<name>` | Only the named project's own entities — unfiltered, because an ancestor asking for a descendant by name wants that project's material, not its own exports reflected back. |
| `all` | This project, what it inherits, and every Lore project discovered beneath it. |

An unknown `--project` name fails at exit 1, not 2 — project names are discovered from the tree, not a fixed set:

```
Unknown project "nope". Projects in scope: citadel, lore, realm.
```

Discovery walks downward with `os.walk`, pruning `.git`, `node_modules`, `.venv`, `__pycache__` and the project's own `.lore/` directory, and follows no symlink. A directory holding `.lore/` is a project, and the walk continues into it, so a project nested inside a project is still found. Discovery runs only when the resolved scope is `all` or names a project — a bare command in a project with no tree performs zero directory scans, and probes upward for an exporting ancestor with one `Path.is_dir()` check per directory between the project root and the filesystem root.

## Origin-qualified addressing

An entity that did not originate in the reading project is addressed as `<project-name>:<entity-id>` — split on the **first** colon, because a codex id may itself contain one and a project name cannot (its grammar admits no `:`). A bare id always resolves locally first; a qualified id never resolves locally, even when a local document happens to share its exact text. `lore codex edit camelot:x` never matches a local document literally named `camelot:x`.

A `related` entry inside a document is read in the namespace of the project that wrote it: an ancestor's `related: [lore:tech-db-schema]` reduces to `tech-db-schema` when read from inside `lore`, because that qualifier is `lore`'s own name naming a document `lore` owns. Every other qualifier keeps its form. This is what lets an inherited document backlink to something the descendant already has, with no special case in the traversal.

## ORIGIN column and `origin` field

Every returned row, from every affected command, carries an `origin` value under `--json` — `"self"` for this project's own rows, else the originating project's name — always present, even in a project with no tree. Text mode adds a leading `ORIGIN` column, but only when the result set holds at least one non-`self` row; a project with no tree prints exactly what it printed before this feature existed. Sort order is unchanged — each command's existing sort key, applied to the id as returned, which is the qualified form for a foreign row.

## Read-only across a boundary

Every entity reached across a boundary is read-only. An edit, delete, or field-set against an origin-qualified id fails on every write path — `new`, `-f edit`, field-edit (`--set`/`--unset`/`--add`/`--remove`), and `delete` — with the same message on stderr at exit 1:

```
Cannot write "camelot:standards-naming": an entity from another project is read-only.
```

A Python caller reaching the same function directly gets `ForeignEntityError`, not a silent success — the rule is enforced once, in the core, and every write path calls it as its first statement. There is no `--force`, no push, no copy-on-read: an inherited or federated entity has exactly one authoritative copy, in the project that authored it.

The `native` access-mode carve-out (`decisions-006-id-references`) — an agent reading `.lore/codex/`, `.lore/rites/` or `glossary.yaml` with its own file tools instead of the CLI — does **not** cross a boundary. A foreign entity lives in a different repository, one this project's own `lore health` never audits, and is reachable only by origin-qualified id through the CLI or `lore.api`, in both access modes.

## Glossary inheritance

The glossary is exported whole or not at all — `[shared].glossary = true` — because a keyword is natural language matched against document prose, not an id, and there is no partial unit to export. An inherited keyword stays bare (never qualified): qualifying it would break the auto-surface matcher on `lore codex show`. On a keyword collision between a local item and an inherited one, the local item wins for every lookup that must answer with a single item (`read_glossary_item`, the auto-surface matcher); `lore glossary list` and `lore glossary search` show both rows, each carrying its origin, so the collision itself is visible.

## `lore health` reads no other project

A health run validates only the project it runs in, in every direction, with no exception. It never reads an ancestor's or a descendant's files, and an inherited or federated entity is never checked. This is a deliberate boundary, not an omission: cross-project visibility exists so an agent can read across a tree, not so one project can be judged by another's state. The one place this touches an existing check is the glossary audit — `lore health`'s duplicate-keyword and collision checks run over this project's own glossary file only, so an inherited keyword can never raise this project's exit code.

## `codex chaos` is excluded

`--project` is not accepted on `lore codex chaos`. Its termination ratio is defined over the reachable subgraph the seed can walk within one project; crossing a boundary would change what that ratio measures, and nothing requires it to.

## Python API

Every capability above is reachable from `lore.api` with the same arguments, return shapes and failure conditions as the CLI — see `ref-lore_api-core` for the exact names and `tech-arch-projects-module` for how `lore.projects` and `lore.scoped` implement the model.
