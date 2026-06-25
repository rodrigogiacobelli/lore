---
id: decisions-018-overlays-are-path-discovered-config
title: 'ADR-018: Custom-schema overlays are path-discovered project config, not ID-addressable
  entities'
summary: ADR classing a .lore/custom-schemas/<kind>.yaml overlay as a user-owned,
  path-discovered config file (the .lore/config.toml / .lore/codex/glossary.yaml precedent)
  rather than an ID-addressable Lore entity. This places overlays outside the ADR-006
  by-ID-not-by-path rule and explains why no lore schema show retrieval path exists.
related:
- decisions-006-id-references
- decisions-013-toml-for-config-yaml-for-glossary
- tech-arch-schemas
---

# ADR-018: Custom-schema overlays are path-discovered project config, not ID-addressable entities

## Context

The Custom Codex Frontmatter Schemas feature (PRD `custom-codex-schemas-prd`,
Tech Spec `custom-codex-schemas-tech-spec`) introduces a new on-disk surface: a
project-local **overlay** file at `.lore/custom-schemas/<kind>.yaml` that adds
custom frontmatter properties onto a packaged codex schema. The PRD explicitly
keeps a `lore schema ...` CLI command group **out of scope** — overlays are
discovered by filename convention, never created or read through a `lore <x>
show <id>` command.

This creates a classification question against **ADR-006**
(`decisions-006-id-references`): "Agents reference entities by ID, never by file
path." ADR-006 enumerates the entity categories it governs — Doctrines, Knights,
Codex documents, Artifacts — each of which is a *retrievable Lore-managed entity*
surfaced by a dedicated `lore <x> show <id>` command. A reader could either:

1. mistake an overlay for an ADR-006 entity and conclude the feature **violates**
   ADR-006 (it is reached by path, not by ID), or
2. "fix" the perceived violation by adding a `lore schema show` retrieval path —
   which the PRD deliberately rejected.

No existing ADR classes a "schema overlay" as a config-class file addressed by
path. The Tech Spec's Change Log line "Honors ... ADR-006" is correct only under
the reading this ADR now records. The ADR & Standards Audit on the Tech Spec
flagged this as an unrecorded decision.

## Decision

A custom-schema overlay is **user-owned project configuration addressed by its
canonical path**, not a Lore-managed entity addressed by ID. It is therefore
**outside the scope of ADR-006**, exactly as `.lore/config.toml` and
`.lore/codex/glossary.yaml` are.

Concretely:

- An overlay lives at the fixed path `.lore/custom-schemas/<kind>.yaml`, where
  `<kind>` matches a packaged schema kind (`codex-frontmatter`,
  `codex-source-frontmatter` for v1). It is discovered by filename, zero config.
- An overlay has **no** `lore <x> show <id>` retrieval path and is **not** a node
  in the codex graph (no `id`/`title`/`summary` frontmatter, no `related`/`binds`
  edges). `lore impacts`, `lore codex map`, and the codex link-integrity checks
  never see it.
- ADR-006's "by ID, never by path" rule does **not** apply to overlays. They are
  the same class of object as `.lore/config.toml` (TOML project config) and
  `.lore/codex/glossary.yaml` (YAML user vocabulary) under ADR-013
  (`decisions-013-toml-for-config-yaml-for-glossary`): files a team owns and
  edits, referenced by their canonical path.
- Authoring help is delivered by the `new-custom-schema` scaffolding skill, not
  by a CLI entity command. The skill writes the file at the canonical path.

## Rationale

**ADR-006 governs retrievable entities, and an overlay is not one.** ADR-006's
whole mechanism — "the only way to retrieve an artifact is to know its ID" —
presupposes a `lore <x> show <id>` surface. An overlay has none by design. It is
not retrieved at all; it is *resolved* by the validator layer from a known path,
the same way `load_config` reads `.lore/config.toml`. There is nothing for
ADR-006 to govern.

**The config precedent already exists.** ADR-013 established that user-owned
project files (`.lore/config.toml`, `.lore/codex/glossary.yaml`) live at fixed
canonical paths and are read by path, not seeded under `default/` and not
addressed by ID. Overlays are the third member of that class. Recording this
keeps the boundary consistent instead of inventing a new rule per file.

**It forecloses a rejected design.** Without this ADR, a future author trying to
"comply with ADR-006" could add a `lore schema show <kind>` command. The PRD
rejected a `lore schema` group outright (discovery is convention + skill + docs).
Pinning the classification protects that decision.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Treat overlays as ADR-006 entities and add `lore schema show`** | Directly contradicts the PRD's Out-of-Scope "no `lore schema ...` group." Adds a retrieval surface for a file that needs none; overlays are resolved by the validator, never shown to an agent by ID. |
| **Amend ADR-006 to list overlays as an exception** | ADR-006 is about entities that *have* a `show <id>` command. Overlays do not; they are not exceptions to the rule, they are simply a different class (config), already covered by the ADR-013 precedent. An exception clause would muddy ADR-006's clean entity scope. |
| **Leave the classification implicit** | The Tech Spec already had to assert "Honors ADR-006" without a governing record. Leaving it implicit invites the two failure modes above (false violation reading, or a rejected `lore schema show` addition). |
| **Make overlays codex docs (give them `id`/`related`)** | Overlays are JSON-Schema fragments, not documentation. They carry no narrative, link to nothing, and must not appear in `lore codex list` / `map` / `impacts`. Forcing codex frontmatter onto them is a category error. |

## Consequences

**Easier:**
- The ADR-006 boundary is now explicit: by-ID for entities, by-path for the three
  user-owned config files (`config.toml`, `glossary.yaml`, `custom-schemas/*.yaml`).
- A future author cannot read the feature as an ADR-006 violation, nor "fix" it
  with a CLI retrieval path the PRD rejected.

**Harder:**
- One more file class an agent must recognise as path-addressed rather than
  ID-addressed. Mitigated by grouping it with the existing config precedent.

## Constraints Imposed

1. **No `lore schema` command group.** Overlays are never given a `show <id>`
   retrieval path. Discovery stays convention + the `new-custom-schema` skill +
   docs.
2. **Overlays are not codex graph nodes.** They carry no `id`/`related`/`binds`;
   `lore codex map`, `lore impacts`, and codex link-integrity checks ignore them.
3. **Overlays are path-addressed.** They are referenced as
   `.lore/custom-schemas/<kind>.yaml`, the same posture as `.lore/config.toml`
   and `.lore/codex/glossary.yaml`. ADR-006's by-ID rule does not apply.
