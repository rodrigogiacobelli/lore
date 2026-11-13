---
id: gs-rerun
feature: core
requires: ['pseudo:cli']
commands: [init]
---
## Re-run it whenever the answers change

`lore init` is idempotent and reconciles: it installs what is newly selected, removes what Lore installed and you have
since deselected, and reports any skill a release retired along with its successor.

```
lore init --reconfigure      # ask the recorded questions again (needs a terminal)
lore init --dry-run          # print the plan and write nothing
lore init --help             # every question also has a flag
```

Your answers are recorded in `.lore/config.toml` and reused: the agents, how agents reach each feature, the opt-in
capabilities, and how installed skills are tracked in git.
