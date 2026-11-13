---
id: sg-rule
feature: memory
commands: [init]
---
## How it works

`lore init` overwrites Lore-owned seed files and leaves user-tracked files alone, and the skill exploits that asymmetry:
the seed at `.lore/artifacts/default/codex/codex.md` is the freshly overwritten target, and `.lore/codex/codex.md` is the
project file you update. Every difference between them is either **generic** (describes how Lore or the codex works:
sync it) or **project-specific** (leave it alone). The rule and what to do when a generic section looks deliberately customized follow.
