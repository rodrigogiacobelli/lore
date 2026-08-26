# Reference — capturing an upstream artifact as a source snapshot

Read this only when the knowledge passed the ingestion boundary in step 2 of the
skill: authored outside the project, authored outside the conversation, and
identifiable well enough to be re-fetched and compared later.

A snapshot is a verbatim copy of one upstream item, stored at
`.lore/codex/sources/<system>/<id>.md`, whose `related` field names every
canonical document the item caused to change. The snapshot is the raw record;
the canonical documents are the distilled knowledge. Both land, every time.

## Ask three questions

- **What system is this from?** `jira`, `slack`, `meetings`, `vendor-docs`.
- **What is the id?** `KONE-23335`, `2026-08-24-arch-review`.
- **How should I fetch it?** Pasted text, a local file, or a URL through a tool
  you have.

The answers set the path and make the later refresh possible. If the user cannot
answer the first two, the item failed the boundary — distil it into a codex
document instead and write no snapshot.

## First capture, or a refresh?

Check whether `.lore/codex/sources/<system>/<id>.md` already exists.

- **Absent** → first capture. Follow *Capture* below.
- **Present** → refresh. Follow *Refresh* below. Never write a second file and
  never write a history file; the previous content lives in git history.

## Capture

1. **Fetch the content** the way the user specified. Store the body verbatim.
   Do not summarise. Reformat only when the upstream format is structurally
   unreadable — Atlassian ADF into markdown, for example.

2. **Read it and propose canonical updates.** Identify every term, concept,
   constraint or decision in the snapshot that project memory does not yet
   carry. For each, name the specific canonical document to change and the
   one-sentence addition you propose. Present the list and get approval before
   applying anything.

   When the item creates intent around a concrete technical artifact — a table,
   an endpoint, a model, an event, a job — the canonical home is a reference
   document under `technical/<domain>/ref/`, cluster-grained, whose body
   explains *why* and points at the source of truth. Never propose a schema
   dump. When no reference document exists for the cluster yet, propose creating
   one rather than appending intent to an unrelated entity document.

3. **Apply the approved edits** per `references/codex-doc.md`, and track which
   canonical ids you actually changed. Those ids are the snapshot's `related`
   list.

   A canonical document may mention the source id in prose. It must never carry
   the source id in `related` — `lore health` rejects that as
   `canonical_links_to_source`.

4. **Write the snapshot.** Frontmatter is exactly four fields:

   ```markdown
   ---
   id: <id>
   title: "<upstream title>"
   summary: <one-sentence summary>
   related:
     - <canonical-id-you-edited>
     - <another-canonical-id-you-edited>
   ---

   > **Source:** <system>://<id>
   > **Fetched:** <YYYY-MM-DD>
   > **Disclaimer:** Point-in-time snapshot. Upstream may have changed.

   <verbatim upstream body>
   ```

   `related` must be non-empty, and every id in it names a canonical document
   this source changed. `lore health` rejects an empty `related`, a missing
   `related`, or any fifth field.

   If step 2 found nothing canonical to change, stop and ask the user: either
   name one canonical document whose graph this source belongs in, or abandon
   the ingestion. A source that touches no canonical knowledge does not belong
   in project memory.

<!-- lore:access cli -->
   Draft the snapshot to a temp file, then:

   ```
   lore codex new <id> --type codex-source --group sources/<system> -f <draft>.md
   ```

   `--type codex-source` selects the stricter four-field schema.
   `--group sources/<system>` creates the directory when it does not exist.
<!-- lore:access end -->
<!-- lore:access native -->
   Write the file yourself at `.lore/codex/sources/<system>/<id>.md`, creating
   the directory when it does not exist.

   The snapshot validates against a stricter schema than a canonical document —
   exactly `id`, `title`, `summary`, `related`, and `related` non-empty — and
   nothing selects it for you when you write the file directly. Run
   `lore health --scope codex schemas` to confirm you hit it.
<!-- lore:access end -->

## Refresh

1. **Read the stored body.** Strip the frontmatter block and the provenance
   header; keep the verbatim body.
2. **Fetch the fresh version** the way the user specified. Keep it verbatim.
3. **Diff and present.** Compare stored against fresh and summarise in prose:
   sections added, sections removed, fields and values changed. Paste the raw
   diff only if asked.
4. **Ask what is codex-worthy.** The user may say "none" — then skip to step 6.
5. **Propose and apply canonical updates** for each codex-worthy change, per
   `references/codex-doc.md`. A diff-driven edit is the easiest place to leak a
   delta into a canonical document: write what is true after the change, never
   what changed.
6. **Overwrite the snapshot**, rewriting `related` from scratch. Do not merge
   with the prior list. It holds exactly the canonical documents you edited in
   step 5, plus any from an earlier run that are still accurate for the
   refreshed content. Drop the rest.

   If the user vetoed every proposed edit, re-check each existing `related`
   entry against the fresh content and carry forward only what still applies.
   An empty `related` is a health error; when a refresh leaves nothing valid,
   ask whether to abandon the refresh or name a catch-all canonical document.

## Verify

```
lore health --scope codex schemas voice
```

`voice` skips the `sources/` layer entirely — a snapshot is verbatim upstream
text and is exempt. Any voice warning is on a canonical document you edited, not
on the snapshot. A schema error naming the snapshot almost always means
`related` is missing, empty, or names an id that does not exist.

## Report

Snapshot path, the canonical documents edited — or "none", after a vetoed
refresh — and confirmation that `related` names those same documents.
