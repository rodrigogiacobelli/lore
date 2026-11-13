---
id: ud-artifacts
feature: doctrines
requires: [route=cli]
mentions: [update-artifact]
---
**Create artifacts first.** For each new artifact in the design doc, create it before writing the doctrine, because the mission
files reference artifacts by id. Use the `update-artifact` skill for each one and verify it is retrievable by its id.
