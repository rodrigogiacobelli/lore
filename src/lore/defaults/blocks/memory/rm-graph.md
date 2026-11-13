---
id: rm-graph
feature: memory
capabilities: [memory-graph]
commands: [codex map, codex chaos, impacts]
---
## Step 2: Traverse the graph for the *what*

From the most relevant document, walk its neighbours:

```
lore codex map <id>                    # bidirectional neighbours, depth 1
lore codex map <id> --depth N          # deeper; --depth-out N follows `related` only, --depth-in N backlinks only
lore codex map <id> --full             # full bodies instead of the table
lore codex chaos <id> --threshold 50   # serendipitous discovery; 30 broad, 100 tight
```

## Step 3: Cross to code, and back

```
lore impacts <codex-id>          # the code files this document governs
lore impacts <path-or-glob>      # the documents that govern this file
```

`impacts` is a bidirectional index over every `binds:` field. When a search lands on a technical or standards document,
read the files it governs if the question is about implementation. When the question starts from a file path, run
`impacts` on it first and read the governing documents before the code.
