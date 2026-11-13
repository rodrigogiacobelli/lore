---
id: uf-keys
feature: memory
capabilities: [memory-index]
commands: [index build]
---
## Fields

- the key: the cluster's hub, exactly as `lore index build` reports it
- `slug`: lowercase, digits and hyphens, 1-60 chars; the display key of a row
- `name`: 1-80 chars, one line; what a reader sees in a search result
- `summary`: 1-1000 chars; what the group covers, for someone deciding whether to read it
- `authored_against`: the cluster's current digest, 64 lowercase hex characters. **Quote it**: an all-digit digest parses as
  an integer in unquoted YAML and fails the schema.
