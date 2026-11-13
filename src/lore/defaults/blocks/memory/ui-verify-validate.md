---
id: ui-verify-validate
feature: memory
capabilities: [memory-index]
commands: [health --scope index, index search]
glue: tight
---
Then run `lore health --scope index`. `schema` and `unresolvable_hub` are errors and must be cleared; the rest are
warnings that name work still to do. Check your summary lengths first: the cap is 1000 characters and it is a schema
rule, so **one over-length summary makes every `lore index search` return a schema error**, not just the row that broke
it.
