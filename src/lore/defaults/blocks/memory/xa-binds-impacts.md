---
id: xa-binds-impacts
feature: memory
capabilities: [memory-graph]
commands: [impacts]
---
A document with `binds: [src/lore/cli.py]` is surfaced by `lore impacts src/lore/cli.py`. After editing `binds:`, verify
the document's reach:

```
lore impacts <codex-id>          # the paths the doc claims
lore impacts <path-or-glob>      # the docs claiming this path
```
