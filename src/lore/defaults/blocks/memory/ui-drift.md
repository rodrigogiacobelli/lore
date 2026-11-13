---
id: ui-drift
feature: memory
capabilities: [memory-index]
---
### 3. Refresh each `drifted` cluster

The members changed since the summary was written. Re-read them, rewrite `name` and `summary` if the subject moved, and
replace `authored_against` with the current digest either way.

### 4. Resolve each stale entry

- `hub <id> heads no cluster`: the document exists but the partition moved. Re-key the entry to the hub of the cluster that
  holds those documents now.
- `hub <id> is not a document in this codex`: the hub was deleted or renamed. Re-key the entry to where its documents
  landed, or delete it if the group is gone.

Never re-key an entry without reading the new cluster's members.
