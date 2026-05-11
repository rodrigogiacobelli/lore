---
name: update-codex
description: Create or update canonical codex docs for a direct chat request — enforces discovery, dedup, classification, and frontmatter rules so ad-hoc edits match the rigor of the tech-writer doctrine flow.
---

# Update Codex

Use this skill when the user asks, in chat, to add or change a fact in the codex outside the feature-implementation pipeline. Direct asks ("document X", "add Y to the codex", "update the doc on Z") routinely misfire because agents skip discovery, skip dedup, pick the wrong layer, or improvise frontmatter. This skill makes the right steps mandatory.

If the request is "document an entire feature's worth of changes", stop and suggest `/start-quest` with the feature-implementation doctrine instead — that flow has a Tech Writer agent built for it.

## CODEX.md is your primary input — and your responsibility

`.lore/codex/CODEX.md` is the project-wide guide to the entire documentation: the layers, the conventions, the rules every codex doc must follow. **Always read it first** — it is the source of truth for how the codex is organised in *this* project, and it may carry project-specific guidance not present anywhere else.

You also **own keeping it current**. When a change introduces a new convention, a new layer or subdirectory, a new doc category, or a new project-wide rule that future doc edits must follow, update `CODEX.md` so the next reader (human or agent) finds the rule from the top. **CODEX.md is lean by design** — do not bloat it with per-doc summaries, per-feature notes, or content that belongs in the docs themselves. Only structural or rule-level changes warrant an edit. The same dedup and discovery rules below apply to CODEX.md itself.

## Steps

### 1. Clarify the change

Before touching anything, restate the change in one sentence and confirm:

- Is this **one fact** changing, **several**, or a **new doc** being created?
- Is the user describing a *fact* (something newly true about the system) or a *thought* (an opinion, intent, or speculation)? The codex stores facts about the system as it exists today. Speculation belongs in `transient/` or out of the codex entirely.

If the request is vague ("document X"), ask what specific fact about X is being added or corrected.

### 2. Discover existing homes

Always run before writing. The dedup rule is "one fact, one file" — finding the right home prevents duplicate or contradictory docs.

```
lore codex search <keyword>
```

Run multiple searches if the topic has angles (entity name, workflow name, command name, table name). For relationships, search by both endpoints. For glossary candidates, also run `lore glossary search <term>`.

Optionally scan the taxonomy:

```
lore codex list
```

Read every candidate that looks adjacent:

```
lore codex show <id1> <id2> <id3>
```

### 3. Classify

Pick the right layer using the codex taxonomy. Read `lore codex show codex` if unsure of the rules.

| Question | Layer |
|----------|-------|
| What is this thing? | `conceptual/entities/` |
| How do two things connect? | `conceptual/relationships/` |
| What does the system do internally / what does a user do? | `conceptual/workflows/` |
| How is it built / stored / served? | `technical/` |
| Intent around a DB table, endpoint, event, job? | `technical/<domain>/ref/` (reference doc) |
| Why was this choice made? | `decisions/` (ADR) |
| How do we comply with a rule? | `standards/` |
| Hard limits we must never violate? | `constraints/` |
| Trust model? | `security/` |
| Dev / deploy / run? | `operations/` |

For `ref-*` docs, default to one cluster doc per logical group (not per entity) and ensure the `**Covers:**` line names every covered entity verbatim.

### 4. Decide create vs update vs link

- If a doc already covers this fact, **stop** — there is nothing to do.
- If a doc already covers a closely related fact and the new fact extends it, **update** that doc.
- If the new fact is a different scope, **create** a new doc and add a `related` link from the closest existing doc.
- If the fact already lives in another doc, **link via `related`** instead of repeating it.

Never copy-paste a fact across docs.

### 5. Glossary gate

If any candidate change adds or modifies an entry in `.lore/codex/glossary.yaml`, run the gate first:

```
lore artifact show glossary-design
```

Most term-like additions belong in entity, workflow, or ADR docs — not in the glossary. Skip the glossary unless the design checklist passes.

### 6. Find a template (for new docs)

```
lore artifact list
```

Use the relevant template (e.g. an ADR template for `decisions/`, an entity template for `conceptual/entities/`) so frontmatter and body conventions are correct from the start.

### 7. Apply

Frontmatter is exactly:

```yaml
---
id: <unique-id>
title: <human title>
summary: <1-3 sentences for scanning>
related:        # optional; omit or use [] if none
  - <other-id>
---
```

No other fields. `lore health` rejects extras.

Body rules:

- No "Related Documentation" sections — cross-references live exclusively in `related`.
- No duplicated facts — link instead.
- For workflow docs, lead with subject (system or user) and stay consistent.
- For `ref-*` docs, the `**Covers:**` line lists every covered entity verbatim, followed by a `**Source of truth:**` pointer at the schema location in code.
- For ADRs, include the rejected alternatives — they tell future agents what not to suggest.

### 8. Verify

Run:

```
lore health --scope codex
```

Must report `Health check passed.` Fix any error before declaring done.

Re-run the original `lore codex search <keyword>` and confirm the new or updated doc appears. If it does not, the discoverability words are wrong — fix the summary or body until search finds it.

### 9. Report

Tell the user:

- Codex IDs created and a one-line description of each.
- Codex IDs updated and the section/fact changed.
- Any docs deliberately not changed and why (dedup, out of scope).
- Health check status.

Do not summarize what the docs *say* — the user can read them. Summarize what *changed*.
