---
id: uw-purpose
feature: watchers
---
# Update Watcher

Author a Lore watcher. This skill **creates a watcher or edits an existing one**, whichever the request calls for: "make
the changelog watcher fire on merge too" and "watch for blocked missions" both land here.

Watchers are YAML definitions for agents that monitor and react to project state: they describe what to watch for and
what to do when it triggers.

## Creating or editing

- **Editing**: the watcher exists. Read it in full first, then change the one field the request names. A single-field edit
  is cheaper and safer than a whole-file replace.
- **Creating**: nothing watches for this condition yet. Run the whole flow below.
