---
id: uf-shape
feature: memory
capabilities: [memory-index]
---
## The authored index file

`.lore/index/authored.yaml` is one mapping, each entry keyed by the cluster's hub. Create it whole the first time (`version: 1`
and an `entries` mapping) and preserve every entry you are not changing:

```yaml
version: 1
entries:
  conceptual-workflows-lore-init:      # the cluster's HUB: this is the key
    slug: init
    name: Initialising a project
    summary: What `lore init` writes and how it reconciles a project.
    authored_against: "b41f...64 hex characters..."
```
