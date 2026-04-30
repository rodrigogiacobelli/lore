---
id: decisions-013-toml-for-config-yaml-for-glossary
title: "ADR-013: TOML for project config, YAML for glossary content; lore init seeds glossary directly under .lore/codex/"
summary: >
  ADR establishing two coupled file-format decisions for the Glossary feature:
  `.lore/config.toml` is TOML (project config), `.lore/codex/glossary.yaml`
  is YAML (codex content). Also carves the first-and-only narrow exception to
  the existing rule that `lore init` does not seed `.lore/codex/`: the glossary
  skeleton is written directly to `.lore/codex/glossary.yaml` (not under
  `default/`) because it is user-tracked vocabulary.
related:
  - conceptual-entities-glossary
  - conceptual-workflows-glossary
  - conceptual-workflows-lore-init
  - tech-arch-initialized-project-structure
  - tech-arch-schemas
  - tech-arch-source-layout
  - decisions-001-dumb-infrastructure
  - decisions-006-no-seed-content-tests
---

# ADR-013: TOML for project config, YAML for glossary content; lore init seeds glossary directly under .lore/codex/

**Status:** ACCEPTED

## Context

The Glossary feature (PRD `fi-prd-glossary`, Tech Spec `glossary-tech-spec`) introduces two new on-disk surfaces that did not previously exist in a Lore project:

1. `.lore/codex/glossary.yaml` — a single canonical file holding project-specific term definitions, surfaced via the `lore glossary` CLI and auto-attached to `lore codex show` output.
2. `.lore/config.toml` — the first project-level configuration file Lore has ever needed, designed as a generic key-value surface from day one with `show-glossary-on-codex-commands = true` as its first key.

Three forces drove this ADR:

- **Format consistency vs. ergonomics.** Lore already uses YAML for every codex frontmatter block, every doctrine `.yaml`, every watcher `.yaml`, and every JSON Schema in `src/lore/schemas/`. A naive answer is "use YAML for both." But `.lore/config.toml` is a tiny, flat, human-edited key-value file — exactly the surface TOML was designed for. YAML's whitespace sensitivity and quoting rules add cost where TOML adds none.
- **`lore init` and `.lore/codex/`.** Both `tech-arch-initialized-project-structure` and `conceptual-workflows-lore-init` previously stated as a hard property that `lore init` does NOT seed `.lore/codex/`. PRD FR-27 requires init to seed `.lore/codex/glossary.yaml`. The contract has to be amended explicitly — silent change is not acceptable.
- **No `default/` clobber.** Every other entity directory (`doctrines/`, `knights/`, `artifacts/`, `watchers/`) has a `default/` subtree that is gitignored and overwritten on every re-init. The Glossary cannot live under `default/` because its content is user-owned project vocabulary; an overwrite would clobber maintainer edits on every re-init.

Key forces:

- **Force 1 — Human-edit ergonomics for config.** TOML's flat `key = value` shape is the lowest-friction format for the kind of one-key file `.lore/config.toml` is on day one and will remain after any plausible expansion. No nesting, no quoting traps for booleans, no whitespace pitfalls.
- **Force 2 — Codex content stays YAML.** Glossary items contain string lists (`aliases`, `do_not_use`) and multi-line definitions. YAML's flow `[a, b]` and folded `>` scalars are ergonomic; agents and humans already read YAML in every other codex file.
- **Force 3 — User-tracked vs. seeded files.** `.lore/codex/glossary.yaml` and `.lore/config.toml` are both user-tracked. Re-init must NOT clobber them. Every other init-seeded file lives under a `default/` subtree precisely so re-init can overwrite it without touching user content; these two files break that pattern by design.

## Decision

Three coupled rulings, all in scope of one ADR because they only make sense together:

1. **`.lore/config.toml` is TOML.** Loaded with stdlib `tomllib` (Python 3.11+; minimum bumped from 3.10 in the same release). Loader accepts arbitrary additional keys (forward-compatible). The first and only MVP key is the boolean `show-glossary-on-codex-commands`, default `true`.
2. **`.lore/codex/glossary.yaml` is YAML.** Single file; top-level `items:` list of mappings. Schema is `lore://schemas/glossary` (packaged at `src/lore/schemas/glossary.yaml`).
3. **`lore init` seeds glossary and config in place.** `lore init` writes `.lore/codex/glossary.yaml` directly (NOT under `.lore/codex/default/`) and `.lore/config.toml` directly (NOT under `.lore/default/`). Both writes are idempotent — re-init never overwrites either file. This is the first and only narrow carve-out to the rule that `lore init` does not seed `.lore/codex/`. Both `tech-arch-initialized-project-structure` and `conceptual-workflows-lore-init` are updated to reflect this.

## Rationale

- **TOML for config because it is the right tool for short, flat, human-edited key-value files.** Nothing in the foreseeable config surface needs YAML's expressiveness; everything benefits from TOML's simpler grammar.
- **YAML for glossary because it is the right tool for codex content.** Lists, multi-line definitions, and consistency with every other codex file outweigh the marginal cost of two formats in one tree.
- **Direct seeding because `default/` would clobber user content.** The whole point of `default/` is "Lore owns these files; users do not edit them." The glossary and config are the opposite — users own them; Lore must not overwrite them.
- **Idempotent seeding makes re-init safe.** `lore init` checks for existence and skips the write if the file is present. A maintainer's edits survive every subsequent `lore init`.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **YAML for both config and glossary** | Adds zero value over TOML for the flat config surface; YAML's whitespace/quoting cost is paid for no gain. Forces every config consumer to load YAML where stdlib `tomllib` already exists. |
| **TOML for both config and glossary** | Glossary items have string lists and multi-line definitions; TOML's array syntax is workable but uglier than YAML, and we lose consistency with the codex YAML conventions all agents and maintainers already know. |
| **Glossary under `.lore/codex/default/glossary.yaml`** | `default/` is gitignored and overwritten on every re-init by design. Maintainer edits to project vocabulary would be silently destroyed. Direct contradiction with the file's purpose as user-owned content. |
| **Config under `.lore/default/config.toml`** | Same clobber problem as glossary-under-default. Project config is user-owned; defaults belong in code (`DEFAULT_CONFIG`), not in a gitignored seed file. |
| **Vendor `tomli` to keep Python 3.10 support** | Adds a dependency and an `import tomllib` / `import tomli as tomllib` shim for the entire life of the codebase. Lore is a single-machine dev tool installed via `uv tool` / `pipx`; bumping to 3.11 (released October 2022) is cheap. |
| **Hold the line on "init never touches `.lore/codex/`"** | Only viable if the glossary lives outside `.lore/codex/`. PRD scopes the glossary as codex content (an inline-vocabulary surface alongside conceptual entity docs). Moving it out of `.lore/codex/` would harm discoverability and contradict the codex's role as the project's living documentation. |

## Consequences

**Easier:**
- Editing `.lore/config.toml` is one-line k=v with no nesting cost.
- Glossary stays in the codex tree, where agents already look for project documentation.
- Re-init is safe — `lore init` becomes a no-op for both files once present.
- Single normaliser, single schema kind, single CLI surface for the glossary.

**Harder:**
- Two file formats in the codex tree (`.md` + `.yaml`). Tooling and tests must understand both.
- Python 3.11 minimum eliminates 3.10 users — small but real cost.
- The `lore init` contract is now "does not seed `.lore/codex/`, EXCEPT `glossary.yaml`." The exception must be documented in every doc that previously stated the absolute rule (`tech-arch-initialized-project-structure`, `conceptual-workflows-lore-init`).

## Constraints Imposed

1. **Config is TOML, glossary is YAML.** Any new project-level config key uses TOML at `.lore/config.toml`. Any new codex content uses YAML (frontmatter or full file). Mixing the two is a violation.
2. **`lore init` seeds glossary and config idempotently.** Re-init MUST NOT overwrite either file when present. Implementation: `if not path.exists(): write(...)`.
3. **No `default/` placement for glossary or config.** Both files live at their canonical paths only. There is no `.lore/codex/default/glossary.yaml` and no `.lore/default/config.toml`.
4. **Python 3.11 minimum.** `pyproject.toml`'s `requires-python` is `>=3.11`. `tomllib` is the only TOML loader; no `tomli` fallback.
5. **Schema parity.** `glossary.yaml` is validated by `lore://schemas/glossary` at create time (not applicable — no CLI write path) and at audit time (`lore health --scope schemas` and `lore health --scope glossary`).
6. **Init seeded files must be schema-green on a fresh project.** A freshly-initialised project must pass `lore health --scope schemas` (and `lore health --scope glossary`) — both the glossary skeleton (`items: []`) and an absent config must be green.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-04-29 | accepted | Initial decision. Captured in the same release that adds `lore glossary`, `.lore/config.toml`, and the `--skip-glossary` flag on `lore codex show`. |
