---
id: sg-compare-head
feature: memory
---
### 3. Reconcile `.lore/codex/codex.md`

Compare the fresh seed against the project file. A raw `diff` is noisy against a customized file, so reconcile
**semantically**, section by section: read both in full, then **adopt** new layer definitions, content-class rules,
frontmatter fields and naming conventions, and **keep** this project's layer set, examples and local
rules. Never copy the `id:` line: the seed carries `id: example-codex`, the project file `id: codex`.
