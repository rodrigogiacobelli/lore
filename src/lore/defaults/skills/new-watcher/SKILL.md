---
name: new-watcher
description: Draft and create a new watcher via `lore watcher new`
---

# New Watcher

Create a new Lore watcher. Watchers are YAML definitions for agents that monitor and react to project state — they describe what to watch for and what to do when it triggers.

## Steps

### 1. Understand the watcher

Ask the user (or read from context):
- What should this watcher monitor? (e.g. "when a quest closes", "when a mission is blocked", "when a file changes")
- What should it do when it triggers?
- How often or under what conditions should it fire?

### 2. Check existing watchers

```
lore watcher list
```

Look at an existing watcher for reference:

```
lore watcher show <existing-watcher>
```

### 3. Draft the YAML

Write the watcher definition to a temporary file. Use the existing watcher format as your template — `lore watcher show` of an existing one gives you the schema to follow.

### 4. Create

```
lore watcher new <name> --from <temp-file>
```

### 5. Verify

```
lore watcher show <name>
```
