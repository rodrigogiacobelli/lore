---
id: xa-frontmatter
feature: memory
---
## Frontmatter

Exactly these fields, plus any project-local keys declared in a `.lore/custom-schemas/` overlay:

```yaml
---
id: <unique-id>
title: <human title>
summary: <1-3 sentences for scanning>
related:        # optional; omit or use [] if none
  - <other-id>
binds:          # optional; repo-root-relative paths or globs this doc governs
  - <path-or-glob>
rites:          # optional; the rites this doc governs
  - <rite-id>
---
```
