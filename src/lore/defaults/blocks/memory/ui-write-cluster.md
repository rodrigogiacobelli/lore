---
id: ui-write-cluster
feature: memory
capabilities: [memory-index]
---
### 2. Write each `unauthored` cluster

For each `unauthored` row, read its members and write an entry keyed by its hub (the row shows `hub: <id>` where its name
would go). The members come from the JSON envelope or the render (step 5). Read titles and summaries first, both
frontmatter; open a body only when they do not tell you what the group is about. Then write `name` and `summary` in your
own words, as the writing rules below describe.
