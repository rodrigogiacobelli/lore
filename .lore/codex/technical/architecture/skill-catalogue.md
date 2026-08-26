---
id: tech-arch-skill-catalogue
title: Skill Catalogue and Access-Mode Rendering
summary: The format of `skills-catalogue.yaml` — families, per-skill entries, reference
  files, and the append-only retirement ledger that explains where a removed skill went —
  plus the access-mode block renderer that produces one installed skill from one authored
  SKILL.md, and the authoring convention that keeps a command in both modes.
binds:
- src/lore/skills.py
- src/lore/defaults/skills-catalogue.yaml
- src/lore/schemas/skill-catalogue.yaml
- src/lore/defaults/skills/**
- tests/unit/test_skills.py
related:
- conceptual-entities-skill
- conceptual-workflows-lore-init
- conceptual-workflows-init-reconcile
- conceptual-workflows-init-interactive
- tech-arch-agents-md
- tech-arch-install-manifest
- decisions-001-dumb-infrastructure
- decisions-006-id-references
- decisions-006-no-seed-content-tests
- standards-dry
---

# Skill Catalogue and Access-Mode Rendering

Ten skills ship with Lore. The catalogue records their structure; each skill's own `SKILL.md` carries its content. `conceptual-entities-skill` describes what a skill is and where it installs.

## The Catalogue

`src/lore/defaults/skills-catalogue.yaml` sits at the `defaults/` root, deliberately **not** inside `skills/`, so the skills tree stays exactly one directory per skill and the renderer never has to exclude a file.

```yaml
version: 2

families:
  memory:    Project memory — codex, rites and glossary, consulted together
  machinery: Lore's own configuration entities
  workflow:  Multi-step processes over quests and missions

skills:
  - id: store-memory
    family: memory
    references: [codex-doc.md, rite.md, source.md]
  - id: retrieve-memory
    family: memory
  - id: update-doctrine
    family: machinery
  - id: update-knight
    family: machinery
  - id: update-watcher
    family: machinery
  - id: update-artifact
    family: machinery
  - id: update-custom-schema
    family: machinery
  - id: start-quest
    family: workflow
  - id: inquest
    family: workflow
  - id: sync-codex-guide
    family: workflow

retired:
  new-doctrine:       {into: update-doctrine,      reason: renamed}
  new-knight:         {into: update-knight,        reason: renamed}
  new-watcher:        {into: update-watcher,       reason: renamed}
  new-artifact:       {into: update-artifact,      reason: renamed}
  new-custom-schema:  {into: update-custom-schema, reason: renamed}
  lore-update:        {into: sync-codex-guide,     reason: "renamed; agent-file half replaced by the CLAUDE.md marked block"}
  new-rite:           {into: store-memory,         reason: merged into store-memory}
  update-codex:       {into: store-memory,         reason: merged into store-memory}
  ingest-source:      {into: store-memory,         reason: merged into store-memory}
  refresh-source:     {into: store-memory,         reason: merged into store-memory}
  explore-codex:      {into: retrieve-memory,      reason: merged into retrieve-memory}
  explore-rite:       {into: retrieve-memory,      reason: merged into retrieve-memory}
  explore-codex-rite: {into: retrieve-memory,      reason: merged into retrieve-memory}
```

| Field | Meaning |
|---|---|
| `version` | The catalogue version, recorded in each install manifest. |
| `families` | The three selectable groups, each with the one-line description the prompt shows. |
| `skills[].id` | The skill's directory name under `defaults/skills/` and at its install destination. |
| `skills[].family` | Which family selection installs it. |
| `skills[].references` | File names under that skill's `references/` directory. Absent means the skill is a lone `SKILL.md`. |
| `retired` | The ledger: every id Lore has shipped and no longer ships, the id that replaced it, and the reason. |

A skill's human-readable description is authored once, in its own `SKILL.md` frontmatter, and is not repeated here. The catalogue carries structure — id, family, reference files, retirement — and nothing an agent reads.

`retired` rows are **append-only**. A project hopping several releases needs every intermediate rename explained, and `reason` is quoted verbatim in the removal report.

The catalogue validates against `lore://schemas/skill-catalogue` through `load_schema`, never through the overlay resolver. An unparseable or schema-invalid catalogue raises `RuntimeError` naming the packaged file — a build defect, never a user error.

## Family Resolution

`skills.resolve_families()` turns a selection into the concrete family list. It accepts the three family tokens plus two aggregates: `all` expands to all three, `none` to the empty list. Resolution happens in the business layer, so `plan_init(skill_families=["all"])` and `--skills all` are the same call. Only the expanded list is written to `init-skill-families`; the aggregate tokens are never persisted.

## The Access-Mode Renderer

One authored `SKILL.md` per skill, rendered at install time into the recorded access mode. Text outside any block is unconditional; text inside a block survives only when its mode is selected.

```markdown
<!-- lore:access cli -->
Read documents with `lore codex show <id1> <id2>`. Batch IDs into one call —
`show` deduplicates and appends matched glossary terms.
<!-- lore:access end -->
<!-- lore:access native -->
Read documents directly from `.lore/codex/<layer>/<id>.md` with your own file
tool. Glossary terms are not auto-attached; run `lore glossary search <term>`
when a term is unfamiliar.
<!-- lore:access end -->

Traverse the graph with `lore codex map <id>` and `lore codex chaos <id>`, and
cross the codex↔code boundary with `lore impacts <path>`. No file tool
reproduces a precomputed traversal, so these stay in both modes.
```

`skills.render(text, mode)`:

1. Scans for `<!-- lore:access MODE -->` … `<!-- lore:access end -->` regions.
2. Keeps a region's body verbatim, with its two marker lines stripped, when `MODE` equals the selected mode.
3. Drops the whole region otherwise — markers and a single trailing newline included.
4. Raises `ValueError` naming the file and line on a nested block, an unterminated block, an unknown mode token, or an `end` with no opener.

There is no template engine, no variable, and no expression language: block selection is line-range arithmetic. `decisions-001-dumb-infrastructure` rejected a template engine on the grounds that Lore would have to understand and evaluate templates.

### Why there is no `both` token

A command that belongs in both modes is authored outside any block, which is already unconditional. `lore codex map`, `lore codex chaos` and `lore impacts` are written that way, so they appear in both renderings without a special case. A third token would give two ways to say one thing.

### The same renderer serves the instruction text

`.lore/LORE-AGENT.md` and every agent instruction block go through `skills.render` as well — the instruction text carries its own command layer, and that layer is an access-mode choice like any other. `tech-arch-agents-md` holds the rest of what the instruction template generates.

## Testing the Renderer

`decisions-006-no-seed-content-tests` forbids asserting the prose of anything under `src/lore/defaults/`. The renderer is proved against test-authored fixtures, and the shipped tree is proved structurally: every catalogue id has a directory, every directory has a `SKILL.md` with a `name` in its frontmatter, every declared reference file exists, and every `retired` entry names a live successor.
