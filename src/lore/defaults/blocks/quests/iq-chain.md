---
id: iq-chain
feature: quests
requires: [memory]
commands: [show, missions]
---
## Steps

### 1. Reconstruct the chain

Identify the doctrine that drove the work and list its missions in dependency order:

```
lore show <quest-id>
lore missions -q <quest-id>
```

For each doctrine mission record its id, the Lore mission id that ran it, and that mission's status. `lore show <mission-id>`
returns the doctrine mission body and the description the executing agent actually received: together they are the
instructions that link was held to.
