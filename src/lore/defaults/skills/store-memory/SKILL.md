---
name: store-memory
description: Record knowledge into project memory — a codex document, a rite, or a source snapshot — creating, editing or deleting as the request requires
---

# Store Memory

One entry point for writing to project memory. Use it whenever the user asks you
to record, correct, or retire something the project should remember — "document
this", "the codex is wrong about X", "capture this ticket", "write down how we
do Y", "drop that doc".

Project memory has three shapes and this skill covers all three:

| Shape | Holds | Lives in |
|---|---|---|
| **Codex document** | Semantic knowledge — what is true about the system today | `.lore/codex/` |
| **Rite** | Procedural knowledge — how to do or diagnose a recurring task | `.lore/rites/` |
| **Source snapshot** | A verbatim copy of an upstream artifact, plus the canonical docs it changed | `.lore/codex/sources/` |

If the request is "document an entire feature's worth of changes", stop and
suggest `/start-quest` with the feature-implementation doctrine instead — that
flow has a Tech Writer step built for it.

## Step 1 — Name what you are recording

Restate the change in one sentence, then classify it. The three questions below
settle every case:

1. **Is this a fact or a procedure?** A fact about the system as it exists today
   is a codex document. A step-by-step "how do I do or diagnose X" is a rite.
2. **Is it a fact at all?** The codex stores what is true, not what someone
   hopes or suspects. Speculation belongs in `codex/transient/` or nowhere.
3. **Where did it come from?** See the ingestion boundary below.

If the request is vague — "document X" — ask which specific fact about X is
being added or corrected before you touch anything.

## Step 2 — Apply the ingestion boundary

Write a source snapshot **only when the knowledge arrives as an artifact
authored outside the project and outside the conversation, and identifiable well
enough to be re-fetched and compared later.**

All three conditions hold, or there is no snapshot:

- **Authored outside the project** — a Jira ticket, a meeting transcript, a
  vendor's API doc. A note you or the user just wrote is not an upstream
  artifact.
- **Authored outside the conversation** — the user pasting their own reasoning
  is conversation, however long the paste. The artifact existed before the
  conversation reached for it.
- **Re-fetchable and comparable** — you can name the system and the id
  (`jira`/`KONE-23335`, `meetings`/`2026-08-24-arch-review`) well enough that a
  later refresh finds the same item and diffs it.

Fail any one of them and the knowledge still lands — as a codex document or a
rite, distilled in your own words. The snapshot is what makes a *refresh*
possible later; without re-fetchability it buys nothing and costs a file that
can never be checked against its origin.

## Step 3 — Read `codex.md` first

`.lore/codex/codex.md` is the project-wide guide to the whole documentation set:
the layers, the conventions, the rules every codex document follows. It may
carry project-specific guidance that exists nowhere else. Read it before you
draft.

You also own keeping it current. When a change introduces a new convention, a
new layer, a new document category, or a new project-wide rule, update
`codex.md` so the next reader finds the rule from the top. It is lean by
design — only structural or rule-level changes warrant an edit, never per-doc
summaries or per-feature notes.

<!-- lore:access cli -->
```
lore codex show codex
```
<!-- lore:access end -->
<!-- lore:access native -->
Read `.lore/codex/codex.md` with your own file tool.
<!-- lore:access end -->

## Step 4 — Discover the existing home

The dedup rule is **one fact, one file**. Search before you write, every time.
Run several searches when the topic has angles — entity name, workflow name,
command name, table name — and search both endpoints of a relationship.

<!-- lore:access cli -->
```
lore codex search <keyword>
lore codex list
lore codex show <id1> <id2> <id3>
lore rite list
lore rite search <keyword>
lore glossary search <term>
```

Batch ids into one `lore codex show` call — it deduplicates and appends matched
glossary terms.
<!-- lore:access end -->
<!-- lore:access native -->
Grep `.lore/codex/**/*.md` for the keyword and read the candidates directly with
your own file tool. Rites are YAML under `.lore/rites/main/` and
`.lore/rites/shared/`; the vocabulary is `.lore/codex/glossary.yaml`.

Two things you give up by reading files instead of asking Lore, and must do
yourself: glossary terms are not auto-attached to what you read, and a rite's
`use:` steps are not inlined — follow each bare id to its file under
`.lore/rites/shared/`.
<!-- lore:access end -->

Traverse the graph with `lore codex map <id>` and `lore codex chaos <id>`, and
cross the codex↔code boundary with `lore impacts <path-or-id>`. No file tool
reproduces a precomputed traversal, so these stay on the CLI in every mode.

Then decide:

- A document already covers this fact → **stop**, there is nothing to record.
- A document covers a closely related fact the new one extends → **edit** it.
- The fact is a different scope → **create**, and link it from the nearest
  existing document.
- The fact already lives elsewhere → **link**, never copy.
- The knowledge is no longer true and nothing supersedes it → **delete**.

## Step 5 — Read the reference for the shape you picked

Each reference carries the frontmatter shape, the authoring rules and the exact
commands for one shape of memory. Read the one you need — not all three.

| You are recording | Read |
|---|---|
| A fact about the system | `references/codex-doc.md` |
| A procedure | `references/rite.md` |
| An upstream artifact | `references/source.md` |
| A vocabulary term | the gate and the write path below — no reference file |

Every canonical document also speaks with one voice. Read the rules before you
draft prose:

```
lore artifact show codex-voice
```

If the change adds or modifies an entry in `.lore/codex/glossary.yaml`, run the
gate first — most term-like additions belong in an entity, workflow or decision
document instead:

```
lore artifact show glossary-design
```

A term that passes the gate is one entry in one file — no reference of its own.
`keyword` is the identity, so renaming a term is a delete plus a new one.

<!-- lore:access cli -->
```
lore glossary new <keyword> --definition "..." [--alias <form>] [--do-not-use <form>]
lore glossary edit <keyword> --definition "..."
lore glossary delete <keyword>
```
<!-- lore:access end -->
<!-- lore:access native -->
Add or amend the entry in `.lore/codex/glossary.yaml` yourself, under the
top-level `items:` list:

```yaml
items:
  - keyword: Constable
    definition: >-
      Mission type for orchestrator-handled chores.
    aliases:
      - constable mission
```

Two things the CLI would have done that you now own: validating the entry
against the glossary schema, and keeping `keyword` unique across the file.
`lore health --scope glossary` catches both — it is in the step 7 run.
<!-- lore:access end -->

## Step 6 — Apply the change

Follow the reference file. It names the create, edit and delete path for that
shape.

## Step 7 — Verify

```
lore health --scope codex schemas rites glossary voice
```

`lore health` is the validator every mode leans on, so it stays on the CLI.
Fix every error before you declare done. `voice` reports warnings, never
errors — read each one and either rewrite the sentence or confirm it passes the
two tests in `codex-voice`.

Then confirm the knowledge is findable. Re-run the search from step 4 and check
the new or edited document comes back. If it does not, the discoverability words
are wrong — fix the summary or the body until the search finds it.

## Step 8 — Report

Tell the user:

- Ids created, with a one-line description of each.
- Ids edited, and the fact that changed.
- Ids deleted, and why the knowledge stopped being true.
- Anything deliberately left alone, and why — dedup, out of scope, speculation.
- The `lore health` result.

Report what *changed*, not what the documents *say*. The user can read them.
