---
id: ui-purpose
feature: memory
capabilities: [memory-index]
commands: [index build]
---
# Update Index

Lore partitions the codex `related` graph into **clusters** of densely linked documents and names each cluster's **hub**,
the member most linked to the rest of its cluster. It does not name the clusters; that is this skill's job.
`.lore/index/authored.yaml` is the only file in the index a rebuild cannot recover, and **no Lore command writes it**. You
do. Everything else (`.lore/index/codex.json`, the partition, the digests) is regenerated on demand.

Run this skill when `lore index build` reports a cluster that is `unauthored` or `drifted`, a stale entry, or after a batch
of codex work has moved the graph.
