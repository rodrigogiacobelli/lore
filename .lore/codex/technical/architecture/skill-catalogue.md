---
id: tech-arch-skill-catalogue
title: Skill Catalogue and Instruction Blocks
summary: The format of `skills-catalogue.yaml` (version 3) — legacy families, per-skill
  entries with a head block and ordered block lists per file, the two instruction
  documents, the line-cap exceptions and the append-only retirement ledger — plus the
  tagged-block format, the gate grammar, the command-grant table, the assembler that
  produces one skill file or instruction document from the blocks a profile keeps, and
  the lint that proves the caps and the no-leaked-command guarantee.
binds:
- src/lore/skills.py
- src/lore/blocks.py
- src/lore/blocklint.py
- src/lore/defaults/skills-catalogue.yaml
- src/lore/defaults/blocks/**
- src/lore/schemas/skill-catalogue.yaml
- src/lore/schemas/block.yaml
- src/lore/schemas/block-commands.yaml
- scripts/check_blocks.py
- tests/unit/test_skills.py
- tests/unit/test_blocks.py
- tests/unit/test_blocklint.py
- tests/unit/test_blocks_shipped.py
related:
- conceptual-entities-skill
- conceptual-workflows-lore-init
- conceptual-workflows-init-features
- conceptual-workflows-init-reconcile
- conceptual-workflows-init-interactive
- tech-arch-agents-md
- tech-arch-install-manifest
- decisions-001-dumb-infrastructure
- decisions-006-id-references
- decisions-006-no-seed-content-tests
- standards-dry
---

# Skill Catalogue and Instruction Blocks

Eleven skills ship with Lore. The catalogue records which blocks make up each skill file; the blocks under `src/lore/defaults/blocks/` carry the content. `conceptual-entities-skill` describes what a skill is and where it installs, and `conceptual-workflows-init-features` describes which answers install which skills.

## The Catalogue

`src/lore/defaults/skills-catalogue.yaml` sits at the `defaults/` root and validates against `lore://schemas/skill-catalogue` through `load_schema`, never through the overlay resolver. An unparseable or schema-invalid catalogue raises `RuntimeError` naming the packaged file — a build defect, never a user error.

```yaml
version: 3

legacy_families:
  memory:    {description: "Project memory - codex, rites and glossary", features: [memory], skills: [...]}
  machinery: {description: "Lore's own configuration entities", features: [doctrines, artifacts, watchers], skills: [...]}
  workflow:  {description: "Multi-step processes over quests and missions", features: [quests], skills: [...]}

skills:
  - id: store-memory
    head: sm-head
    files:
      - path: SKILL.md
        blocks: [sm-purpose, sm-name-it, ...]
      - path: references/codex-doc.md
        blocks: [xa-classify, ...]

documents:
  lore-agent:      {max_lines: 98, blocks: [i-intro, i-cli-help, ...]}
  getting-started: {max_lines: 100, blocks: [gs-intro, ...]}

oversize:
  store-memory/SKILL.md: 140
  store-memory/references/codex-doc.md: 112
  store-memory/references/rite.md: 140
  store-memory/references/source.md: 135

retired:
  new-doctrine: {into: update-doctrine, reason: renamed}
  # ... append-only
```

| Field | Meaning |
|---|---|
| `version` | The catalogue version, recorded in each install manifest as `catalogue_version`. |
| `legacy_families` | The retired family model: the token set of the deprecated `--skills` alias and the table the migration reads. |
| `skills[].id` | The skill's directory name at its install destination. |
| `skills[].head` | The id of the block holding the skill's frontmatter (`name`, `description`). |
| `skills[].files` | Each file the skill writes, with the ordered list of block ids it is assembled from. `SKILL.md` is first. |
| `documents` | The two instruction documents, `lore-agent` and `getting-started`, each with its block list and line cap. |
| `oversize` | The explicit, bounded exceptions to the 100-line skill-file rule. |
| `retired` | The ledger: every id Lore has shipped and no longer ships, the id that replaced it, and the reason. |

`retired` rows are **append-only**. A project hopping several releases needs every intermediate rename explained, and `reason` is quoted verbatim in the removal report. A chain is possible: `new-knight` retires into `update-knight`, which retires in turn into `update-doctrine`. Both rows stand, and a reader resolving where a skill went follows `into` until it lands on an id the release still ships.

`skills.resolve_families()` and `family_ids()` expand the `--skills` tokens (`all` is all three families, `none` is the empty list) for the deprecated alias; they take no part in choosing which skills install.

## Blocks

A block is one markdown file with YAML frontmatter, stored under `src/lore/defaults/blocks/<feature>/<id>.md`. The directory equals the block's `feature` tag, and the file stem equals its `id`. Block ids are globally unique and prefixed by owner: `i-` for the instruction text, `gs-` for the getting-started page, the skill's two-letter code for its blocks, and `x*`, `u*`, `s*` prefixes for reference files.

```markdown
---
id: sm-discover-cli
feature: memory
action: write
requires: [memory.read=cli]
commands: [codex list, codex search, codex show, rite search, glossary search]
mentions: []
glue: blank
---
Body markdown. No frontmatter fences. No template syntax.
```

| Tag | Meaning |
|---|---|
| `feature` | `core`, `memory`, `doctrines`, `artifacts`, `watchers` or `quests`. The feature must be on for the block to survive, except `core`. |
| `action`, `route` | The block survives when that action has that route; `action` alone means the route is not `off`; `route` alone means either action has it. |
| `capabilities` | Capability ids that must all be on. |
| `requires`, `unless` | Condition strings that must all hold, and none of which may hold. |
| `commands` | The `lore` command phrases the body uses. Lint compares it with what the body contains. |
| `mentions` | Skill ids or `skill/path` files the body refers to. Lint proves each target survives wherever the block does. |
| `glue` | `blank` (a blank line precedes the block) or `tight` (none does, for list items and table rows). |

A condition string is a feature id (`memory`; Doctrines and Artifacts are always true), a route test (`route=cli`), a feature-and-route test (`memory.cli`: the feature is on and the route is the CLI), a capability (`cap:memory-index`; `cap:validate` is always true) or a pseudo-capability: `pseudo:cli` (the route is the CLI, or Quests or a Memory opt-in is on) and `pseudo:skills` (at least one skill installed). There is no `or`, no `not` beyond `unless`, no variable and no include; a conjunction of tags is the whole language (`decisions-001-dumb-infrastructure`).

`blocks.assemble` returns the surviving blocks in catalogue order, and `blocks.join` writes each body stripped of surrounding blank lines, one blank line between blocks (none before a `tight` block) and a final newline. A skill file is its head block, a blank line and the joined body. The head never counts when deciding whether a skill has a surviving block.

## The Command-Grant Table

`src/lore/defaults/blocks/commands.yaml` lists every `lore` command phrase a block may contain and the conditions under which it may. A phrase is permitted when any grant holds. A block may declare a phrase only when its own tags imply one of that phrase's grants, so "a command whose capability is off appears nowhere" is a property of the block set, not of one profile.

| Phrases | Grant |
|---|---|
| `codex`, `rite`, `glossary` list, show, new, edit and delete | `memory.cli` |
| `codex`, `rite`, `glossary` search | `cap:memory-search` |
| `codex map`, `codex chaos`, `impacts` | `cap:memory-graph` |
| `index search`, `index build` | `cap:memory-index` |
| `health --scope codex`, `rites`, `glossary`, `voice` | `memory` |
| `health --scope bindings` / `index` | `cap:memory-graph` / `cap:memory-index` |
| `health --scope watchers` | `watchers` |
| `health`, `health --scope doctrines`, `artifacts`, `schemas`, `skills` | `cap:validate` |
| `doctrine`, `artifact`, `watcher` list, show, new, edit and delete | `<feature>.cli` |
| `new`, `claim`, `done`, `block`, `ready`, `needs`, `list`, `show`, `board add` and the other quest commands | `quests` |
| `--help`, `--version`, `--json`, `init` | `cap:validate` (granted always; taught only with `pseudo:cli`) |

## The Assembler

`lore.skills` is the catalogue-aware layer over `lore.blocks`:

| Function | Result |
|---|---|
| `installed_skills(profile)` | The skill ids with at least one surviving `SKILL.md` body block, in catalogue order. |
| `render_skill_file(skill, path, profile)` | The text of one file, or `None` when the skill is not installed or no block of a reference file survives. |
| `skill_files(skill, profile)` | The files the skill writes. |
| `render_document(name, profile)` | `lore-agent` or `getting-started`; `None` when no feature is on. |
| `desired_files(targets, profile)` | Every skill file for every install root. |
| `neighbor_profiles(profile)` | Each profile that differs from the given one in one answer, for health's wrong-profile check. |
| `skill_description(skill)` | The description from the head block, for the skills table. |

The skills table in the instruction text is the one generated region: a marker pair in the `i-skills-table` block that `lore init` replaces with one row per installed skill and every root it landed in. `unresolved_marker` detects a `lore:block` or `lore:skills-table` remnant, which `lore health --scope skills` reports as an error.

## The Line Caps and the Lint

`lore.blocklint.lint()` checks the shipped tree against ten rules without reading any prose (`decisions-006-no-seed-content-tests`):

| Code | Rule |
|---|---|
| L1 | Every block parses, matches `lore://schemas/block`, sits in the directory of its feature, and uses known capabilities and valid conditions. |
| L2 | The `commands` a block declares equal the commands in its body, have rows in the grant table, and are implied by the block's own tags. |
| L3 | Every block is listed by the catalogue, every listed block exists, no list repeats a block, every head names its skill and carries a description. |
| L4 | The instruction document cannot exceed its cap, a skill file cannot exceed 100 lines, and an `oversize` entry names a real file with a bound above 100. |
| L5 | A block that mentions a skill survives only where that skill is installed. |
| L6 | No marker appears in a body except the skills-table pair. |
| L7 | No template syntax and no command outside a code span. |
| L8 | `core` and `route` are used only where they mean something, and a skill block is never `core`. |
| L9 | A block never excludes what it requires. |
| L10 | Every mentioned `skill/path` file exists in the catalogue. |

The bound for a file is conservative: it takes the largest total over every combination of the gate variables the file's blocks use. `lint_rendered(profile)` re-checks the rendered output of a profile for the line caps and for leaked commands. `scripts/check_blocks.py` runs the lint as a release preflight and in CI, and `tests/unit/test_blocks_shipped.py` runs both over the fixture profiles and 300 random ones.

## Authoring Rules

- One concept per block. A harness variant and a CLI variant are two blocks gated on the route, not one block with two halves.
- Every command sits in a code span and appears in `commands`.
- A reference to a Lore-shipped design document is a pair of blocks: one naming `lore artifact show <id>` for `artifacts.read=cli`, one naming the path under `.lore/artifacts/default/` for any other Artifacts route. Both require the features and capabilities that gate the seeded file.
- A block that mentions a skill declares it in `mentions`.
- Text states what is true now. No block narrates a change.

## Testing

`decisions-006-no-seed-content-tests` forbids asserting the prose of anything under `src/lore/defaults/`. The renderer is proved against test-authored fixture blocks, and the shipped tree is proved structurally: every catalogue block exists, every skill has a head naming itself, every `retired` entry names a live successor, and the lint and rendered properties hold for every profile.
