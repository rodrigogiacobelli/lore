---
id: xa-binds
feature: memory
---
## The `binds:` workflow

`binds:` is the codex-to-code edge, and it points one way: the codex names the code, never the reverse. Populate it
whenever a document governs specific files, typically technical documents, standards, decision records and `ref-*`
clusters.

Globs use `**` for recursive descent (`src/lore/**/*.py`). Literal paths and globs mix freely in one list. Absolute
paths, `..` segments and empty strings are rejected by the schema.
