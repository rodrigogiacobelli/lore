---
id: codex-index-prd
title: Codex Index — PRD
summary: A clustered, authored index over the codex `related` graph, built and searched by two new lore commands, so a cold agent routes to the right documents in one call instead of searching the corpus.
related:
  - decisions-010-public-api-stability
  - decisions-011-api-parity-with-cli
  - decisions-018-overlays-are-path-discovered-config
  - decisions-021-health-reports-are-ephemeral-by-default
  - decisions-025-cross-boundary-reads-are-read-only
  - conceptual-workflows-codex-map
  - conceptual-workflows-health
  - conceptual-workflows-impacts
  - tech-arch-schemas
  - conceptual-entities-skill
---

# Codex Index — PRD

## Executive Summary

An agent that opens a codex cold does not know where anything is. It searches the
corpus, reads what the search returns, and discards the map when its context
ends. The next agent repeats the search.

The Codex Index gives that agent an entry point. Lore partitions the authored
`related` graph into a few dozen **nodes** — clusters of documents that link
densely to each other — and a human or agent writes one name and one summary per
node. The result is a small file an agent searches first: it names a node, and
the node names its member documents and their paths.

Two commands carry it. `lore index build` clusters and renders. `lore index
search` refreshes the render if the codex has moved, then matches. Clustering is
deterministic and calls no model, so the refresh is free and the index is never
stale.

Measured on an 857-document codex, searching a node index instead of the corpus
reduced retrieval cost by 45%.

## Project Classification

Lore is a CLI tool and an importable Python library. Its users are AI agents
driving the CLI, human developers at a terminal, Realm consuming
`from lore.api import ...`, and downstream projects that receive
`src/lore/defaults/` on `lore init`.

This feature adds a command group, a core module, two public API callables, one
packaged schema, one `lore health` scope, one seeded skill, and an edit to two
seeded doctrine missions. It adds no database table and no migration.

## Problem and Users

**The AI agent** is the primary user, in its cold state. A worker dispatched to a
mission, a scout opening a codex it has never read, a fresh session — each starts
without knowing which documents govern its task. The only entry points today are
`lore codex list`, which returns every document, and `lore codex search`, which
matches words against titles and summaries and misses whenever the agent's
vocabulary differs from the codex's. `lore codex map` traverses the graph but
requires a seed document the agent must already know.

**The human developer** has the same problem on arrival at an unfamiliar project,
and additionally owns the index: the names and summaries are theirs to write.

**Realm** reaches the same capability through `lore.api`, because every mission
it dispatches starts a cold agent.

**A downstream project** receives the skill that authors the index and the
doctrine steps that keep it current.

## Success Criteria

**For the calling agent.** A codex question is answered in one command plus the
document reads it implies, rather than a search-read-search loop. A result names
the documents to open and their paths, so no second lookup resolves an id to a
file. A result always describes the codex as it is now.

**For the human developer and Realm.** The index costs one authoring pass per
project and a few sentences per changed cluster thereafter. `lore health --scope
index` names every node whose summary no longer matches the documents under it,
so drift is reported rather than discovered.

## Scope

### In scope

- `lore index build` and `lore.api.build_index` — partition the `related` graph,
  render the index, report unauthored and drifted nodes.
- `lore index search` and `lore.api.search_index` — refresh when stale, then
  match.
- `.lore/index/authored.yaml` — the authored half: one entry per node.
- `.lore/index/codex.json` — the rendered half: generated, git-ignored.
- `src/lore/schemas/index-authored.yaml` — the packaged schema for the authored
  file.
- `lore health --scope index`.
- A seeded `update-index` skill that authors and re-authors the file.
- A closing index step in the `codex-apply` mission of `feature-implementation`
  and `quick-feature-implementation`.
- Index-aware retrieval in the seeded `retrieve-memory` skill, and the closing
  index step in the seeded `store-memory` skill.
- A `defaults/gitignore` change that commits `index/authored.yaml` and ignores
  `index/codex.json`.

### Out of scope

- **Code indexing.** Parsing source with tree-sitter and indexing symbols is a
  later feature. The `.lore/index/` directory and the `lore index` group are
  named to accommodate it; nothing in this feature reads code.
- **`--project`.** `lore index search` is local-only. Refreshing a foreign
  project's index would write outside the project Lore runs in, which ADR-025
  forbids, and reading one without refreshing would return results of unknown
  age under a command whose contract is freshness.
- **A `lore index show <slug>` retrieval command.** The authored file is
  project configuration addressed by its path, not a Lore entity addressed by an
  id (ADR-018).
- **Model calls inside a command.** Summaries are authored by the skill. No
  `lore` command calls a language model, reads an API key, or touches the
  network.
- **A `--no-refresh` escape hatch.** `lore index search` always refreshes.
- **Automatic invocation.** No hook, no daemon, no watch loop. The commands run
  when a caller runs them.

## Workflows

### Build the index

**CLI.** `lore index build` partitions the `related` graph over
`.lore/codex/`, writes `.lore/index/codex.json`, and prints a table of nodes with
their member counts, followed by the nodes needing attention:

```
  SLUG                     NAME                  MEMBERS  STATUS
  install-and-seeding      Install and Seeding        16  ok
  (unauthored)             hub: tech-arch-lsp          4  unauthored
  database-and-storage     Database and Storage        6  drifted
```

Exit 0 whether or not nodes need attention — an unauthored cluster is a state to
report, not a failure. Exit 1 with the error envelope on stderr when `.lore/` is
absent or `authored.yaml` is unreadable.

`lore --json index build` returns
`{"nodes": [{slug, name, hub, members, member_paths, status}], "unauthored": N, "drifted": N}`,
where `status` is `ok`, `unauthored`, or `drifted`, and `slug` and `name` are
`null` for an unauthored node.

**Python.** `lore.api.build_index(project_root) -> dict` returns the same
structure. It raises `IndexError` — a `ValueError` subclass named for this
feature — when the authored file is present but unparseable.

### Search the index

**CLI.** `lore index search <keyword>` refreshes `codex.json` if the codex has
changed since it was rendered, then matches `<keyword>` case-insensitively
against each node's name, summary, and member ids, printing the matching nodes
with their members:

```
  install-and-seeding — Install and Seeding
    lore init writes the project, reconciles on upgrade, and owns what it seeded.
    conceptual-workflows-lore-init      conceptual/workflows/lore-init.md
    tech-arch-install-manifest          technical/architecture/install-manifest.md
```

Exit 0 with no output when nothing matches. Exit 1 with the error envelope when
`.lore/index/authored.yaml` does not exist, carrying the message
`no index authored for this project. Run the update-index skill to author it.`
`--project` is refused at exit 2, because `index search` is not in
`_PROJECT_READ_COMMANDS`.

`lore --json index search <keyword>` returns
`{"nodes": [{slug, name, summary, hub, members, member_paths}]}`.

**Python.** `lore.api.search_index(project_root, keyword) -> list[dict]` returns
the same node list and refreshes identically. It raises `IndexNotAuthoredError`
when the authored file is absent.

### Author the index the first time

A human or agent runs the `update-index` skill. The skill runs `lore index
build`, reads each unauthored cluster's member titles and summaries, writes a
`name` and a `summary` per node into `.lore/index/authored.yaml` along with the
digest each summary was authored against, and runs `lore index build` again to
confirm every node reports `ok`.

### Keep the index current

The `codex-apply` mission of `feature-implementation` and
`quick-feature-implementation` closes by running `lore index build`, reading the
unauthored and drifted rows, updating those entries in `.lore/index/authored.yaml`
from the documents already in its context, and rebuilding. The seeded
`store-memory` skill closes the same way, because it writes codex documents
outside any doctrine.

### Retrieve through the index

The seeded `retrieve-memory` skill runs `lore index search` first when it opens
a codex cold, and falls back to searching the corpus when the search matches
nothing or reports that no index is authored. When the documents it needs are
already in its context, it answers from context and re-reads only a document that
may have changed.

### Audit the index

`lore health --scope index` reports:

- **error** — `authored.yaml` fails its schema; an entry's `hub` names no
  document in the codex.
- **warning** — a cluster has no authored entry; an entry's `authored_against`
  digest no longer matches its members.

## Functional Requirements

1. Lore partitions the `related` graph of `.lore/codex/` into nodes
   deterministically: the same codex produces the same partition on every run,
   on every machine.
2. Lore derives each node's hub — the member most linked to the rest of its own
   node — and keys authored entries by that hub, so an entry stays attached to
   its node as membership shifts.
3. Lore renders each node with its member ids and each member's path relative to
   the codex root, so a caller opens a document without resolving its id.
4. Lore records, per authored entry, a digest of the members and their content at
   the moment the summary was written.
5. Lore refreshes the rendered index before a search whenever the codex has
   changed since the render, without calling a model or the network.
6. Lore reports a node whose members or their content have changed since its
   summary was authored.
7. Lore reports a cluster with no authored entry.
8. Lore refuses to search an index that has never been authored, and names the
   skill that authors it.
9. Every capability is a core function that the Click command wraps and
   `lore.api` re-exports.

## Non-Functional Requirements

**Round-trips.** ADR-001 makes tool calls the performance budget. Answering a
codex question from cold costs one `lore index search` plus the reads of the
documents it names. The refresh inside that command is not a second call.

**Determinism.** The partition is a pure function of the codex. No model, no
API key, no network, no randomness that is not seeded.

**Reliability.** The rendered index is a cache: deleting `.lore/index/codex.json`
loses nothing, and the next search rebuilds it. `authored.yaml` is the only file
whose loss is not recoverable by rebuilding, and it is committed.

**Concurrency.** Two processes searching at once may both refresh. The render is
written atomically so a reader never sees a partial file.

**Security.** Lore has no auth surface — local filesystem and SQLite only. This
feature reads the codex and writes inside `.lore/` of the project it runs in.

## Maintainer Story

**Upgrading.** `lore init` installs the `update-index` skill and the two edited
`codex-apply` missions. A project that has never authored an index is unaffected
until it runs the skill: `lore index search` reports that no index is authored,
and no other command changes behaviour.

**Seeding.** `src/lore/defaults/skills-catalogue.yaml` gains an `update-index`
entry in the `machinery` family. `src/lore/defaults/gitignore` gains an
un-ignore for `index/authored.yaml` while `index/codex.json` stays ignored.

**Schema.** `src/lore/schemas/index-authored.yaml` ships as packaged data.

**Health.** `_ALL_SCOPES` in `health.py` and the duplicated `_VALID_SCOPES` in
`cli.py` both gain `index`.

**Database.** No table, no migration. The index lives on the filesystem.

**Changelog.** `CHANGELOG.md` records the `lore index` command group,
`build_index` and `search_index` — a minor bump under ADR-010 — the `index`
health scope, and the `update-index` skill.

## Pre-Architecture Notes
