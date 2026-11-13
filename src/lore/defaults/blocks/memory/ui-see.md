---
id: ui-see
feature: memory
capabilities: [memory-index]
commands: [index build]
---
## Steps

### 1. See what needs writing

Run `lore index build`. Every row is `ok`, `unauthored` or `drifted`; an authored entry the partition has left behind prints
below the table as a stale entry. The command never writes `authored.yaml`, so it is safe to run at any time.
