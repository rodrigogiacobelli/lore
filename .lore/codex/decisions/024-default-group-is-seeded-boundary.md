---
id: decisions-024-default-group-is-seeded-boundary
title: "ADR-024: The default/ group is the seeded-vs-authored boundary"
summary: >
  ADR fixing how Lore tells a file it installed from one a project authored,
  for file-backed entities: an entity is a seeded default iff its derived
  group is `default` or begins with `default/` (projects.is_seeded_default).
  .lore/.install-manifest.json answers a different question and records no
  entity; codex.md and glossary.yaml are lore-init-written but not seeded
  defaults, because ADR-013 already carves both out as user-owned files
  written once and never overwritten.
binds:
  - src/lore/projects.py
  - src/lore/init.py
related:
  - decisions-013-toml-for-config-yaml-for-glossary
  - decisions-006-no-seed-content-tests
  - conceptual-workflows-nested-projects
  - tech-arch-initialized-project-structure
---

# ADR-024: The default/ group is the seeded-vs-authored boundary

## Context

An export must never offer a seeded default — a file Lore itself installed,
rather than one a project authored — but nothing before this feature had to
draw that line explicitly.

`.lore/.install-manifest.json` looked like the obvious mechanism, and is not:
it records only files Lore wrote **outside** `.lore/` — an agent's skills
directory, the root `.gitignore`, `.lore/LORE-AGENT.md` — and records no
knight, doctrine, artifact, watcher, or codex document. Reading it for export
eligibility would pass every entity through unfiltered.

Meanwhile `lore init` already seeds doctrines, knights, artifacts and watchers
into a `default/` subtree under each entity directory, and `.lore/.gitignore`
already names exactly those four subtrees (`doctrines/default/`,
`knights/default/`, `artifacts/default/`, `watchers/default/`). `lore init`
also writes `.lore/codex/codex.md` and `.lore/codex/glossary.yaml` directly —
not under a `default/` subtree — and ADR-013 already records both as
user-owned files, written once and never overwritten on re-init. Rites ship no
packaged files at all: `src/lore/defaults/` has no `rites/` directory, and a
fresh project's `.lore/rites/main` and `.lore/rites/shared` are empty.

## Decision

An entity is a **seeded default** iff its derived group is `default` or begins
with `default/`. `projects.is_seeded_default(group)` is the single home for
this test, wherever code must tell a file Lore installed from one a project
authored, for the file-backed entity kinds.

The install manifest keeps its own, different job — reconciling files Lore
wrote outside `.lore/` — and is not read by this feature. `lore init` writing
`.lore/codex/codex.md` and `.lore/codex/glossary.yaml` does not make either a
seeded default: neither ever carries a `default` group, so `is_seeded_default`
excludes nothing for codex or the glossary, and the exclusion for both was
already ADR-013's, not a new one. Rites ship no packaged files, so the test
excludes nothing for rites either — there is nothing under a `default/` group
for a rite to be.

## Rationale

- **The manifest and the `default/` group answer different questions.** The
  manifest reconciles a fixed set of files outside `.lore/` across a `lore`
  upgrade; the `default/` group marks a file inside `.lore/` as
  Lore-installed and re-seedable. Using one to answer the other's question
  silently drops coverage.
- **The `default/` convention already exists and is already load-bearing.**
  `.lore/.gitignore` already treats those four subtrees as disposable, and
  `_SeedTree(..., prune=True)` in `lore init` already re-seeds them on every
  run. This ADR names the existing convention as the export boundary rather
  than inventing a second one.
- **Excluding codex and the glossary rests on ADR-013, not on a new
  observation.** Both are user-owned carve-outs written once; the fact that
  `lore init` writes them does not make them Lore's to reclaim on export,
  any more than it makes them Lore's to overwrite on re-init.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Read the install manifest** | It records no knight, doctrine, artifact, watcher, or codex document — every entity would pass through unfiltered, and FR-10's exclusion would silently not hold. |
| **Record entities in the manifest too** | A `lore init` change this feature does not authorise, and it would make export filtering depend on a generated file that a `lore init` a version behind would populate differently. |
| **Compare content hashes against `src/lore/defaults/`** | An edited seeded default would read as authored the moment it diverged from the packaged copy — inverting the intended answer for the file most worth catching. |

## Consequences

**Easier:**
- One predicate answers "is this a Lore-installed file" for every file-backed
  entity kind that has a `default/` subtree, reusing the directory convention
  ADR-013 and `.lore/.gitignore` already establish rather than adding a
  second one.

**Harder:**
- The test is structural, not content-aware: a project that hand-edits a file
  inside a `default/` subtree, against the grain of the convention, still
  reads as a seeded default and is never exportable.

## Constraints Imposed

1. **`projects.is_seeded_default(group)` is the single home for the
   seeded-vs-authored question**, for every file-backed entity kind. No second
   implementation of the test.
2. **`.lore/codex/codex.md` and `.lore/codex/glossary.yaml` are never seeded
   defaults**, because neither entity ever carries a `default` group — the
   exclusion is ADR-013's carve-out, not a special case in this test.
3. **The install manifest is never consulted for export eligibility.** It
   answers a different question and stays scoped to files Lore writes outside
   `.lore/`.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-02 | accepted | Recorded alongside `projects.is_seeded_default`, the export filter's seeded-default exclusion. |
