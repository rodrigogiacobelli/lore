---
id: xr-pick
feature: memory
---
# Reference: recording a procedure as a rite

Read this when the knowledge is procedural: how to do or diagnose a recurring task. A rite is not documentation and not
a template that spawns work. It is organised know-how an agent reads and follows in the moment.

## Pick the shape

A rite has two shapes.

- **Main rite** (`.lore/rites/main/`): a node-graph that carries the judgment, with branching nodes routed by `then` /
  `if` / `goto`, ending in typed `conclusions`. Choose it when the procedure weighs a result, branches on a condition,
  or ends in one of several outcomes.
- **Shared step** (`.lore/rites/shared/`): a pure, reusable procedure with a single exit: `id`, `title`, `summary`, `do`
  and nothing else. No branching, no trigger, no conclusions. Choose it for one platform, one screen, one query that
  reports a fact and never decides.

A main rite composes shared steps with `use:`. When a procedure repeats across rites, factor it into a shared step.
