---
id: iq-verdict
feature: quests
requires: [memory]
---
### 4. Write the verdict

Write the blame file to `.lore/codex/transient/inquest-<slug>.md`, where `<slug>` is a short kebab-case name for the issue.
The verdict is a transient codex doc with frontmatter `id`, `title` and `summary`, and a body that names the culprit link,
the failure mode, the responsible party and the evidence. It survives report runs, unlike `.lore/reports/`, which is wiped
on every run.
