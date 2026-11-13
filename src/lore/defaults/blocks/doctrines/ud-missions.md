---
id: ud-missions
feature: doctrines
---
### 3. Draft one mission file per mission

Every mission in the design table gets a file whose stem is the mission id. Its frontmatter carries exactly `id`, `title`
and `summary`, and `id` must equal the filename stem. The body is the worker's whole brief, in this order: the role it
adopts, how it works, its hard rules, its inputs, its steps, its done criteria, and what it hands on. Each file is
self-contained: there is no include mechanism, and no order, dependency, phase or type belongs in it. Say where each id
comes from ("your board messages contain the X ID"), and name artifacts and codex documents by id, never by a path that may
move.
