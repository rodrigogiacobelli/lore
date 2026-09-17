---
id: decisions-037-index-is-a-top-level-lore-directory
title: "ADR-037: .lore/index/ is a top-level directory — one committed authored file, one ignored render"
summary: >
  ADR recording that the codex index lives in its own top-level directory under
  .lore/, holding authored.yaml (committed) and codex.json (git-ignored). lore
  init seeds neither and creates neither; build_index creates the directory on
  its first write. The seeded .lore/.gitignore carries !index, !index/** and
  index/codex.json.
binds:
  - src/lore/paths.py
  - src/lore/defaults/gitignore
related:
  - decisions-013-toml-for-config-yaml-for-glossary
  - decisions-021-health-reports-are-ephemeral-by-default
  - decisions-041-render-is-a-cache-invalidated-by-a-stat-fingerprint
  - tech-arch-initialized-project-structure
  - tech-arch-codex-index
---

# ADR-037: .lore/index/ is a top-level directory — one committed authored file, one ignored render

## Context

ADR-013 records a carve-out that keeps `glossary.yaml` and `codex.md` inside
`.lore/codex/` rather than under a `default/` subtree. No ADR said whether a new
top-level directory under `.lore/` is permitted, and the codex index needs a
home for two files with opposite lifecycles: one hand-authored and committed,
one generated and disposable.

## Decision

`.lore/index/` holds `authored.yaml`, which is committed, and `codex.json`,
which is git-ignored.

`lore init` seeds neither file and creates neither; `build_index` creates the
directory on its first write. The seeded `.lore/.gitignore` carries `!index`,
`!index/**` and `index/codex.json`, in that order — the un-ignore pair is
required for git to descend into the directory at all, and the third line then
ignores the render alone.

## Rationale

- **`.lore/codex/` is a markdown tree three audits walk.** A generated JSON
  cache inside it is a file each of them has to be taught to skip.
- **Two halves of one artefact belong in one place.** Splitting them across two
  directories leaves a reader hunting for the second.
- **The two lifecycles differ, the subject does not.** One directory with one
  extra ignore line expresses that; two directories express a difference in
  subject that does not exist.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Both files under `.lore/codex/`** | `.lore/codex/` is a markdown tree three audits walk, and a generated JSON cache inside it is a file each of them has to be taught to skip. |
| **Authored file in `.lore/codex/`, render elsewhere** | Two locations for two halves of one artefact, and the render would still need a home. |
| **Render under `.lore/reports/`** | That directory is wiped and recreated by `lore oracle`, which would delete the cache on an unrelated command. |

## Consequences

**Easier:**
- A reader finds both halves of the index in one directory.
- The codex audits keep walking markdown only, with no JSON exclusion to
  maintain.

**Harder:**
- `.lore/` gains a fourth top-level directory a reader has to learn.
- The seeded `.lore/.gitignore` needs the `!index` / `!index/**` pair before the
  `index/codex.json` line, because the `*` that opens the file otherwise stops
  git descending into the directory and the third line never matches.

## Constraints Imposed

1. **`.lore/index/authored.yaml` is committed and `.lore/index/codex.json` is
   git-ignored.** A project that tracks the render tracks a file whose content
   is a function of its own codex.
2. **`lore init` creates neither file.** The directory appears on the first
   `build_index` write.
3. **A new top-level directory under `.lore/` takes an ADR.** This one is the
   recorded case.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded with the `lore index` command group, the first feature to need a `.lore/` directory that is neither an entity tree nor a report tree. |
