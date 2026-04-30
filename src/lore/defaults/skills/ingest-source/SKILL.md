---
name: ingest-source
description: Capture a raw upstream source (Jira ticket, transcript, pasted doc) into the codex sources layer and propagate new knowledge into canonical docs.
---

# Ingest Source

Capture a single upstream item as a verbatim snapshot under `.lore/codex/sources/<system>/<id>.md`, then propose any resulting canonical-doc updates. Use this for first-time capture. To update a source that already exists on disk, use `/refresh-source` instead.

## Steps

### 1. Ask three questions

- "What system is this source from?" (e.g. `jira`, `slack`, `meetings`)
- "What is the source ID?" (e.g. `KONE-23335`)
- "How should I fetch it?" (pasted text, local file, URL via a tool the user has available)

### 2. Resolve the target path

Target: `.lore/codex/sources/<system>/<id>.md`

### 3. Refuse to run if the snapshot already exists

```
test -e .lore/codex/sources/<system>/<id>.md && echo "exists"
```

If the file exists: stop. Tell the user "A snapshot already exists at <path>. Run `/refresh-source` instead." Do not proceed.

### 4. Fetch the content

Use whatever method the user specified. Store the raw body verbatim. Do not summarise, do not reformat unless the upstream format is structurally unreadable (e.g. Atlassian ADF → markdown).

### 5. Read the content and propose canonical updates

Identify new terms, concepts, constraints, or decisions in the snapshot that are not yet in the canonical codex. For each, name a specific canonical doc path that should be updated and the one-sentence addition you propose. Present the list to the user for approval.

If any candidate update is a glossary entry — adding a term to `.lore/codex/glossary.yaml` — gate it through the design checklist before proposing:

```
lore artifact show glossary-design
```

The Glossary is for small, project-specific terms only. Entities, named workflows, generic IT vocabulary, and future-scope ideas belong in entity docs, workflow docs, ADRs, standards docs, or nowhere — not the glossary.

### 6. Apply approved edits

For each approved edit, modify the relevant canonical doc. Canonical docs may mention the source ID in prose; they must NEVER list the source ID in `related` — `lore health` will reject that as `canonical_links_to_source`.

Track the canonical codex IDs that were actually edited. You will list these in the snapshot's `related` field.

### 7. Write the snapshot (with the required outbound `related`)

Write `.lore/codex/sources/<system>/<id>.md` with this exact structure:

```markdown
---
id: <id>
title: "<upstream title>"
summary: <one-sentence summary>
related:
  - <canonical-id-edited-in-step-6>
  - <another-canonical-id-edited-in-step-6>
---

> **Source:** <system>://<id>
> **Fetched:** <YYYY-MM-DD>
> **Disclaimer:** Point-in-time snapshot. Upstream may have changed. Re-run `/refresh-source` to update.

<verbatim upstream body>
```

Frontmatter fields are exactly four: `id`, `title`, `summary`, `related`. `related` MUST be non-empty — every ID in it names a canonical doc this source caused to change. `lore health` rejects empty `related`, missing `related`, or any extra field.

If step 6 identified zero canonical docs to edit, pause and ask the user: either (a) identify at least one canonical doc whose `related` graph this source belongs in (e.g. a broad entity doc the snapshot informs), or (b) abort the ingestion — a source that touches no canonical doc does not belong in the codex.

### 8. Verify via `lore health`

Run:

```
lore health --scope codex --scope schemas
```

Expected output: `Health check passed. No issues found.` If schema errors reference the new snapshot, check `related` is present and non-empty and contains only existing codex IDs. If `canonical_links_to_source` fires on a canonical doc, that canonical doc's `related` was polluted with the source ID — remove it.

### 9. Report

Tell the user: snapshot path, list of canonical docs edited, confirmation that `related` points at those same docs.
