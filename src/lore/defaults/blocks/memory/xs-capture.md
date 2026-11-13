---
id: xs-capture
feature: memory
---
## Capture

1. **Fetch the content** the way the user specified. Store the body verbatim. Do not summarise. Reformat only when the
   upstream format is structurally unreadable, Atlassian ADF into markdown for example.

2. **Read it and propose canonical updates.** Identify every term, concept, constraint or decision in the snapshot that
   project memory does not yet carry. For each, name the specific canonical document to change and the one-sentence
   addition you propose. Present the list and get approval before applying anything.

   When the item creates intent around a concrete technical artifact (a table, an endpoint, a model, an event, a job),
   the canonical home is a reference document under `technical/<domain>/ref/`, cluster-grained, whose body explains
   *why* and points at the source of truth. Never propose a schema dump. When no reference document exists for the
   cluster yet, propose creating one rather than appending intent to an unrelated entity document.

3. **Apply the approved edits** per `references/codex-doc.md`, and track which canonical ids you actually changed. Those
   ids are the snapshot's `related` list.

   A canonical document may mention the source id in prose. It must never carry the source id in `related`; that is a
   `canonical_links_to_source` error.

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

   `related` must be non-empty, and every id in it names a canonical document this source changed. An empty `related`,
   a missing `related`, or any fifth field is rejected.

   If step 2 found nothing canonical to change, stop and ask the user: either name one canonical document whose graph
   this source belongs in, or abandon the ingestion. A source that touches no canonical knowledge does not belong in
   project memory.
