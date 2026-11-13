---
id: decisions-006-id-references
title: Agents reference entities by ID, never by file path
summary: 'ADR recording the decision that agents reach artifacts, doctrines, watchers
  and the other file features by ID through Lore CLI commands whenever the feature''s
  route is cli, rather than reading file paths directly; a harness route lifts the rule
  for that feature and action. This keeps the CLI the stable interface where a project
  chooses it and prevents agents from bypassing the abstraction layer.

  '
related:
- ref-lore_cli-commands
---

# ADR-006: Agents reference entities by ID, never by file path

## Context

Lore manages several categories of reusable entity: Doctrines (workflow
templates), Codex documents (project documentation), Watchers (reactive-agent
definitions), and Artifacts (reusable content templates). All of these live
on disk as files in predictable directory trees inside `.lore/`.

An agent that knows the file system layout can bypass the CLI entirely and
read any of these files directly — e.g. `Read .lore/artifacts/transient/business-spec.md`
or `cat .lore/doctrines/default/tdd-implementation/missions/red.md`. That works.
The question is whether it should be the intended usage.

## Decision

For every feature whose route is `cli`, agents must access Lore-managed
entities by ID through the CLI, not by constructing and reading file paths
directly.

- **Artifacts:** `lore artifact show <id>` — never read `.lore/artifacts/…` directly
- **Codex documents:** `lore codex show <id>` — never read `.lore/codex/…` directly
- **Doctrines:** `lore doctrine show <name>` — never read `.lore/doctrines/…` directly, and `lore doctrine show <name> --mission <id>` for one mission body

The same principle applies to default entities shipped inside the package
(`src/lore/defaults/`): agents should never construct paths into the package
source tree.

A doctrine's design document and every mission body must reference other
entities by their Lore ID, not by path. For example: "retrieve artifact
`transient-business-spec` with `lore artifact show transient-business-spec`"
— not "open `.lore/artifacts/transient/business-spec.md`".

### The harness route

`lore init` records, for each file feature (Memory, Doctrines, Artifacts,
Watchers) and for each action (read, write), a **route**: `cli` (agents reach
the files through `lore` commands), `harness` (agents use their own file tools)
or `off` (agents are not told). The by-ID rule binds a feature and an action
whose route is `cli`. For a route that is `harness`, the rule is lifted for that
feature and action:

- **Memory** (codex documents, rites and the glossary) — read and write
  `.lore/codex/<layer>/<id>.md`, `.lore/rites/main/` and `.lore/rites/shared/`,
  and `.lore/codex/glossary.yaml` directly.
- **Doctrines** — read and write the directory `.lore/doctrines/<group>/<id>/`.
- **Artifacts** — read and write `.lore/artifacts/`.
- **Watchers** — read and write `.lore/watchers/`.

`lore health` validates the result on every route, which is what makes direct
writes safe: `--scope schemas` for frontmatter, `--scope rites` for the rite
graph, `--scope glossary` for the glossary file, and the doctrine, artifact and
watcher scopes for their entities. An agent on a `harness` route owns what the
CLI would have done: frontmatter normalisation, id and filename agreement, and
reading a `default/` versus flat directory split. Each seeded skill states that
cost where the agent reads it.

Lore-shipped reference documents (the codex voice rules, the rite design guide,
the doctrine, mission and inquest design documents, the codex skeleton) are
named by ID with `lore artifact show` when Artifacts is on the `cli` read route,
and by their path under `.lore/artifacts/default/` when Artifacts is on any other
route.

The rule holds unchanged for everything else, whatever the routes:

- **Any feature whose route is `cli`** — by ID through the CLI. Every one of
  these hides a `default/` versus flat-directory split, slash-derived groups and
  `.deleted` soft-delete naming, and `lore doctrine show` additionally assembles
  a mission index across a directory. This is the layout-is-an-implementation-detail
  argument at its strongest.
- **Quests, missions, board messages, dependencies** — SQLite-backed; there is no
  file to read.
- **`lore codex map`, `lore codex chaos`, `lore impacts`, `lore index`** — a
  two-budget directional BFS, a random walk with a reachable-subgraph termination
  ratio, a bidirectional `binds:` index, and a partition computed on demand. No file
  read reproduces them, so they are CLI commands wherever a project turns on the
  capability.
- **`lore health`** — it is the validator the harness route leans on.

The test that draws the line: a command stays CLI-only when it does something a
file tool cannot reproduce. Reading a markdown file is reproducible; traversing a
graph is not.

An agent on the harness route for Memory gives up the glossary auto-surface on
`lore codex show`, multi-ID deduplication, and group derivation.

## Rationale

**The CLI is the stable interface; file paths are an implementation detail.**
The directory layout of `.lore/` can change across Lore versions without a
breaking change if the CLI surface stays stable. Agents that hardcode paths
will break silently when the layout changes. Agents that use CLI commands
won't notice.

**Tool call cost matters.** An agent that reads a file at a known path is
using a general-purpose tool call (Read, Bash). An agent that calls
`lore artifact show` is using one targeted CLI call. The CLI result is
already filtered, formatted, and ID-validated. There is no second trip to
discover the path.

**Enforcing tool use keeps orientation predictable.** If agents use the CLI,
the only way to retrieve an artifact is to know its ID. That means every
doctrine design document and mission body that references an artifact must state
the ID explicitly. This is self-documenting: an agent reading a mission body can
immediately execute `lore artifact show <id>` without any prior knowledge of
directory structure.

**Parallel to ADR-004 (mission_type).** ADR-004 established that Lore stores
and exposes data but does not interpret it — interpretation belongs to the
consumer. This ADR applies the same boundary in the opposite direction: the
CLI exposes entities by ID; file-path knowledge belongs to the implementation,
not to consumers (agents).

## Consequences

- Every doctrine design document and mission body that references an entity must
  use its ID with the relevant `lore` command, not a file path.
- Every mission body that directs an agent to use a template or another entity
  must name the entity ID and the retrieval command.
- The agent instruction file Lore renders (`.lore/LORE-AGENT.md` and each
  selected agent's marked block) instructs the CLI for the features whose route
  is `cli` and file paths for the features whose route is `harness`, and names no
  command whose capability is off.
- Writers of new Doctrines must follow this convention or their work is
  non-conforming.
- The `lore artifact list` command becomes critical for discovery: agents
  that don't know an ID upfront must list first, then show.

## Alternatives considered

**Allow both file paths and CLI commands.** Rejected. Dual pathways create
inconsistency and erode the abstraction. Once agents know they can read files
directly, they will do so opportunistically, and the CLI layer becomes
vestigial.

**Store IDs in a registry separate from files.** Rejected. The existing
frontmatter pattern (each file declares its own `id`) is already the
registry. The CLI reads frontmatter at access time; no separate index is
needed.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-03-31 | accepted | Initial decision. Recorded with the first public release. |
| 2026-08-25 | accepted (scope narrowed) | Carve-out added for the `native` access mode: codex documents, rites and the glossary may be read and written with an agent's own file tools, validated afterwards by `lore health`. Artifacts, knights, doctrines, watchers, the graph commands and the SQLite-backed entities keep the by-ID rule in both modes. |
| 2026-09-16 | accepted | Decision unchanged. The enumeration of entity categories loses Knights, which no longer exist; `lore doctrine show` is the by-ID reach for both a doctrine's design and one mission body. The carve-out's stated reason for keeping doctrines CLI-only is rewritten to the surviving one — a doctrine still hides a `default/` split, slash-derived groups and `.deleted` naming, and `lore doctrine show` assembles a mission index across a directory. |
| 2026-10-30 | accepted (carve-out extended) | The by-ID rule binds a feature and an action whose route is `cli`. The carve-out that covered codex documents, rites and the glossary under the `native` access mode extends to Doctrines, Artifacts and Watchers under a `harness` route, answered separately for reading and for writing. The sentence "in both modes" is replaced by the per-feature rule, and the consequence about the agent instruction file now follows each feature's route. Lore-shipped reference documents are read by path when Artifacts is not on the `cli` read route. |
