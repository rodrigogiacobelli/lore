---
id: ui-write-file
feature: memory
capabilities: [memory-index]
commands: [index build]
---
### 6. Write the file

`.lore/index/authored.yaml` is a plain project file at a path you know, not a Lore entity with an id, so you write it
directly with your own file tool. Preserve the entries you are not changing: an overwrite drops every group somebody
else wrote up. `lore index build` creates `.lore/index/` on its first run.
