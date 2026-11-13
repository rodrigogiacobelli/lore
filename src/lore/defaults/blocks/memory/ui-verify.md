---
id: ui-verify
feature: memory
capabilities: [memory-index]
commands: [index build, index search]
---
### 7. Verify

Run `lore index build`, then `lore index search <a keyword from a summary you wrote>`. Every cluster reports `ok` and the
search returns the cluster you described. The match is a plain substring of the whole query, so spell out the phrase a
reader would type, unhyphenated; see the search rules below.
