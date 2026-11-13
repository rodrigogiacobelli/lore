---
id: iq-chain-doctrine-cli
feature: quests
requires: [route=cli, memory]
commands: [doctrine show]
---
The doctrine's design document carries the dependency order: `lore doctrine show <doctrine-id>`. Where a Lore mission
carries no doctrine mission reference, read the doctrine's own copy with `lore doctrine show <doctrine-id> --mission <mission-id>`.
