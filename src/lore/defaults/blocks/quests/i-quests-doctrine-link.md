---
id: i-quests-doctrine-link
feature: quests
commands: [new, show]
mentions: [start-quest]
---
Start a quest from a doctrine with `/start-quest`: it reads the doctrine, creates the quest with `lore new quest` and
each mission with `lore new mission -D <doctrine-id>/<mission-id>`, so `lore show` hands every worker its doctrine
mission.
