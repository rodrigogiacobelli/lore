---
id: rm-index
feature: memory
capabilities: [memory-index]
commands: [index search]
mentions: [update-index]
---
**Start with `lore index search <keyword>`.** It answers a keyword with named *clusters* of densely linked documents, so a
cold read lands on the whole group a topic lives in. It stays on the CLI even where the rest of this skill uses your own
file tools: the command rebuilds from the codex before it matches, so reading `.lore/index/` by hand answers from the last
build. A miss, or a `no index authored for this project` refusal, means the project has no index; use the entry points
below. Authoring one is the `update-index` skill's job, not this one's.
