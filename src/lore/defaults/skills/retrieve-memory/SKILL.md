---
name: retrieve-memory
description: Answer a question from project memory, consulting both the codex for what is true and the rites for how to do or diagnose something
---

# Retrieve Memory

One entry point for reading project memory. Use it to research a question,
compare information, map a domain, or find the procedure for a recurring task.

Project memory has two surfaces and this skill consults both:

- **Codex** — semantic knowledge: *what is true*. A graph of typed markdown
  documents you search, read and traverse.
- **Rites** — procedural knowledge: *how to do or diagnose X*. Node-graph main
  rites that carry the judgment, composed from pure shared steps.

A "what / why / where" question is codex. A "how do I" question is a rite. Many
real questions carry both — "what is our refund policy *and* how do I issue
one" — and then you run both. They are complementary, not alternatives.

## The bridge runs one way

A codex document names the rites it governs in its `rites:` frontmatter field.
Rites carry no links back. So when a question has both halves, start in the
codex: find the governing document, read it for the *what*, then follow its
`rites:` field to the *how*. Nothing bridges in the other direction — if you
start from a rite, you find the codex document by searching for it.

## Step 1 — Classify and enter

Decide what the question is really asking, then pick the entry point.

<!-- lore:access cli -->
| Goal | Command |
|---|---|
| Find documents by keyword | `lore codex search <keyword>` |
| Read one or more documents | `lore codex show <id1> <id2> ...` |
| See the whole taxonomy | `lore codex list` |
| Browse main rites — id, group, trigger, summary | `lore rite list` |
| Browse reusable shared steps | `lore rite list --shared` |
| Narrow a rite group | `lore rite list --filter <a/b>` |
| Keyword-browse rites by id, title, summary or trigger | `lore rite search <keyword>` |
| Read rites in full, shared steps inlined | `lore rite show <id1> <id2> ...` |
| List project vocabulary | `lore glossary list` |
| Search vocabulary | `lore glossary search <query>` |
| Read vocabulary entries | `lore glossary show <kw1> <kw2> ...` |

Batch ids into one `lore codex show` call — it deduplicates and appends the
glossary terms it matched, so an unfamiliar term arrives with its definition
attached. `lore rite show` inlines every shared step a main rite pulls in with
`use:`, so one call gives you the complete, follow-it-now procedure.
<!-- lore:access end -->
<!-- lore:access native -->
| Goal | Where |
|---|---|
| Find documents by keyword | grep `.lore/codex/**/*.md` |
| Read a document | read `.lore/codex/<layer>/<id>.md` |
| See the whole taxonomy | list `.lore/codex/` |
| Browse main rites | read `.lore/rites/main/**/*.yaml` — `trigger` and `summary` are the retrieval surface |
| Browse reusable shared steps | read `.lore/rites/shared/**/*.yaml` |
| Read the vocabulary | read `.lore/codex/glossary.yaml` |

Three things reading files gives up, which are now yours to do:

- **Glossary terms are not attached** to what you read. When a term is
  unfamiliar, look it up in `.lore/codex/glossary.yaml` yourself.
- **Shared steps are not inlined.** A main rite's `use:` names a bare id; find
  that file anywhere under `.lore/rites/shared/` and read it too, or you are
  following half a procedure.
- **The group is the directory.** A document's or rite's subfolder is its
  group; the id alone does not tell you where the file is, so grep for the id
  rather than guessing the path.
<!-- lore:access end -->

Run several searches when the topic has angles — entity name, workflow name,
command name, table name. Note the ids that look relevant.

Searching for the name of a concrete artifact — a table, an endpoint, an event,
a job — usually lands on a `ref-<system>-<concept>` cluster document under
`technical/<domain>/ref/`. Those hold intent: history, gotchas, constraints
nothing enforces. The schema itself is not there; the document names where it
lives in code.

## Step 2 — Traverse the graph for the *what*

From the most relevant document, walk its neighbours:

```
lore codex map <id>                    # bidirectional neighbours, depth 1
lore codex map <id> --depth N          # symmetric deeper walk
lore codex map <id> --depth-out N      # outbound `related` only
lore codex map <id> --depth-in N       # inbound backlinks only
lore codex map <id> --full             # full bodies instead of the table
lore codex chaos <id> --threshold 50   # serendipitous discovery; 30 broad, 100 tight
```

These stay on the CLI in every mode. `map` is a two-budget directional traversal
and `chaos` is a random walk with a reachable-subgraph termination ratio — no
sequence of file reads reproduces either.

## Step 3 — Cross to code, and back

```
lore impacts <codex-id>          # the code files this document governs
lore impacts <path-or-glob>      # the documents that govern this file
```

`impacts` is a bidirectional index over every `binds:` field in the codex, and
it is CLI-only for the same reason as the traversals. Use it in both
directions: when a search lands on a technical or standards document, enumerate
the files it governs and read them if the question is about implementation.
When the question starts from a file path, run `impacts` on it first and read
the documents that govern it before you read the code.

## Step 4 — Cross to the rites for the *how*

When the relevant codex document carries a `rites:` field, those are the
procedures attached to that knowledge — read them. When nothing bridged you,
match a rite yourself: retrieval is AI-as-matcher, and Lore never matches a
situation to a rite for you. Read each `trigger` — the prose cue — and each
`summary` — the one-line outcome — and pick the one that fits.

Then walk the nodes in order. At each `do` / `use` node, carry the result to the
`then` edge; at a fork, evaluate the `if` and follow the `goto`. Stop at a
`conclusion` — that typed outcome is the rite's answer. The judgment lives in
the rite; do not improvise past a conclusion.

## Step 5 — Answer, citing what you used

Stitch the factual and procedural halves into one answer. Cite codex ids for
facts and rite ids with the conclusion you reached for procedures, so the user
can go read the same thing.

If a surface does not hold the answer, say so plainly for that half rather than
inferring across the gap. A missing procedure is a signal to record one with
`store-memory`, not to improvise one.
