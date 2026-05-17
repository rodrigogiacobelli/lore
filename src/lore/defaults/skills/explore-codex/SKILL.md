---
name: explore-codex
description: Search, map, and traverse the codex to answer a question
---

# Explore Codex

Use the Lore codex to research a question, compare information, or map out a domain. The codex is a graph of typed markdown documents — use search to find entry points, map/chaos to traverse connections, and show to read content.

## When to use which command

| Goal | Command |
|------|---------|
| Find documents by keyword | `lore codex search <keyword>` |
| Read one or more documents | `lore codex show <id1> <id2> ...` |
| List neighbours of a document (bidirectional, depth 1 by default) | `lore codex map <id>` |
| Read full bodies of a document and its neighbours | `lore codex map <id> --full` |
| Walk outbound `related` links only | `lore codex map <id> --depth-out N` |
| Walk inbound backlinks only | `lore codex map <id> --depth-in N` |
| Discover loosely connected documents serendipitously | `lore codex chaos <id> --threshold <30-100>` |
| See everything | `lore codex list` |
| List project vocabulary | `lore glossary list` |
| Search glossary terms | `lore glossary search <query>` |
| Read one or more glossary entries | `lore glossary show <kw1> <kw2> ...` |

Searching by the name of a concrete artifact (a table, endpoint, event, job) typically lands on a `ref-<system>-<concept>` cluster doc under `technical/<domain>/ref/`. Those docs hold intent (history, gotchas, non-enforced constraints) — not schema. The schema source of truth is named in the doc body and lives in code (migrations, OpenAPI, ORM).

## Steps

### 1. Find entry points

Start with a keyword search:

```
lore codex search <keyword>
```

Run multiple searches if the topic has several angles. Note the IDs of relevant documents.

### 2. Read the relevant documents

```
lore codex show <id1> <id2> <id3>
```

Prefer batching multiple IDs in one call over separate calls.

### 3. Traverse the graph if needed

From the most relevant document, list its neighbours:

```
lore codex map <id>
```

Default is a neighbour table — same columns as `lore codex list` — bidirectional at depth 1 (outbound `related` plus inbound backlinks). Tweak as needed:

- `--depth N` — symmetric deeper walk
- `--depth-out N` / `--depth-in N` — one-direction-only walk (mutually exclusive with `--depth`)
- `--full` — print full bodies instead of the table

For broader discovery, use chaos traversal. `--threshold` is required (30 = broad walk, 100 = tight walk):

```
lore codex chaos <id> --threshold 50
```

Read any additional documents that look relevant.

### 4. Answer the question

Once you have read enough context, answer what the user asked. Cite codex document IDs when referencing specific information (e.g. "per `lore codex show ops-git-workflow`...").

If the codex does not contain the answer, say so clearly rather than inferring from incomplete information.
