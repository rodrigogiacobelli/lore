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
| Explore related documents from a starting point | `lore codex map <id> --depth 1` |
| Discover loosely connected documents serendipitously | `lore codex chaos <id> --threshold <30-100>` |
| See everything | `lore codex list` |
| List project vocabulary | `lore glossary list` |
| Search glossary terms | `lore glossary search <query>` |
| Read one or more glossary entries | `lore glossary show <kw1> <kw2> ...` |

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

From the most relevant document, explore its connections:

```
lore codex map <id> --depth 1
```

For broader discovery, use chaos traversal (threshold 30 = broad, 100 = tight):

```
lore codex chaos <id> --threshold 50
```

Read any additional documents that look relevant.

### 4. Answer the question

Once you have read enough context, answer what the user asked. Cite codex document IDs when referencing specific information (e.g. "per `lore codex show ops-git-workflow`...").

If the codex does not contain the answer, say so clearly rather than inferring from incomplete information.
