---
id: xo-guard
feature: memory
---
### The add-only guard

The resolver rejects a bad overlay, so catch it before you write.

**(a) Collision check.** No custom field name may collide with a **packaged** field of that kind; if one does, stop and ask
the author to rename it.

| Kind | Protected (packaged) keys: never add or override |
|---|---|
| `codex-frontmatter` | `id`, `title`, `summary`, `type`, `related`, `binds`, `rites` |
| `codex-source-frontmatter` | `id`, `title`, `summary`, `type`, `related` |

**(b) Undeclared-required check.** Every name in `required:` must be a field this overlay declares in `properties:`. You may
not require a packaged field (the base already governs it) nor a name that does not appear in your `properties`.
