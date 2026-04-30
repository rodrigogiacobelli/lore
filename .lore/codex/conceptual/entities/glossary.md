---
id: conceptual-entities-glossary
title: Glossary
summary: >
  What the Glossary is — a single canonical YAML file at `.lore/codex/glossary.yaml`
  that holds short, project-specific term definitions keyed by `keyword`. The
  Glossary is read-only via the `lore glossary` CLI, auto-surfaces matched terms
  on `lore codex show`, and is audited (schema, intra-file collisions, and
  cross-codex deprecated-term scan) by `lore health`.
related:
  - conceptual-entities-artifact
  - conceptual-entities-knight
  - conceptual-entities-mission
  - conceptual-entities-quest
  - conceptual-entities-doctrine
  - conceptual-entities-watcher
  - conceptual-workflows-glossary
  - conceptual-workflows-codex
  - conceptual-workflows-health
  - conceptual-workflows-lore-init
  - tech-cli-commands
  - tech-arch-source-layout
  - tech-arch-schemas
  - decisions-013-toml-for-config-yaml-for-glossary
---

# Glossary

The Glossary is a project's canonical vocabulary record — a single YAML file at `.lore/codex/glossary.yaml` whose `items:` list holds short definitions keyed by `keyword`. Where Codex documents (lore codex show codex) carry full conceptual or technical content, the Glossary holds inline term definitions that are too small to deserve their own document but too important to leave undefined. The Glossary is the project's living vocabulary surface and the substrate the system uses to disambiguate terms inside other Codex documents.

The Glossary is a first-class file-based entity alongside Artifacts (lore codex show conceptual-entities-artifact), Knights (lore codex show conceptual-entities-knight), Doctrines (lore codex show conceptual-entities-doctrine), and Watchers (lore codex show conceptual-entities-watcher). Like Artifacts, the CLI is read-only — `lore glossary list/search/show` — and maintainers edit `.lore/codex/glossary.yaml` directly on disk.

## Properties

Every glossary item is a mapping with up to four keys:

- **`keyword`** — Required. The canonical surface form of the term. Lookup is case-insensitive (via `str.casefold()`); display preserves the original casing. The `keyword` is the natural key — there is no `id` field.
- **`definition`** — Required. A one-to-two sentence explanation of the term. Multi-line YAML scalars (folded `>` or block `|`) are allowed; the renderer collapses internal whitespace when rendering inline.
- **`aliases`** — Optional list of additional surface forms that should match the same item. Aliases participate in matching but are NOT accepted as `lore glossary show` lookup keys.
- **`do_not_use`** — Optional list of deprecated forms. Surfaces ONLY in `lore health` — never in `lore codex show` auto-surface — and emits one `glossary_deprecated_term` warning per occurrence per Codex document.

The glossary file's shape is enforced by the JSON Schema at `lore://schemas/glossary` (packaged at `src/lore/schemas/glossary.yaml`). Schema rules: `keyword` and `definition` are required; `keyword`, `aliases` items, and `do_not_use` items are 1–80 single-line characters; `definition` is 1–1000 characters; `aliases` and `do_not_use` are unique within their list. A multi-line keyword or alias is rejected at the schema layer because the matcher is undefined for newline-bearing strings.

## What Belongs Here

The Glossary holds **small, project-specific terms** that are too tiny to deserve their own Codex document but important enough that an agent reading another document needs the inline definition. Most candidate terms do NOT belong here.

A term is glossary-worthy only when ALL three are true:

1. **Project-specific.** Generic IT vocabulary (ADR, soft-delete, E2E, mock, fixture, idempotent, RBAC, …) does not qualify — assume the reader knows IT.
2. **Not an entity.** Entities (Quest, Mission, Knight, Doctrine, Codex, Artifact, Watcher, Glossary itself, plus system-level entities Camelot, Lore, Realm, Citadel) live in their own `conceptual-entities-<name>` doc. Link to that doc instead.
3. **Not a named workflow, command, or feature.** Anything with a `conceptual-workflows-<name>` doc, a CLI command, or a feature surface (auto-surface, ready queue, board, oracle, health, codex show, …) is already documented there. Link to the workflow doc instead.

If any answer is NO, the term goes in an entity doc, a workflow doc, an ADR, a standards doc, or nowhere — never the Glossary.

The full checklist with worked examples and the "where to put it instead" table is the design-document artifact `glossary-design`. Retrieve it before every glossary edit:

```
lore artifact show glossary-design
```

The `Constable` entry is the canonical worked example: a small project-invented label for a Mission type the orchestrator handles inline. Not an entity, not a workflow, not generic IT — passes all three gates.

## Lifecycle

```
absent ──→ seeded skeleton ──→ user-edited
```

| State | Description | Transition |
|-------|-------------|------------|
| `absent` | No `.lore/codex/glossary.yaml` exists. `lore glossary list` prints `No glossary defined.` and exits 0. `lore codex show` skips auto-surface silently. | `lore init` seeds the skeleton if absent. |
| `seeded skeleton` | File exists with header comment + `items: []`. Schema-valid. Auto-surface produces no `## Glossary` block (no items match). | Maintainer adds items by editing the file. |
| `user-edited` | File contains one or more items. Auto-surface and `lore health` deprecated-term scan operate over the items. | Maintainer adds, edits, or removes items by editing the file. `lore init` is idempotent — a re-init does NOT overwrite a user-edited file. |

The Glossary has no soft-delete. Renames or removals are not migrations — dangling references in other Codex documents simply stop matching, with no error.

## How It Is Surfaced

Three independent surfaces consume the Glossary:

1. **`lore glossary {list,search,show}`** — direct read access. See conceptual-workflows-glossary (lore codex show conceptual-workflows-glossary).
2. **`lore codex show <id>` auto-surface** — when `show-glossary-on-codex-commands = true` in `.lore/config.toml` (the default) and `--skip-glossary` is not passed, the system tokenises every returned Codex document body, matches tokens against keyword and alias token-tuples, and appends a trailing `## Glossary` block with each matched item. The match algorithm is the single shared normaliser described in conceptual-workflows-glossary. `do_not_use` matches are NOT included in the auto-surface block.
3. **`lore health`** — schema validates `glossary.yaml`, runs intra-file collision checks (duplicate keyword, alias-keyword collision, `do_not_use` collision), and scans every Codex document body for `do_not_use` term hits. See conceptual-workflows-health (lore codex show conceptual-workflows-health).

All three surfaces share one normaliser (`lore.glossary._normalise_tokens` and `_build_lookup`). Auto-surface and the health scan are two presentation policies over the same matcher — DRY by construction.

## Edge Cases

- **Missing file:** `lore glossary list` prints `No glossary defined.` and exits 0. `lore codex show` silently skips auto-surface. `lore health` reports the file as absent (no error — empty glossary is valid).
- **Malformed YAML or schema violation:** `lore glossary list/search/show` and `lore health` fail loud (stderr error, non-zero exit). `lore codex show` fails soft — emits one stderr line `glossary unavailable: <reason>`, omits the `## Glossary` block, and exits 0. Reliability requirement: a broken glossary MUST NOT break a `lore codex show`.
- **Aliases are not lookup keys:** `lore glossary show <alias>` returns `Error: glossary keyword "<alias>" not found.` This is by design — aliases are matcher inputs, not retrieval keys. The canonical keyword is the only retrieval surface.
- **Tokeniser scope:** the matcher splits on `[^\w]+` with `re.UNICODE` and lowercases via `str.casefold()`. Multi-word keywords match as contiguous token runs. `missionary` does NOT match `mission`. Apostrophe-bearing tokens (`source's`) split into `source` and `s`, allowing multi-word matches like `Codex Source` to fire on `the codex source's structure`.
- **Carve-out for `lore init`:** the Glossary is the only file `lore init` seeds under `.lore/codex/`. The skeleton is written directly to `.lore/codex/glossary.yaml` (NOT under `.lore/codex/default/`), because the file is user-tracked vocabulary and a `default/` placement would be gitignored and overwritten on every re-init. See decisions-013-toml-for-config-yaml-for-glossary (lore codex show decisions-013-toml-for-config-yaml-for-glossary).

## Related

- conceptual-workflows-glossary (lore codex show conceptual-workflows-glossary) — the read-side workflows (`list`, `search`, `show`, auto-surface, `--skip-glossary`).
- conceptual-workflows-codex (lore codex show conceptual-workflows-codex) — `lore codex show` is the principal auto-surface entry point.
- conceptual-workflows-health (lore codex show conceptual-workflows-health) — schema, collision, and deprecated-term scanning.
- conceptual-workflows-lore-init (lore codex show conceptual-workflows-lore-init) — how the skeleton is seeded.
- decisions-013-toml-for-config-yaml-for-glossary (lore codex show decisions-013-toml-for-config-yaml-for-glossary) — file-format split (TOML for config, YAML for glossary) and the init carve-out.
- tech-arch-schemas (lore codex show tech-arch-schemas) — how the `glossary` schema kind plugs into the schemas module.
