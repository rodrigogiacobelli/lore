---
id: remove-type-field-business-map
type: context-map
lens: business
title: Context Map — remove-type-field (business)
summary: Business-lens context map for the remove-type-field feature — removing the redundant type: frontmatter field from Lore Python source, tests, and default artifact templates.
---

# Context Map — remove-type-field (business)

**Author:** Scout (business lens)
**Date:** 2026-03-27
**Feature:** _Remove the redundant `type:` frontmatter field from the Lore Python codebase (frontmatter.py, codex.py, artifact.py, models.py, cli.py), src/lore/defaults/ artifact templates, and all associated tests_
**Lens:** _business_

---

## Relevant Documents

| ID | Title | Why relevant |
|----|-------|-------------|
| `conceptual-entities-artifact` | Artifact | Defines the Artifact entity and its four required frontmatter fields — including `type:`. This is the primary user-facing entity contract changing: `type` is currently required in artifact frontmatter and exposed as a column in `lore artifact list`. The feature touches whether `type` remains required for artifacts or is dropped/made optional. |
| `conceptual-workflows-artifact-list` | lore artifact list Behaviour | Documents the current five-column table output (ID, TYPE, GROUP, TITLE, SUMMARY) for `lore artifact list`. This feature may change the required frontmatter validation rules and potentially the display columns — directly affecting what agents see when they discover artifacts. |
| `conceptual-workflows-codex` | Codex Commands — lore codex | Documents the current `lore codex list` behaviour, including references to `type` in codex document frontmatter preconditions. The feature removes `type` from codex document contracts, affecting how `lore codex list` validates and displays documents. |
| `tech-arch-frontmatter` | Frontmatter Module Internals | The central module being changed. Defines `required_fields` defaults and the `exclude_type` parameter. Artifact callers currently pass `required_fields=("id","title","type","summary")`; the feature changes what is required for codex documents vs. artifacts and may eliminate `exclude_type` as a parameter. This is the authoritative source of the current contract for both agent and Realm consumers. |
| `tech-arch-source-layout` | Source Layout | Full inventory of all source modules and the shipped defaults tree under `src/lore/defaults/`. Covers the artifact templates in `defaults/artifacts/transient/` and `defaults/artifacts/codex/` — these shipped templates will need their `type:` frontmatter field removed as part of the feature. Documents which modules are touched (frontmatter.py, codex.py, artifact.py, models.py, cli.py). |
| `tech-arch-initialized-project-structure` | Initialized Project Structure | Documents the `.lore/` directory layout seeded by `lore init`, including the `artifacts/default/` subdirectory. Agents and project maintainers who add custom artifact files follow the structure shown here — if `type:` is removed as a required field for codex documents, the guidance on what frontmatter is required changes for both shipped and user-created files. |
| `conceptual-workflows-lore-init` | lore init Behaviour | Documents the step that seeds default artifact templates on `lore init`. The shipped templates in `src/lore/defaults/artifacts/` are overwritten on re-init — removing `type:` from these templates means existing projects that re-init will get templates without `type:`, affecting agents that use them as scaffolds. |
| `standards-public-api-stability` | Public API Stability | Governs the semver policy for changes to `lore.models.__all__`. The `Artifact` dataclass currently exposes a `type` field as part of the public API. If `type` is removed from `Artifact` or made optional, this is a breaking API change requiring a major bump or explicit breaking-change notice in CHANGELOG.md — directly affecting Realm as a consumer. |
| `standards-dry` | DRY — Don't Repeat Yourself | Establishes `frontmatter.py` as the single authoritative home for YAML frontmatter parsing logic. Relevant because the feature must be applied consistently in one place (frontmatter.py) rather than in each caller — validates the implementation approach. |
| `tech-arch-validators` | Validators Module Internals | The validation layer that enforces field contracts. Relevant as context for understanding how required-field rules propagate from frontmatter parsing through the system, and whether any validator currently checks `type`. |

---

## How to Use This Map

Every agent that receives this map should:
1. Run `lore codex show conceptual-entities-artifact conceptual-workflows-artifact-list conceptual-workflows-codex tech-arch-frontmatter tech-arch-source-layout tech-arch-initialized-project-structure conceptual-workflows-lore-init standards-public-api-stability standards-dry tech-arch-validators`
2. Read every document listed before starting their mission
3. Do not explore the codex independently — this map is your entry point

---

## Scout Notes

The core business tension in this feature: the `type:` field is being removed from codex documents (already done in the live codex) but remains in artifact frontmatter. The feature must be surgically precise about what changes where. Downstream agents should pay particular attention to whether `type` is being removed from `Artifact` entirely or only from codex document validation — the current codex suggests artifact files retain `type` while codex documents drop it. The `Artifact` dataclass in models.py and the `type` column in `lore artifact list` output are the most visible user-facing impacts to track.

The `exclude_type` parameter in `frontmatter.py` is a strong signal: it was added specifically to let callers skip files by type — if type is gone from codex documents, this parameter may become dead code, which simplifies the public API surface for both Python and CLI consumers.
