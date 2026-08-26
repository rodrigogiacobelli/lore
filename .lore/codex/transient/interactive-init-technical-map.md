---
id: interactive-init-technical-map
title: Context Map — Interactive lore init and Skill Catalogue Consolidation (technical lens)
summary: Technical-lens context map for the interactive-init feature — the architecture docs, ADRs, standards and reference docs that govern init.py, config.py, api.py, health.py and the defaults tree, plus the pinned contracts (facade purity, CLI parity, click.Choice, no-seed-content tests, the permanent no-JSON-on-init exception) the implementation must not break.
type: context-map
related:
- interactive-init-prd
- conceptual-workflows-lore-init
- conceptual-workflows-health
- conceptual-workflows-schema-migrations
- conceptual-workflows-error-handling
- conceptual-workflows-json-output
- conceptual-workflows-validators
- conceptual-workflows-help
- conceptual-workflows-concurrent-access
- conceptual-workflows-impacts
- conceptual-workflows-codex-map
- conceptual-workflows-codex-chaos
- tech-arch-source-layout
- tech-arch-initialized-project-structure
- tech-arch-agents-md
- tech-arch-api-facade
- tech-arch-project-root-detection
- tech-arch-schemas
- tech-arch-frontmatter
- tech-arch-validators
- tech-overview
- tech-cli-entity-crud-matrix
- technical-test-guidelines
- ref-lore_cli-commands
- ref-lore_api-core
- ref-lore_db-core
- api-guide
- api-reference
- decisions-001-dumb-infrastructure
- decisions-006-no-seed-content-tests
- decisions-008-help-as-teaching-interface
- decisions-010-public-api-stability
- decisions-011-api-parity-with-cli
- decisions-012-multi-value-cli-param-convention
- decisions-013-toml-for-config-yaml-for-glossary
- decisions-014-link-direction
- decisions-017-constrained-flags-use-click-choice
- decisions-018-overlays-are-path-discovered-config
- decisions-019-overlay-scope-stops-at-transient
- decisions-020-codex-voice-is-enforced
- decisions-021-health-reports-are-ephemeral-by-default
- standards-facade
- standards-separation-of-concerns
- standards-single-responsibility
- standards-dependency-inversion
- standards-dry
- standards-public-api-stability
- ops-installation
- ops-publish-pypi
---

# Context Map — Interactive `lore init` and Skill Catalogue Consolidation (technical lens)

**Author:** Scout (technical lens)
**Date:** 2026-08-25
**Feature:** _Interactive prompting in `lore init` (questionary, gated on `stdout.isatty()`), a hash install manifest with legacy-hash fallback for cross-version reconciliation, and the seeded skill catalogue consolidated 15→10 with an injected access-mode command layer._
**Lens:** _technical_
**PRD:** `lore codex show interactive-init-prd`

---

## Relevant Documents

### Docs bound to the files this feature edits

Produced with `lore impacts <path>`. These are the governing docs for each target file — editing the file without updating them leaves the codex wrong.

| ID | Title | Why relevant |
|----|-------|-------------|
| `conceptual-workflows-lore-init` | `lore init` Behaviour | `binds:` `src/lore/init.py`. The authored step sequence (nine steps, plus 7a) that the plan/apply split reorganises. Also the doc that pins two facts the feature changes: the `AGENTS.md` create/marker/backup branch that has zero code references, and the acknowledged-stale `Created lore.db (schema version 1)` message, which the doc points at `init.py` line 54 and which actually lives at `src/lore/init.py:241` (FR-38). Per `technical-test-guidelines` this is also the codex anchor for `tests/e2e/test_lore_init.py`. |
| `tech-arch-initialized-project-structure` | Initialized Project Structure | `binds:` `src/lore/init.py` and `src/lore/paths.py`. Holds the verbatim `.lore/.gitignore` template (FR-5 appends to the ROOT gitignore, a different file) and the `.lore/config.toml` known-key table that FR-36 regenerates from `config.py`. Currently omits `.lore/skills/` and `.lore/docs/`, which `init.py` already writes. |
| `tech-arch-agents-md` | AGENTS.md Specification | `binds:` `src/lore/init.py`. Names `src/lore/defaults/AGENTS.md` as the template source; the file on disk is `src/lore/defaults/docs/LORE-AGENT.md` and no marker logic exists in `src/lore/`. The whole marker/backup spec has to be rewritten around the per-agent registry and the FR-4 conditional prompt. |
| `tech-arch-source-layout` | Source Layout | `binds:` `src/lore/**/*.py` — it governs every file this feature touches. One-line-per-module inventory; any new module (prompting, manifest, agent registry loading, skill rendering) has to be added here, and the entry for `init.py` has to describe the plan/apply split. |
| `tech-arch-api-facade` | API Facade Module | `binds:` `src/lore/api.py`. Pins `api.py` as a pure re-export facade with **zero `def` or `class` statements** and a three-section `__all__`. `plan_init`, `apply_init` and `InitPlan` therefore cannot be defined in `api.py` — they must live in a core module and be re-exported. |
| `conceptual-workflows-health` | `lore health` Behaviour | `binds:` `src/lore/health.py`. The scope vocabulary and the two kinds of scope a new `skills` scope (FR-37) must fit; also the `scan_failed` convention for a checker whose directory is missing, which a skills checker will hit on projects that install skills elsewhere. |
| `decisions-013-toml-for-config-yaml-for-glossary` | ADR-013 | `binds:` `src/lore/config.py` and `src/lore/init.py`. The TOML choice, `tomllib`, forward-compatible extra keys preserved in `Config.extras`, and the seed-in-place / skip-if-present rule. FR-36's header regeneration is a deliberate exception to skip-if-present and needs stating as such. |
| `decisions-021-health-reports-are-ephemeral-by-default` | ADR-021 | `binds:` `src/lore/config.py`, `src/lore/health.py`, `src/lore/init.py`. The worked precedent for adding a root-level config key: default in code, read inside the core function (not the CLI handler), documented in the init header comment. The init answers persisted under FR-10 follow this shape. |

### Public API and parity contracts

| ID | Title | Why relevant |
|----|-------|-------------|
| `decisions-010-public-api-stability` | ADR-010: `lore.api.__all__` is the stable public API contract | Adding `plan_init` / `apply_init` / `InitPlan` is an `__all__` change. Defines what is public and what is internal detail. |
| `standards-public-api-stability` | Public API Stability | The pre-1.0 semver policy: adding names is a minor bump; a positional-arg or return-shape change is a major bump. Directly decides the cost of any `run_init()` signature change — the no-argument call is pinned by `tests/e2e/test_api_parity_init.py`. |
| `decisions-011-api-parity-with-cli` | ADR-011: Python API must be safe and behaviourally equivalent to the CLI | The hardest structural constraint on this feature. No business logic may live only in the CLI layer. Prompting is inherently terminal-only, so every prompt's *effect* must be reachable as a parameter on the core function; the CLI may only gather answers and hand them down. This is the reason the plan/apply split exists. |
| `standards-facade` | Facade | Why `lore.api.__all__` is narrow and everything else is internal. Governs where `InitPlan` is defined versus where it is exported. |
| `ref-lore_api-core` | Lore Python API — core surface | The per-entity public/internal map and the cross-cutting return-shape conventions (dict shapes, typed-model boundaries) a new `InitPlan` return type has to sit alongside. |
| `api-reference` | `lore.api` — Reference | Exhaustive per-symbol reference covering every name in `__all__`. Three new names means three new entries with signature, return shape, exceptions and example. |
| `api-guide` | `lore.api` — Public API guide | The narrative Realm reads. Needs the plan-then-apply flow described for a headless caller. |

### CLI surface conventions

| ID | Title | Why relevant |
|----|-------|-------------|
| `decisions-012-multi-value-cli-param-convention` | ADR-012: Multi-value CLI parameters use space-separated syntax | `--agent claude codex` not `--agent claude --agent codex`. Applies to the agent list and the skill-family list. |
| `decisions-017-constrained-flags-use-click-choice` | ADR-017: Constrained-value CLI flags use `click.Choice` | `--access` and the family/agent tokens are constrained sets, so an out-of-set value must be a Click `BadParameter` → **exit 2**, not an application error → exit 1. Note the tension: FR-11 says the agent registry ships as seeded data, but `click.Choice` needs its set at decorator-evaluation time. Resolving that is a tech-spec decision. |
| `ref-lore_cli-commands` | Lore CLI — commands surface | The cross-cutting conventions doc. Two entries matter most: the exit-code table (0/1/2), and the statement that `--json` is supported on every command **except `lore init` and `lore oracle`**, described there as a *permanent* exception. The PRD defers the init `--json` envelope to the tech spec; that decision collides with this recorded contract. |
| `conceptual-workflows-error-handling` | CLI Error Handling | Exit codes, stderr-vs-stdout routing, and the JSON error format. Governs what happens when the user declines the FR-7 summary or aborts a prompt (Ctrl-C) — an abort that wrote nothing is not obviously an error. |
| `conceptual-workflows-json-output` | JSON Output Mode | The envelope structure and global-vs-local flag position, needed only if the tech spec overturns the init exception above. |
| `conceptual-workflows-help` | Help Output Contract | What enriched `--help` must contain per command group — the obligation every new flag inherits. |
| `decisions-008-help-as-teaching-interface` | ADR-008: `--help` is the primary teaching interface | Establishes that help text teaches rather than describes, and that per-command help is canonical over reference docs. |
| `conceptual-workflows-validators` | Input Validation | The two-layer model — core enforces, CLI translates to UX errors — and how `lore.validators` is wired in. Any new validated input (agent id, family token, access mode) follows this wiring. |
| `tech-arch-validators` | Validators Module Internals | `validators.py` has zero `lore.*` imports and is the safe foundation. Constrains where a new validator may live and what it may import. |
| `tech-cli-entity-crud-matrix` | CLI Entity CRUD Matrix | The entity→command matrix. The PRD explicitly rules out a `lore skill` command group, so skills stay absent from this matrix — worth recording deliberately rather than leaving as an omission. |

### Init mechanics, schema and packaging

| ID | Title | Why relevant |
|----|-------|-------------|
| `tech-arch-project-root-detection` | Project Root Detection | `find_project_root()` walks upward looking for `.lore/`; `lore init` is the documented special case because the directory does not exist yet. Any pre-write reconciliation pass that reads the existing project has to respect that special case. |
| `conceptual-workflows-schema-migrations` | Schema Migrations | Version detection and sequential application. FR-38 replaces the hardcoded `schema version 1` string with the real current version, which this doc and `ref-lore_db-core` define. |
| `ref-lore_db-core` | Lore DB — core cluster | The `lore_meta` table and the schema-version source of truth (`src/lore/defaults/schema.sql`). Needed for the FR-38 fix and for the corrupted-database branch init already has. |
| `tech-arch-schemas` | Schemas Module Internals | The loader, `validate_entity` / `validate_entity_file`, the nine schema kinds, and the merged-schema resolver. Relevant if the `skills` health scope validates skill frontmatter, and it defines the packaged-schema behaviour that governs the transient docs this feature produces. |
| `tech-arch-frontmatter` | Frontmatter Module Internals | `parse_frontmatter_doc` (metadata only) vs `parse_frontmatter_doc_full` (with body), and the `extra_fields` contract. The tool a skills health checker or a skill renderer would use to read a skill's frontmatter. |
| `tech-overview` | Technical Overview | The technology table and the module layering diagram. `questionary` is a NEW hard runtime dependency and this table currently reads "**No extras, no optional dependencies**"; it also still says Python 3.10+ while ADR-013 records the bump to 3.11 for `tomllib`. Both need reconciling. The layering diagram has no `config.py`, `impacts.py`-style entry for whatever new modules land. |
| `conceptual-workflows-concurrent-access` | Concurrent Access Safety | WAL mode, busy timeout, reader/writer isolation. The basis for treating `lore init` as a single-writer operation, cited by the PRD's reliability NFRs. |
| `ops-installation` | Installation | Dev-environment setup and the install/upgrade commands. A new runtime dependency changes what a fresh install pulls. |
| `ops-publish-pypi` | Publish to PyPI | The release runbook and pre-flight checklist. A new hard dependency and a public-API addition both have consequences here (version bump class, changelog). |

### Standards that constrain where the code goes

| ID | Title | Why relevant |
|----|-------|-------------|
| `standards-separation-of-concerns` | Separation of Concerns | `cli.py` formats terminal I/O; business logic lives elsewhere. The questionary prompt loop is terminal I/O and belongs on the CLI side of that line; the plan computation and reconciliation do not. |
| `standards-single-responsibility` | Single Responsibility | Each module owns one concern. Reconciliation (desired vs recorded vs on-disk), manifest read/write, agent-registry loading, and skill rendering are four concerns — argues against growing `init.py` into all of them. |
| `standards-dependency-inversion` | Dependency Inversion | The arrow points inward; core logic never imports the CLI. A core `plan_init` must not reach back for a prompt. |
| `standards-dry` | DRY | Every rule has one authoritative home. Directly relevant to FR-19 (one authored source per skill, access mode injected at install) and to FR-36 (the config header generated from the loader's own key registry rather than hand-copied). |

### Testing

| ID | Title | Why relevant |
|----|-------|-------------|
| `technical-test-guidelines` | Test Authorship Guidelines | The two-tier model and the **codex anchoring rule**: every `tests/e2e/test_*.py` cites exactly one `conceptual-workflows-*` doc and tests only behaviour that doc describes — written *after* the doc exists. Manifest reconciliation and interactive prompting have no such doc today, so codex work is a precondition for E2E tests, not a follow-up. Also fixes file naming: E2E file slug = codex id minus the `conceptual-workflows-` prefix. |
| `decisions-006-no-seed-content-tests` | Do not test seed default file content | Forbids asserting specific field values or prose from anything under `src/lore/defaults/`. Valid targets are existence, parseability, and required-field presence. This directly shapes how the 15→10 catalogue and access-mode injection can be tested — an assertion that a rendered skill contains a particular command string is exactly what this ADR rejects, so the test has to be framed structurally. |

### Codex-editing rules for the doc work in this feature

| ID | Title | Why relevant |
|----|-------|-------------|
| `decisions-020-codex-voice-is-enforced` | ADR-020: canonical codex documents describe current state | Binds the rewrites of `tech-arch-agents-md` and `conceptual-workflows-lore-init`, and any new doc. No history, no "previously", no changelog voice; `lore health --scope voice` audits it. |
| `decisions-014-link-direction` | Link direction — the codex is the hub | Defines the four edge types: codex↔codex `related`, codex→code `binds`, codex→rite `rites`, source→canonical one-way. New modules need `binds:` entries on the docs that govern them. |
| `decisions-018-overlays-are-path-discovered-config` | ADR-018: overlays are path-discovered config | `.lore/custom-schemas/` is not seeded by init — its absence is the zero-overlay baseline. Relevant because init's seeding rules and the health scan both have to keep treating it that way. |
| `decisions-019-overlay-scope-stops-at-transient` | ADR-019: overlay scope stops at transient | Transient docs (this map, the tech spec) validate against the **packaged** codex frontmatter schema alone. That schema is `additionalProperties: false` over `id`/`title`/`summary`/`type`/`related`/`binds`/`rites` — which is why the lens is recorded in the body of this document and not as a `lens:` frontmatter key. |
| `decisions-001-dumb-infrastructure` | Dumb infrastructure design principles | To be amended in place (body + a dated `## Status History` row matching the table format in ADRs 013/014/015/017/020/021). Its "minimise tool calls" principle is also the stated basis for the PRD's access-mode performance NFR. |
| `conceptual-workflows-impacts` / `conceptual-workflows-codex-map` / `conceptual-workflows-codex-chaos` | `lore impacts` / `codex map` / `codex chaos` Behaviour | The three commands FR-18 keeps in both access modes. Read them for the precise mechanics (bidirectional `binds` surfacing; two-budget directional BFS; random walk with reachable-subgraph termination) that justify why no agent file tool substitutes. |

---

## How to Use This Map

Every agent that receives this map should:
1. Run `lore codex show <id1> <id2> ...` with all IDs in the tables above
2. Read every document listed before starting their mission
3. Do not explore the codex independently — this map is your entry point

Read in this order: `interactive-init-prd` → the "Docs bound to the files this feature edits" table → the API and CLI contract tables → the rest.

---

## Scout Notes

**Direct contract collision to resolve in the tech spec.** `ref-lore_cli-commands` states that `--json` is supported on every command except `lore init` and `lore oracle`, and calls the exception **permanent**. The PRD defers "the shape of the `--json` envelope for `lore init`" to the tech spec. Either the tech spec declines `--json` on init, or it overturns a documented permanent exception — which by this project's own convention is an ADR, not a story-level decision.

**`click.Choice` vs a data-driven registry.** ADR-017 requires constrained flags to use `click.Choice` so bad values exit 2. FR-11 requires the agent list to come from seeded data rather than being compiled into init logic. `click.Choice` is evaluated when the decorator runs, so the registry has to be readable at import time — from the *package* data (`src/lore/defaults/`), not from the project's `.lore/`, since `lore init` runs where no `.lore/` exists yet. Worth stating explicitly in the tech spec.

**`api.py` purity blocks the obvious implementation.** `tech-arch-api-facade` pins zero `def`/`class` statements in `api.py`. `InitPlan` needs a home in a core module (`lore.models` is where the other frozen boundary dataclasses live) and only its name may appear in `api.py`.

**Three central nouns have no codex document.** `lore codex search` for `skills`, `manifest`, and `hash` returns only the PRD. `.lore/skills/` is written by `init.py` today, along with a generated `skills/.gitignore` (`src/lore/init.py:216-230`), and nothing in the codex describes either. The codex-apply mission will be creating documents, not only editing them — most likely a new `conceptual-workflows-*` doc for reconciliation (required before its E2E test can exist) and a technical doc for the manifest format.

**A third doc is stale in the same way as the two in scope.** `tech-arch-initialized-project-structure` binds `src/lore/init.py`, shows `AGENTS.md` at the project root, and omits `.lore/skills/` and `.lore/docs/` — both of which `init.py` already creates. It is not named in the PRD's in-scope list but will be wrong on release.

**`tech-overview` contradicts ADR-013 on the Python floor.** The technology table says Python 3.10+; ADR-013 records the minimum bumped to 3.11 for stdlib `tomllib`. Adding `questionary` means editing that table anyway ("No extras, no optional dependencies" stops being true) — fix the version line in the same pass.

**Frontmatter constraint for downstream transient docs.** The packaged codex frontmatter schema is `additionalProperties: false` and allows only `id`, `title`, `summary`, `type`, `related`, `binds`, `rites`. ADR-019 says transient docs get no overlay relief. Both context maps therefore carry `type: context-map` in frontmatter and record the lens in the body; a `lens:` key would fail `lore health --scope schemas`.
