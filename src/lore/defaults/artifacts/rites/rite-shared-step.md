---
id: rite-shared-step
title: Shared Step Template
summary: >
  Copy-paste skeleton for a shared step — a small, reusable, pure procedure that
  main rites pull in with `use:`. Lives under `.lore/rites/shared/` (optionally in
  a subfolder, which becomes its group). A shared step only does and reports; it
  holds NO judgment, no branching, no conclusions. See `lore artifact show
  rite-design` for worked examples.
---

# Shared Step Template

A **shared step** is the smallest reusable unit of procedural memory — a few
clicks in one platform, one database query, one lookup. It runs and reports; it
has a single exit. All judgment about what to do with the result stays in the
main rite that `use:`s it.

Create with `lore rite new <id> --shared --group <path>` (group optional), then
`lore rite edit <id> --shared --from <file>`. The `id` is globally unique across
the whole tree (main steps and shared steps share one id namespace); the
subfolder is cosmetic and becomes the `group`.

```yaml
id: {bare-unique-id}            # globally unique across ALL rites; folder is not identity
title: {short human title}
summary: {one line — what this step does, e.g. "Read the user's contact info from admin."}
do: |
  {Plain, concrete instructions for the one procedure this step performs.}
  {Say exactly what to read/click/run and what to report back.}
  {Keep it small — one platform, one screen, one query.}
```

## Rules

- **Pure procedure only.** A shared step has exactly four fields: `id`, `title`,
  `summary`, `do`. It must NOT contain `nodes`, `then`, `goto`, `use`, or
  `conclusions` — `lore health --scope rites` rejects any of those (the
  single-exit rule).
- **`summary` is required** — a one-line description of what the step does, like
  every other Lore entity. It is NOT a retrieval cue: only main rites carry a
  `trigger`. A shared step is pulled in by id via `use:`, never matched by
  situation, so it has no trigger.
- **No judgment.** If you find yourself wanting to branch ("if X then…"), that
  belongs in the consuming main rite, not here. The step reports facts; the rite
  decides.
- **`id` is bare and globally unique** in any subfolder. A main rite reaches this
  step by `use: {bare-id}` — never by path.
- **Group by platform/system** for browsability — e.g. `shared/portal/…`,
  `shared/backoffice/…`, `shared/db/…`. Grouping is organisation only; it does
  not change how `use:` resolves.
