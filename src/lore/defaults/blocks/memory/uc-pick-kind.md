---
id: uc-pick-kind
feature: memory
---
## Steps

### 1. Pick the target kind

Overlays are discovered by filename, `<kind>.yaml`, with no config. Exactly two kinds are eligible: `codex-frontmatter`
(canonical codex docs, overlay `.lore/custom-schemas/codex-frontmatter.yaml`) and `codex-source-frontmatter` (the codex
**sources** layer, overlay `.lore/custom-schemas/codex-source-frontmatter.yaml`).

Ask the author which kind to extend. If an overlay for that kind exists, read it and **edit** it: each kind gets at most
one overlay file, so an overwrite silently drops every field the project already declared. An overlay is a plain project
file at a path you know, not a Lore entity with an id.
