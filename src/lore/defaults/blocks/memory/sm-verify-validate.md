---
id: sm-verify-validate
feature: memory
commands: [health --scope codex, health --scope schemas, health --scope rites, health --scope glossary, health --scope voice]
---
## Step 7: Verify

```
lore health --scope codex schemas rites glossary voice
```

Fix every error before you declare done. `voice` reports warnings, never errors: rewrite the sentence or confirm it passes
the two tests in the voice rules.
