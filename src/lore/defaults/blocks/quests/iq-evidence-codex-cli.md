---
id: iq-evidence-codex-cli
feature: quests
requires: [memory.cli, memory]
commands: [codex list, codex show]
glue: tight
---
- **Reading the transient docs**: `lore codex list --filter transient` and `lore codex show <id1> <id2>`; batch ids into
  one call.
