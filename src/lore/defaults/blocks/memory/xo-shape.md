---
id: xo-shape
feature: memory
---
### The overlay file

The **add-only** shape is a header comment, a `properties:` mapping (required) and an optional `required:` list. Do **not**
emit `additionalProperties`, `$id`, `$schema`, `title` or `type: object`: the resolver synthesizes them. Create
`.lore/custom-schemas/` if it does not exist.

```yaml
# Add-only overlay for codex canonical-doc frontmatter.
properties:
  owner:
    type: string
    minLength: 1
    description: Team or person accountable for this doc.
required:
  - owner
```
