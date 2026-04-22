---
name: refresh-source
description: Pull a fresh version of an existing source, diff it against the stored snapshot, propagate changes into canonical docs, and overwrite the snapshot.
---

# Refresh Source

Re-ingest a source that was captured previously. Produces a diff summary, walks canonical-doc updates driven by the diff, and overwrites the snapshot on disk. Use this when the upstream item has changed since it was first captured. For first-time capture, use `/ingest-source`.

## Steps

### 1. Ask two questions

- "Which source? `<system>` and `<id>`?"
- "How should I fetch the fresh version?"

### 2. Resolve the target path

Target: `.lore/codex/sources/<system>/<id>.md`

### 3. Refuse to run if the snapshot does not exist

```
test -e .lore/codex/sources/<system>/<id>.md && echo "ok"
```

If the file does not exist: stop. Tell the user "No snapshot at <path>. Run `/ingest-source` first." Do not proceed.

### 4. Read the stored body

Load `.lore/codex/sources/<system>/<id>.md`, strip the frontmatter block and the provenance header, and retain the verbatim body section.

### 5. Fetch the fresh content

Use the method the user specified. Retain verbatim.

### 6. Compute and present the diff

Compare stored body vs fresh body. Present a human-readable summary: added sections, removed sections, changed fields, changed values. Do not paste the raw diff unless the user asks.

### 7. Ask what is codex-worthy

Ask the user which parts of the diff should drive canonical-doc updates. The user may say "none" — if so, skip to step 9.

### 8. Propose and apply canonical updates

For each codex-worthy change, name the specific canonical doc to update and the proposed edit. Apply after approval.

### 9. Overwrite the snapshot (rewriting `related` from scratch)

Write `.lore/codex/sources/<system>/<id>.md` with the fresh content, using the same structure as `/ingest-source` step 7 — frontmatter has `id`, `title`, `summary`, and `related`. Update `title` and `summary` if the upstream headline changed.

Rewrite `related` from scratch on every refresh — do NOT merge with the prior list. Include exactly the canonical docs edited in step 8, plus any canonical docs from the prior run that are still accurate for the refreshed content. Drop canonical docs that are no longer relevant.

If the user vetoed all proposed edits in step 7, the prior `related` list may still be valid — re-check each entry against the fresh content and carry forward only what still applies. Empty `related` is a `lore health` error; if the refresh leaves nothing valid, ask the user whether to abort the refresh or pick a catch-all canonical doc.

**Do not duplicate files. Do not create a history file.** The previous content is retained only in git history.

### 10. Verify via `lore health`

```
lore health --scope codex --scope schemas
```

Expected output: `Health check passed. No issues found.`

### 11. Report

Tell the user: snapshot refreshed, list of canonical docs edited (or "none" if the user vetoed all proposed edits).
