---
id: iq-evidence
feature: quests
requires: [memory]
commands: [show]
---
### 2. Collect the evidence

- **The original intent**: the quest description and the first transient doc (PRD or context map) in
  `.lore/codex/transient/`.
- **The intermediate outputs**: every transient doc in `.lore/codex/transient/`. These are the per-link outputs: PRD, tech
  spec, user stories.
- **The handoffs**: the board messages passed between missions, shown by `lore show`.
- **The commits**: `git log` and `git show <sha>` for the range that delivered the work. Commit messages reference story
  ids.
