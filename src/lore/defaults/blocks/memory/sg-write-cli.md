---
id: sg-write-cli
feature: memory
route: cli
commands: ['codex edit']
glue: tight
---
Apply the merged body through the CLI, which normalises frontmatter and validates against any project overlay:
`lore codex edit codex -f <merged-body>.md`
