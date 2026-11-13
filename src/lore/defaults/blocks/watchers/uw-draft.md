---
id: uw-draft
feature: watchers
---
### 3. Draft the YAML

Write the watcher definition. All of these fields are required, and `id` equals the filename stem:

- `id`, `title`, `summary`
- `watch_target`: a non-empty list of paths or globs, relative to the repo root
- `interval`: one of `on_merge`, `on_commit`, `hourly`, `daily`, `weekly`, `manual`
- `action`: a non-empty list; each entry has exactly one key, `doctrine: <doctrine-id>` or `bash: "<command>"`

An existing watcher is the model to follow.
