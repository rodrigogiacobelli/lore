---
id: sm-index-refresh
feature: memory
capabilities: [memory-index]
commands: [index search, index build]
mentions: [update-index]
---
## Refresh the codex index

A new or deleted document changes the `related` graph, which changes the clusters `lore index search` routes by.

```
lore index build
```

A project that never authored an index reports every cluster `unauthored`: leave it. A project that *has* one reports what
your change moved (an `unauthored` cluster, a `drifted` summary, a stale entry). Update those rows now, from the documents
in context; the `update-index` skill has the file and the digest. Report any you left.
