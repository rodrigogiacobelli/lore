---
id: sm-discover-harness
feature: memory
requires: [route=harness]
---
Grep `.lore/codex/**/*.md` for the keyword and read the candidates directly. Rites are YAML under
`.lore/rites/main/` and `.lore/rites/shared/`; the vocabulary is `.lore/codex/glossary.yaml`.

Two things you give up by reading files, and must do yourself: glossary terms are not attached to what you read, and a
rite's `use:` steps are not inlined, so follow each bare id to its file under `.lore/rites/shared/`.
