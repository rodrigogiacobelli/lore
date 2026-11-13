---
id: uw-context-harness
feature: watchers
requires: [memory.harness]
---
A watcher reacts to project state, so check what the project already records about that state: a condition already
governed by a documented rule should reference it rather than restate it. Grep `.lore/codex/**/*.md` for the state the
watcher reacts to and read the candidates directly.
