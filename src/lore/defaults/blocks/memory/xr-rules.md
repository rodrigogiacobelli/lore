---
id: xr-rules
feature: memory
---
## Rules to hold while drafting

- **`id` is bare and globally unique** across every main rite and shared step in every subfolder, like a codex id. The
  subfolder is cosmetic and only sets the display `group`.
- **`use:` names a bare id**, never a path. Discovery is recursive.
- **Main-rite well-formedness:** exactly one entry node; every node reachable; every `then` / `goto` points at a node id
  or a conclusion key; every conclusion reached is defined and every defined conclusion is reachable.
- **A shared step is pure:** single exit, no `nodes` / `then` / `goto` / `use` / `conclusions`. Branching belongs in the
  consuming main rite.
- **No outbound links.** A rite carries no `related` and no `binds`. The codex points at rites; rites never point back.
- **Retrieval is AI-as-matcher.** Lore never matches a situation to a rite. `trigger` and `summary` are the entire
  retrieval surface; write them for the agent scanning the list.
