---
id: ui-digest
feature: memory
capabilities: [memory-index]
commands: [index build]
---
### 5. Get the digest

Each entry's `authored_against` is the digest of the cluster it describes. `lore --json index build` returns one object per
cluster: match on `hub` and take the `digest` (the human table shows the status, not the digest). Write the entry, then
re-run `lore index build`: a row that stays `drifted` means the digest came from the wrong cluster, or the codex changed
between the two runs.
