---
id: rm-rites-harness
feature: memory
route: harness
---
## Step 4: Cross to the rites for the *how*

| Goal | Where |
|---|---|
| Browse main rites | read `.lore/rites/main/**/*.yaml`; `trigger` and `summary` are the retrieval surface |
| Browse reusable shared steps | read `.lore/rites/shared/**/*.yaml` |

**Shared steps are not inlined.** A main rite's `use:` names a bare id; find that file anywhere under
`.lore/rites/shared/` and read it too, or you are following half a procedure.
