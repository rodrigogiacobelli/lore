---
id: sq-deps
feature: quests
commands: [needs]
---
### 5. Declare dependencies

For each depends-on entry in the design table, declare it with the fully qualified ids:

```
lore needs q-xxxx/m-yyyy:q-xxxx/m-zzzz q-xxxx/m-aaaa:q-xxxx/m-yyyy
```

A bare `m-yyyy` fails with "Mission not found". Repeat pairs until all dependencies are declared.
