---
id: ua-existing-cli
feature: artifacts
requires: [route=cli]
commands: [artifact list, artifact show]
---
```
lore artifact list
lore artifact show <similar-or-target-artifact-id>
```

The id is the only stable handle on a file whose path may move: the artifact tree hides a `default/` versus flat split,
slash-derived groups and `.deleted` soft-delete naming.
