---
id: conceptual-workflows-index
title: lore index Behaviour
summary: What the system does when `lore index build` and `lore index search` run —
  the codex index routes a cold read into the codex by cluster. Covers the partition,
  the two files under `.lore/index/`, the four cluster statuses (`ok`, `unauthored`,
  `drifted`, plus the stale entries the partition left behind), the stat-fingerprint
  refresh a search performs before matching, both human and `--json` output shapes,
  the exit-code contract, the `--project` refusal, and the Python API via
  `build_index()` and `search_index()`.
binds:
- src/lore/index.py
- src/lore/cli.py
- tests/e2e/test_index.py
- tests/e2e/test_api_parity_index.py
- tests/unit/test_index_authored.py
- tests/unit/test_index_digest.py
- tests/unit/test_index_partition.py
- tests/unit/test_index_refresh.py
related:
- conceptual-workflows-codex
- conceptual-workflows-codex-map
- conceptual-workflows-health
- conceptual-workflows-json-output
- conceptual-workflows-error-handling
- conceptual-workflows-nested-projects
- conceptual-entities-skill
- tech-arch-codex-index
- tech-arch-graph
- decisions-035-node-is-a-document-cluster-is-a-set
- decisions-036-index-partitions-the-local-canonical-codex
- decisions-037-index-is-a-top-level-lore-directory
- decisions-038-partition-is-deterministic-modularity-local-moving
- decisions-039-authored-entry-is-keyed-by-its-hub
- decisions-041-render-is-a-cache-invalidated-by-a-stat-fingerprint
- decisions-042-index-search-prints-a-no-match-sentence
- ref-lore_cli-commands
- ref-lore_api-core
---

# lore index Behaviour

A codex is a graph of documents joined by `related`. The codex index partitions
that graph into **clusters** of densely linked documents, names each cluster's
**hub**, and answers a keyword with the clusters it lives in — so an agent
opening a codex cold starts at a named group of documents instead of at the
whole corpus. A node is one codex document; a cluster is a set of them
(`decisions-035-node-is-a-document-cluster-is-a-set`).

The index has two halves, both under `.lore/index/`:

| File | Written by | Tracked | What it holds |
|---|---|---|---|
| `authored.yaml` | a person, or the `update-index` skill | committed | one entry per cluster, keyed by that cluster's hub: `slug`, `name`, `summary`, `authored_against` |
| `codex.json` | `lore index build` and the refresh inside `lore index search` | git-ignored | the partition, plus the fingerprint it was taken at |

**No Lore command creates, edits or deletes `authored.yaml`**
(`decisions-039-authored-entry-is-keyed-by-its-hub`). It is the only file in the
index a rebuild cannot recover. `codex.json` is a pure cache: deleting it loses
nothing, because the next command rebuilds it
(`decisions-041-render-is-a-cache-invalidated-by-a-stat-fingerprint`).

## What the index covers

The index partitions this project's own canonical codex. Documents under
`transient/` and `sources/` are excluded, and no other project's documents are
read (`decisions-036-index-partitions-the-local-canonical-codex`). A document
becomes indexable by graduating out of `transient/`.

Two documents are joined when either names the other in `related`. A document
that names itself is not joined to itself.

## Preconditions

- The caller runs inside a Lore project.
- `.lore/index/authored.yaml` is optional for `lore index build` and required
  for `lore index search`.

## Invocation

```
lore index build
lore index search <keyword>
lore --json index build
lore --json index search <keyword>
```

Neither subcommand takes a local `--json` flag; both carry their envelope
through the global flag (`conceptual-workflows-json-output`).

`--project` is refused on both. The index is built from, and written into, the
project Lore runs in — see `conceptual-workflows-nested-projects`.

## lore index build

The unconditional rebuild. It never consults the stored render, so the render
stays a pure function of the codex, and it is the answer to any doubt about what
the partition holds.

### Steps

1. **Fingerprint the codex** — one `stat` per indexed document, hashed with each
   document's path and size. Taken before the partition, so a document edited
   while the build runs leaves a fingerprint the next search disagrees with
   rather than one it trusts.
2. **Partition the `related` graph** into clusters, and name each cluster's hub.
3. **Digest each cluster** over its membership and its members' content, scoped
   to the cluster — so a document changing elsewhere in the codex cannot move
   it.
4. **Write the render** whole, through the atomic write gate.
5. **Read `.lore/index/authored.yaml`** if it exists. A missing file is a valid
   state, reported as every cluster `unauthored` rather than as a failure.
6. **Classify** every cluster against the authored entries, and every entry
   against the partition.

### The four states

| State | Meaning |
|---|---|
| `ok` | the cluster's hub has an entry carrying the cluster's current digest |
| `unauthored` | the cluster's hub has no entry |
| `drifted` | the entry was authored against another digest — the summary describes documents that have since changed |
| stale entry | an entry whose hub heads no cluster; reported below the table, not as a cluster row |

A stale entry carries one of two reasons: the hub is still a document in this
codex but no longer heads a cluster, or the hub is not a document in this codex
at all. Nothing is re-keyed automatically — attaching a hand-written summary to
a set of documents nobody has checked is the failure the `drifted` status exists
to prevent.

### Output

Rows are ordered by status (`ok`, then `unauthored`, then `drifted`), then by
descending member count, then by ascending hub. A cluster with no entry shows
`(unauthored)` where its slug would go and `hub: <hub>` where its name would go.

```
$ lore index build
  SLUG          NAME                          MEMBERS  STATUS
  authoring     Authoring the codex           16       ok
  (unauthored)  hub: ref-lore_cli-commands    13       unauthored
  storage       Storage and schemas           9        drifted
3 clusters — 1 unauthored, 1 drifted.
Stale entry "retired-flow": hub conceptual-workflows-old heads no cluster.
```

A codex with no indexable documents prints `No codex documents to index.` and
nothing else.

Under `--json`, the same state is the ordinary envelope: `clusters` (each with
`slug`, `name`, `hub`, `status`, `members`, `member_paths`), `unauthored`,
`drifted`, and `stale`. An unauthored cluster carries `null` for `slug` and
`name`.

Every state above is a state to report, so `lore index build` exits **0** in all
of them.

## lore index search

### Steps

1. **Read `.lore/index/authored.yaml`.** A missing file fails the command — the
   search has no names or summaries to answer with.
2. **Refresh the render** — recompute the fingerprint and rebuild only if it
   differs from the stored one. On a warm codex this costs one `stat` per
   document and no rebuild.
3. **Match** the keyword case-insensitively, as a substring, against each
   cluster's member ids, and against its name and summary when it has an entry.
   An unauthored cluster matches on member ids alone: hiding the clusters nobody
   has written up yet would leave documents the index knows about unreachable
   through the command whose job is reaching them. A slug is never matched — it
   is the display key of a row, and no command resolves a cluster by it.
4. **Order** authored clusters first by ascending slug, then unauthored clusters
   by ascending hub.

### Output

Each cluster prints its header, its summary when it has one (whitespace
collapsed, indented four), then one line per member: the member id padded to the
widest id in the whole answer, two spaces, and the member's path relative to the
codex root. A blank line separates clusters.

```
$ lore index search storage
  storage — Storage and schemas
    How Lore stores entities on disk and validates their shape.
    ref-lore_db-core    technical/database/ref/core.md
    tech-arch-schemas   technical/architecture/schemas.md

  (unauthored) — hub: tech-oracle-internals
    tech-oracle-internals  technical/oracle/internals.md
```

No match prints one line and exits 0
(`decisions-042-index-search-prints-a-no-match-sentence`):

```
No clusters matching "<keyword>".
```

Under `--json` the envelope is `{"clusters": [...]}`, each cluster carrying
`slug`, `name`, `summary`, `hub`, `members` and `member_paths`; an unauthored
cluster carries `null` for the first three. No match is `{"clusters": []}`.

## Authoring the entries

`lore index build` reports which clusters need attention; it never writes them.
The `update-index` skill is the writer — it reads each `unauthored` cluster's
members, writes a `slug`, `name`, `summary` and `authored_against` digest keyed
by the cluster's hub, rewrites the summary and digest of each `drifted` cluster,
and re-keys or retires each stale entry. See `conceptual-entities-skill`.

`lore health --scope index` audits the same classification without writing
anything — see `conceptual-workflows-health`.

## Error Paths

| Condition | Result |
|---|---|
| `lore index search` with no `.lore/index/authored.yaml` | Exit **1**, stderr: `no index authored for this project. Run the update-index skill to author it.` Under `--json`, the ordinary error envelope carries the same message. |
| `.lore/index/authored.yaml` is unparseable or fails its schema | Exit **1**, stderr: the file's path relative to the project root, then the failure. Both subcommands. |
| The render path is a link, escapes the project root, or cannot be written | Exit **1**, stderr: the atomic write gate's own refusal, unchanged. |
| `--project` on either subcommand | Exit **2**, stderr: `Error: --project is a read selector; it is not accepted on "index build"` / `"index search"`. From the root group the label is the same. |
| `lore index search` with no KEYWORD | Exit **2**, Click's own usage error on stderr. |
| `lore index` with no subcommand | Exit **2**, the group's help on stderr. |
| An unknown subcommand | Exit **2**, Click's own usage error. |

Exit **0** covers both success paths, including a table whose every row is
`unauthored` and a search that matched nothing.

## Python API

```python
from lore.api import build_index, search_index

report = build_index(project_root=Path("."))
clusters = search_index(project_root=Path("."), keyword="storage")
```

Both return the shapes the `--json` envelopes carry. `build_index` raises
`CodexIndexError` when the authored file exists and cannot be used, and treats a
missing one as every cluster `unauthored`. `search_index` raises
`CodexIndexNotAuthoredError` when no authored file exists, and `CodexIndexError`
on the same failures `build_index` names. See `ref-lore_api-core`.

## Out of Scope

- Naming or summarising a cluster. Lore partitions and reports; the summaries
  are authored.
- Resolving a cluster by slug. No command accepts one.
- Indexing code. The index covers codex documents.
