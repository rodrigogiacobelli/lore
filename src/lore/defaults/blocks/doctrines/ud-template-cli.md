---
id: ud-template-cli
feature: doctrines
requires: [route=cli]
commands: [artifact show]
---
## Input: design doc (preferred)

The user may provide a design doc. If they are unsure of the format, show them the template: `lore artifact show doctrine-design`

When a design doc is provided, use it as the authoritative spec: its table maps directly to mission files. If none is
provided, ask the user for the workflow description before proceeding.
