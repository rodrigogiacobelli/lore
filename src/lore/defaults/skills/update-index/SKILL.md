---
name: update-index
description: Author and refresh the codex index — write the slug, name and summary for each cluster of documents Lore has partitioned, so `lore index search` can route a cold read to the right group
---

# Update Index

Lore partitions the codex `related` graph into **clusters** of densely linked
documents and names each cluster's **hub** — the member most linked to the rest
of its own cluster. It does not name the clusters. That is this skill's job.

`.lore/index/authored.yaml` is the only file in the codex index a rebuild cannot
recover, and **no Lore command writes it**. You do. Everything else —
`.lore/index/codex.json`, the partition, the digests — is regenerated on demand
and is safe to delete.

Run this skill when `lore index build` reports a cluster that is `unauthored` or
`drifted`, when it reports a stale entry, or after a batch of codex work has
moved the graph.

## The file

```yaml
version: 1
entries:
  conceptual-workflows-lore-init:          # the cluster's HUB — this is the key
    slug: init
    name: Initialising a project
    summary: >-
      What `lore init` writes, how it reconciles an existing project, and the
      answers it records.
    authored_against: "b41f...64 hex characters..."
```

| Field | Rule |
|---|---|
| the key | the cluster's hub, exactly as `lore index build` reports it |
| `slug` | lowercase, digits and hyphens, 1–60 chars — the display key of a row |
| `name` | 1–80 chars, one line — what a reader sees in a search result |
| `summary` | 1–1000 chars — what this group of documents covers, written for someone deciding whether to read them |
| `authored_against` | the cluster's current digest, 64 lowercase hex characters |

**Quote `authored_against`.** A digest that happens to be all digits parses as an
integer in unquoted YAML and fails the schema.

No command resolves a cluster by its `slug`, and `lore index search` does not
match against it — but it is not inert: **authored results are sorted by slug**,
so it is your only lever over what a reader sees first. Name the cluster you
would want at the top of a crowded answer accordingly. Keep slugs distinct:
two rows with the same slug make the output ambiguous and order arbitrarily, and
`lore health --scope index` warns about it.

## Steps

### 1. See what needs writing

```
lore index build
```

Every row is `ok`, `unauthored` or `drifted`, and any authored entry the
partition has left behind prints below the table as a stale entry. The command
writes the render and never writes `authored.yaml`, so it is safe to run at any
time.

### 2. Write each `unauthored` cluster

For each `unauthored` row, read its members and write an entry keyed by its hub.

An unauthored row shows `hub: <id>` where its name would go — that hub is the
key you write the entry under. Its members come from the JSON envelope or the
render (step 5), and you read them in one call:

<!-- lore:access cli -->
```
lore codex show <id1> <id2> ...   # batch the members into one call
```
<!-- lore:access end -->
<!-- lore:access native -->
Each cluster in `.lore/index/codex.json` carries `member_paths` — paths relative
to `.lore/codex/` — so read those files directly with your own file tool.
<!-- lore:access end -->

Read titles and summaries first — both are frontmatter, in the first few lines
of each file, so you can characterise a whole cluster without opening a single
body. Open a body only when the titles do not tell you what the group is about.
Then write, in your own words:

- **`name`** — what a reader would call this group. Not the hub's title repeated:
  the hub is one document, the cluster is several.
- **`summary`** — what the group covers and what question it answers. Write it
  for someone who has read nothing, deciding whether this is the right place to
  start. Name the concrete subjects, so a keyword search lands here.

A cluster that resists description usually means the partition grouped
documents that share links but not a subject. Say so in the summary rather than
inventing a theme — a reader is better served by "the CLI's error paths and the
two config keys that affect them" than by a label that fits nothing.

### 3. Refresh each `drifted` cluster

A `drifted` row means the members have changed since the summary was written.
Re-read them, rewrite `name` and `summary` if the group's subject moved, and
replace `authored_against` with the current digest either way.

### 4. Resolve each stale entry

A stale entry names a hub that heads no cluster. The line says which case it is:

| Line | What it means | What to do |
|---|---|---|
| `hub <id> heads no cluster` | the document still exists; the partition moved and something else now heads its cluster | find the cluster that holds those documents now and re-key the entry to its hub, rewriting the summary if the membership changed |
| `hub <id> is not a document in this codex` | the hub document was deleted or renamed | re-key the entry to the cluster its documents landed in, or delete the entry if the group is gone |

Never re-key an entry without reading the new cluster's members. An entry moved
blind attaches a summary to documents nobody checked, which is the failure the
`drifted` status exists to catch.

### 5. Get the digest

Each entry's `authored_against` is the digest of the cluster it describes.

<!-- lore:access cli -->
```
lore --json index build
```

The envelope carries one object per cluster. Match on `hub` and take the
`digest`. (`lore index build`'s human table shows the status, not the digest.)
<!-- lore:access end -->
<!-- lore:access native -->
Read `.lore/index/codex.json` with your own file tool. Each cluster object
carries `hub`, `members`, `member_paths` and `digest` — match on `hub` and take
the `digest`.
<!-- lore:access end -->

Write the entry, then re-run `lore index build`: a cluster whose entry carries
the right digest comes back `ok`. A row that stays `drifted` means the digest
was copied from the wrong cluster, or the codex changed between the two runs.

### 6. Write the file

`.lore/index/authored.yaml` is a plain project file at a path you know, not a
Lore entity with an id, so you write it directly with your own file tool in
every access mode. Preserve the entries you are not changing — the file is one
mapping and an overwrite drops every group somebody else wrote up.

Create the file whole the first time, with `version: 1` and an `entries`
mapping. `lore index build` creates `.lore/index/` on its first run, so the
directory is already there.

### 7. Verify

```
lore index build
lore health --scope index
```

Every cluster reports `ok`, and `lore health --scope index` reports nothing.
`schema` and `unresolvable_hub` are errors and must be cleared; the rest are
warnings that name work still to do.

Then confirm the index answers:

```
lore index search <a keyword from a summary you wrote>
```

**The match is a plain substring of the whole query**, casefolded, against the
member ids, the name and the summary. It does not split the query into words, so
`soft delete` does not find a summary that says "soft-delete", `json output`
does not find one that says "`--json` output" — the backtick is inside the
string — and a natural-language question matches nothing at all.

So the rule is stronger than "use concrete words": **spell out, at least once
and unhyphenated, the phrase a reader would actually type.** Write both forms
where they differ. Run the queries a cold agent would really send — `soft
delete`, `nested project`, `getting started` — and when one misses, fix the
summary rather than the query. The reader does not get to see your wording
before choosing theirs.

Check your summary lengths before this step. The cap is 1000 characters and it
is a schema rule, so **one over-length summary makes every `lore index search`
return a schema error** — not just the row that broke it.

### 8. Report

Tell the user which clusters were authored, which were refreshed, which stale
entries were re-keyed or retired, and any cluster you could not describe with
confidence — naming the members, so they can decide.
