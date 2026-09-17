---
id: tech-arch-codex-index
title: Codex Index Internals
summary: 'Technical reference for src/lore/index.py and the two files under .lore/index/.
  Covers document selection, the undirected related adjacency, the two hashes (a
  per-cluster content digest and a stat-level codex fingerprint), the render payload
  and its version, the refresh path, the classification both lore index build and
  lore health --scope index read, keyword matching, and the CodexIndexError /
  CodexIndexNotAuthoredError pair with its issues attribute.

  '
binds:
- src/lore/index.py
- src/lore/paths.py
- src/lore/schemas/index-authored.yaml
- tests/unit/test_index_authored.py
- tests/unit/test_index_digest.py
- tests/unit/test_index_partition.py
- tests/unit/test_index_refresh.py
- tests/unit/test_schemas_index_authored.py
- tests/unit/test_health_index.py
related:
- tech-arch-graph
- tech-arch-schemas
- tech-arch-source-layout
- tech-arch-initialized-project-structure
- tech-arch-api-facade
- conceptual-workflows-index
- conceptual-workflows-health
- decisions-036-index-partitions-the-local-canonical-codex
- decisions-037-index-is-a-top-level-lore-directory
- decisions-038-partition-is-deterministic-modularity-local-moving
- decisions-039-authored-entry-is-keyed-by-its-hub
- decisions-040-no-lore-exception-shadows-a-builtin
- decisions-041-render-is-a-cache-invalidated-by-a-stat-fingerprint
- standards-dependency-inversion
---

# Codex Index Internals

**Source module:** `src/lore/index.py`

The module partitions the codex `related` graph into clusters, names each
cluster's hub, and answers a keyword with the clusters it lives in. Nothing in
it prints, and every rule a Python caller would otherwise have to reimplement
lives here rather than in the command that wraps it.

`conceptual-workflows-index` describes the behaviour from the outside. This
document describes how it is built.

## On-disk layout

Both files live under `.lore/index/` and are reached through `paths`
(`decisions-037-index-is-a-top-level-lore-directory`):

| `paths` helper | Path | Lifecycle |
|---|---|---|
| `index_dir(root)` | `.lore/index/` | created by the first render write |
| `index_authored_path(root)` | `.lore/index/authored.yaml` | committed; written by the `update-index` skill or a person, never by Lore |
| `index_rendered_path(root)` | `.lore/index/codex.json` | git-ignored; generated, disposable |

`lore init` seeds neither file.

## What gets indexed

`_indexed_documents(project_root)` returns this project's own canonical codex
records by ascending id: `codex._list_codex_local(project_root)`, filtered
through `projects._is_unexportable_codex_layer` to drop `transient/` and
`sources/` (`decisions-036-index-partitions-the-local-canonical-codex`).

`_adjacency(documents)` builds the undirected `related` graph.
`codex._build_adjacency` is the one reader that turns `related` into edges and
is not copied here; the outbound and inbound maps are unioned, because the
stable side owns the link and which end of a pair stores it says nothing about
the pair. A document's own id is discarded from its neighbour set — a document
listing itself in `related` reaches both maps, and `partition_graph`'s stated
precondition is that a node never neighbours itself.

## The two hashes

They answer different questions and are deliberately not one hash.

**`_cluster_digest(members, paths)`** — `sha256` over
`f"{member}\t{sha256(file bytes)}\n"` for each member, sorted by member id. It
covers what the members are and what they say, and nothing else. Scoped to the
cluster, so a document changing elsewhere in the codex cannot mark it drifted —
the precision a drift warning needs to be worth reading. A member whose file
moves without changing refreshes the render and leaves the digest alone, which
is correct: the summary describes what the documents say, not where they sit.

**`_codex_fingerprint(project_root)`** — `sha256` over
`f"{relpath}\t{size}\t{mtime_ns}\n"` for every indexed file, sorted by relpath.
One `stat` per document and no file read, so a search never has to decide
whether to rebuild first
(`decisions-041-render-is-a-cache-invalidated-by-a-stat-fingerprint`). It walks
`*.md` under the codex root directly rather than reading frontmatter, applying
the same `transient/` and `sources/` exclusion.

## The render

`_render_payload` returns the whole render. The fingerprint is taken **before**
the partition, so a document edited while a build runs leaves a fingerprint the
next search disagrees with rather than one it trusts.

```json
{
  "version": 1,
  "codex_fingerprint": "<sha256>",
  "clusters": [
    {
      "hub": "<codex id>",
      "members": ["<codex id>", "..."],
      "member_paths": ["<path relative to the codex root>", "..."],
      "digest": "<sha256>"
    }
  ]
}
```

`_RENDER_VERSION` is `1`. The payload carries no slug, name, summary or status,
so two projects with identical codexes and different authoring render
identically.

`_write_render` serialises with `json.dumps(..., indent=2, sort_keys=False,
ensure_ascii=False)` plus a trailing newline and writes through
`safewrite.atomic_write_text`, so a concurrent reader sees the old file or the
new one and never half of either.

`_load_render` returns `None` for every unusable state — absent, unreadable,
unparseable, not a mapping, of another `version`, or missing a string
`codex_fingerprint` or a list `clusters`. A cache that can fail a command is not
a cache. `_current_render` adds the fingerprint comparison.

Two entry points sit on top:

- `_refresh(project_root)` — the stored render if it still describes the codex,
  otherwise rebuild and write. Two processes refreshing at once write the same
  bytes through an atomic write, so a reader sees one whole file either way.
- `_current_clusters(project_root)` — the read-only half, for the health audit:
  same fast path, no write, so an audit leaves behind no cache nobody asked for.

## The authored half

`_load_authored(project_root)` returns the entries keyed by hub. It raises
`CodexIndexNotAuthoredError` when the file does not exist, and `CodexIndexError`
when it exists and cannot be used. Validation runs through
`schemas.validate_entity_file(path, "index-authored")` before the YAML is read
for content.

A mapping keyed by hub makes "one entry per cluster" structural rather than a
convention, and makes a duplicate hub unrepresentable rather than a check.

The packaged schema `lore://schemas/index-authored` requires `version: 1` and an
`entries` object whose property names match `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` and
whose values carry exactly `slug`, `name`, `summary` and `authored_against`. The
`authored_against` value is matched against `^[0-9a-f]{64}$` — an all-digit
digest written unquoted in YAML parses as an integer and fails the schema. See
`tech-arch-schemas`.

## Classification

`_classify(clusters, entries)` is the single classification both `lore index
build` and `lore health --scope index` read, so the table and the audit cannot
drift apart. It returns `clusters` (one row each), `unauthored`, `drifted` and
`stale`.

`_cluster_status` compares an entry's `authored_against` against the cluster's
current digest: no entry is `unauthored`, an equal digest is `ok`, anything else
is `drifted`.

`_cluster_rows` sorts by `_STATUS_RANK` (`ok` 0, `unauthored` 1, `drifted` 2),
then descending member count, then ascending hub — what is fine, what is
missing, what moved.

`_stale_rows` reports every entry whose hub heads no cluster, by ascending slug,
with one of two reasons: `hub_not_a_hub` when the hub is still an indexed
document, `hub_not_found` when it is not. The two carry different severities
downstream because a hub that is still a document in this codex is a codex edit
needing a re-read, while one that is not is a deleted document needing a
decision (`decisions-039-authored-entry-is-keyed-by-its-hub`).

## Matching

`_matches(needle, cluster, entry)` tests a casefolded substring against the
cluster's member ids always, and against an authored cluster's `name` and
`summary` as well. The slug is deliberately absent: it is the display key of a
row, and no command resolves a cluster by it, so matching on it would return a
cluster for a word that appears nowhere a reader can see.

## Public surface

Four names reach `lore.api.__all__`:

| Name | Shape |
|---|---|
| `build_index(project_root: Path) -> dict` | the classification; writes the render unconditionally |
| `search_index(project_root: Path, keyword: str) -> list[dict]` | the matching clusters, authored first by ascending slug then unauthored by ascending hub |
| `CodexIndexError(ValueError)` | the authored file is present and cannot be used |
| `CodexIndexNotAuthoredError(CodexIndexError)` | no authored file exists |

`CodexIndexError` carries an `issues` attribute — a `list[SchemaIssue]`,
mirroring `SchemaValidationError` — so `lore health` reports one row per schema
failure with its rule and pointer rather than validating the file a second time.
A parser failure carries the one issue that describes it, under the `yaml-parse`
rule at pointer `/`.

`partition_graph` and `cluster_hub` live in `graph.py` and stay internal — see
`tech-arch-graph`. `_check_index` is `health.py`'s and is likewise internal.

Naming follows `decisions-040-no-lore-exception-shadows-a-builtin`: no name in
`lore.api.__all__` equals a Python builtin.

## Imports

`index.py` imports `codex`, `graph`, `paths`, `projects`, `safewrite` and
`schemas`. It imports neither `cli.py`, `db.py` nor `api.py` — see
`standards-dependency-inversion`.
