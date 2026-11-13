---
id: ud-design
feature: doctrines
---
### 2. Draft the design document

The design document is the file the doctrine is named for: `<id>.design.md`. Its frontmatter carries exactly `id`, `title`
and `summary`, and its `id` must equal the doctrine name. Fill in the mission table (phase, mission id, type, depends-on,
input, output), the artifacts the doctrine uses, the escalation table and any notes. The type tokens are `agent` (a
worker), `constable` (an orchestrator chore handled inline) and `human` (needs the user; never claimed). The table is the
single source of order, dependency, phase and type.
