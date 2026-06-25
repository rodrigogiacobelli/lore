---
id: custom-codex-schemas-business-map
title: Context Map — Custom Codex Frontmatter Schemas (business lens)
summary: Business-lens context map for the Custom Codex Frontmatter Schemas feature — the codex/glossary entities, the codex create/edit and health-audit workflows, the link-direction and config-seeding ADRs, and the standards a project-local overlay must respect. Lens carried in the body because the codex schema rejects a raw lens frontmatter key (the exact gap this feature closes).
type: context-map
---

# Context Map — Custom Codex Frontmatter Schemas (business lens)

**Author:** Scout (business lens)
**Date:** 2026-06-18
**Feature:** _Let a project declare add-only custom frontmatter fields for its codex docs via overlay files in `.lore/custom-schemas/`, validated by `lore health` and `lore codex` create/edit._
**Lens:** _business_

> Frontmatter note: the codex schema is `additionalProperties: false` and does not (yet) accept a `lens` key, so this map carries its lens in the title and the `**Lens:**` line rather than in frontmatter. Adding a `lens:` frontmatter key is exactly the maintainer pain this feature removes. See Scout Notes.

---

## Relevant Documents

| ID | Title | Why relevant |
|----|-------|-------------|
| `custom-codex-schemas-prd` | Custom Codex Frontmatter Schemas — PRD | The feature spec itself — the three locked design decisions (strict declared-only, add-only, per-kind overlays), the two user workflows (maintainer adds `owner`; agent/CI runs the merged audit), and FR-1..FR-13. Read first. |
| `conceptual-entities-glossary` | Glossary | The Glossary is the other user-tracked YAML under `.lore/codex/` that `lore health` audits with a schema. Closest precedent for a project-authored file that participates in validation; useful contrast — overlays live in `.lore/custom-schemas/`, not the codex tree, and are add-only. |
| `codex` | Codex | The root explainer for what a codex doc is and how authors read/write it. Establishes the maintainer persona whose docs carry the custom keys (`owner`, `reviewed`, `jira`) this feature legitimizes. |
| `conceptual-workflows-codex` | Codex Commands — lore codex | The maintainer-facing surface (`list`, `search`, `show`, `map`, `chaos`). Note codex has NO CLI write path here — create/edit (where overlay validation must also bite, per FR-9) is a separate workflow surfaced by the codex create/edit story, not these read commands. |
| `conceptual-workflows-health` | lore health Behaviour | The audit workflow that today emits `Unknown property 'owner'` and after this feature must pass on declared keys while still flagging typos. Defines the `schemas` scope, the always-error severity of schema violations, the `scan_failed` issue type a malformed overlay must surface as (FR-10), and the fail-loud / never-false-green policy. Core user-success surface. |
| `tech-cli-entity-crud-matrix` | CLI Entity CRUD Matrix | Confirms the product boundary: codex has no CLI write path and the feature adds NO new `lore schema` command group (Out of Scope). Custom-schema discovery is convention + docs + the scaffolding skill, consistent with this matrix's "Codex has no CLI write path" row. |
| `conceptual-entities-artifact` | Artifact | The scaffolding skill (FR-11..FR-13) drafts an overlay file; artifacts/skills are how Lore packages reusable authoring help. Frames what "a skill writes a valid file under `.lore/...` and validates it" looks like as a product capability. |
| `decisions-013-toml-for-config-yaml-for-glossary` | ADR-013: TOML for config, YAML for glossary; lore init seeds glossary under .lore/codex/ | Sets the precedent that user-authored project content is YAML and that `lore init` seeds user-tracked vocabulary directly (not under `default/`). Overlays are YAML project files too; this ADR is the closest product decision on where user-authored config-vs-content lives and why it is not under `default/`. |
| `decisions-014-link-direction` | Link direction — the codex is the hub, links live on the stable side | Establishes which frontmatter fields are authoritative core edges (`related`, `binds`, `rites`). An overlay must NOT redefine or weaken these (FR-7 add-only rule). Tells the product why core fields like `id`/`title`/`summary`/`related`/`binds`/`rites` are off-limits to overlays. |
| `decisions-011-api-parity-with-cli` | ADR-011: Python API must be behaviourally equivalent to the CLI | The parity guardrail the PRD calls out (Compatibility/Parity NFR): the merged-validator behaviour must be reachable from both `lore health`/`lore codex` (CLI) and `lore.api`/`lore.schemas` (Python, e.g. Realm). A product requirement, not just a technical one. |

> Add one row per relevant document. The "why relevant" column must be specific enough that a downstream agent knows exactly why to read it.

---

## How to Use This Map

Every agent that receives this map should:
1. Run `lore codex show <id1> <id2> ...` with all IDs in the table above
2. Read every document listed before starting their mission
3. Do not explore the codex independently — this map is your entry point

---

## Scout Notes

- **The `lens` frontmatter key cannot be written today.** The codex schema is `additionalProperties: false` with allowed keys `id, title, summary, type, related, binds, rites`. The mission asked for `lens: business` in frontmatter, but `lore health` rejects it as `Unknown property 'lens'` (verified directly). Since acceptance requires a clean `lore health`, both maps carry their lens in the title + `**Lens:**` body line and set `type: context-map`. This is itself a live demonstration of the maintainer pain the feature removes — once an overlay declaring `lens` (or `type`-like context-map fields) exists, this frontmatter would validate.
- **`type` is already an accepted optional codex field** (free-form label, not a schema selector). So `type: context-map` is schema-valid today and needs no overlay.
- **Glossary check:** the only glossary term is `Constable`; no collision with feature vocabulary (overlay, custom-schema, merge, additionalProperties). The PRD's terms are safe to use as-is.
- **Product naming gap:** "overlay", "custom-schema", and "add-only merge" are new product nouns introduced by this PRD and not yet in the glossary or codex. After this ships, a glossary entry and/or a `conceptual-` doc for the overlay concept may be worth adding so future agents discover it via search (today `lore codex search "customization overlay"` returns nothing).
