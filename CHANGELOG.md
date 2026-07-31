# Changelog

All notable changes to lore-agent-task-manager are recorded here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

See standards-public-api-stability for the public API stability and semver policy.

## [Unreleased]

### Added

#### `lore health --scope voice` — codex voice linting

A tenth `--scope` token that audits canonical codex prose against the codex voice rules (`lore artifact show codex-voice`). Because `health_check`'s accepted scope values are public API, the added token is an additive, minor-bump change per standards-public-api-stability.

- **Five mechanical checks** — `voice_past_narration` (V1, V2: "previously", "formerly", "used to be", "has been renamed", "no longer exists"), `voice_expiry_hedge` (V3: "currently", "for now", "at the time of writing", "so far"), `voice_forward_promise` (V4: "will be added", "planned", "in the future"), `voice_dangling_deixis` (V5: "as mentioned above", "the new `<x>`", "this release"), and `voice_sales_register` (V9: "powerful", "seamless", "robust", "cutting-edge", "effortless", "simply", "just"). V6, V7, V8, and V10 need judgement a pattern match cannot supply and have no check.
- **Warnings only** — every row is a `warning` and no voice id is escalated, so the scope never changes the exit code. `lore health --scope voice` on a codex full of violations still exits 0.
- **Per-layer rule budgets** — each check is skipped in the layers whose purpose is the construct it flags: `decisions/` may narrate prior state, `transient/` may narrate and promise, `sources/` carries verbatim upstream text, and `vision/` is deferred until the rule is settled.
- **Regions the linter does not read** — frontmatter values other than `summary`, fenced code blocks, inline code spans, and the `transient/health-*.md` reports `lore health` writes itself. A report quoting a violation has not committed one.
- **Patterns tuned against known false positives** — "no longer" describing present state ("the parent is no longer visible") and subordinate uses ("if the Knight file no longer exists") do not fire; nor do the "employed in order to" sense of "used to", generic change verbs in a conditional perfect passive ("after its facts have been folded"), procedural "the new value"/"the new file", "work being planned", or the temporal senses of "just".

#### `codex-voice` — the codex voice rules, shipped as an artifact

A new design-document artifact defines the single voice every canonical codex document speaks in, retrieved with `lore artifact show codex-voice`. It ships with the package, so `lore init` seeds it into every project alongside `doctrine-design`, `glossary-design`, `inquest-design`, and `rite-design`.

- **The artifact** — `lore-design-documents/codex-voice.md`. Ten rules, two tests that settle borderline sentences (does it mean anything to a reader who never saw a previous version; is a fact about today lost if you delete it), and a table giving each codex layer its own rule budget. The rules live here and nowhere else: every skill, knight, doctrine, and codex document references the artifact by ID rather than restating it.
- **Seeded skills** — the five skills that author or edit canonical codex prose now retrieve the rules before drafting and run `lore health --scope voice` before finishing: `update-codex`, `ingest-source`, `refresh-source`, `lore-update`, and `new-rite`. Skills that write only to `transient/` or write no codex files are deliberately untouched, `inquest` most notably: its verdicts are narratives about work already done, which the tense rules exist to keep out of canonical layers.
- **Tech Writer knight** — gains a `## Voice` section built in the shape of its existing glossary gate, and a rule requiring `lore health --scope voice` to pass before any codex mission closes.
- **Doctrines** — the codex-authoring steps in `feature-implementation`, `quick-feature-implementation`, and `tdd-feature` retrieve the rules at draft time and gate on the check before posting their completion board message.
- **Codex change proposal template** — gains a `## Voice Check` section for recording the judgement calls the automated scope cannot make.
- **Seeded codex guide** — the `codex.md` template every new project reads first gains a voice section and adds change narration and forward promises to its list of what does not belong in a codex.
- **The decision** — recorded as `decisions-020-codex-voice-is-enforced`, covering why enforcement is warnings rather than errors, why each layer gets the budget it does, and why the rules ship as an artifact instead of a `standards/` document.

### Fixed

#### `lore health --scope` flag form in the source-ingest skills

`ingest-source` and `refresh-source` instructed agents to run `lore health --scope codex --scope schemas`, the repeated-flag form that `decisions-012-multi-value-cli-param-convention` explicitly names as wrong. Both now use the space-separated form the convention requires.

#### Codex documentation corrections found while applying the voice rules

- **`lore health` unknown-scope behaviour** — `conceptual-workflows-health` documented a single exit-1 error for an unrecognised `--scope` value, describing the hand-rolled validator that `decisions-017-constrained-flags-use-click-choice` rejected. The two real paths are now documented separately: a value outside the `click.Choice` set exits 2 with Click's message, while an unknown token in the positional argument exits 1.
- **Stale scope list in the Python API reference** — `ref-lore_api-core` omitted `rites` from `health_check`'s valid scope tokens, shipped incomplete since that scope was added.
- **Wrong signatures in the CLI entity matrix** — `tech-cli-entity-crud-matrix` documented `create_knight`, `create_watcher`, and `create_artifact` as taking a directory as their first argument; all three take `project_root`.
- **Nonexistent references in the Artifact entity doc** — `conceptual-entities-artifact` claimed two shipped namespaces where there are four, and named three artifact IDs and three doctrines that no longer exist.

#### Custom codex frontmatter schema overlays — scope corrections

- **Overlays no longer reach `codex/transient/`** — a custom field, especially a `required` one, was applied to every codex document including the in-flight working docs under `.lore/codex/transient/` and the health reports `lore health` writes there itself. Declaring a required custom field therefore turned every past report into a schema error and every subsequent `lore health` run added one more, while `lore codex new --group transient` refused to create a PRD or tech spec without the field. Overlays now govern canonical codex docs and the `sources/` layer only; transient working docs validate against the packaged schema at every seam (`lore health`, `lore codex new`, `lore codex edit`). A transient doc that carries a declared custom key is still rejected as an unknown property — custom fields are canonical-codex governance.
- **`lore codex edit --set/--unset/--add/--remove` honours the overlay** — field-edit mode validated against the packaged schema only, so `--set owner=alice` failed with `Unknown property 'owner'` even when the project's overlay declared `owner`. That blocked the backfill `lore health` prescribes when a custom field is newly made required. Field-edit now resolves the same merged schema as every other codex writer (packaged for transient docs), and CLI scalar coercion consults it too, so a custom array, integer, or boolean field coerces by its declared type instead of reaching validation as a raw string.

## [0.9.0] - 2026-06-25

### Added

#### Custom codex frontmatter schemas

Projects can extend the packaged codex frontmatter schemas with their own **add-only overlay** files, validated everywhere the packaged schemas are.

- **Overlay discovery and merge** — a project drops `.lore/custom-schemas/<kind>.yaml` (for v1, `codex-frontmatter` and `codex-source-frontmatter`), auto-discovered by filename with no config. The resolver merges the overlay's `properties` and `required` onto the packaged base: **add-only** (a key colliding with a packaged field is rejected; defaults can never be redefined or weakened) and **strict** (`additionalProperties` stays `false`, so declared custom keys validate but undeclared keys — typos — still error). Merged validators are cache-keyed on the overlay's mtime, so an edited overlay is re-read within a long-running process.
- **Validation integration** — `lore health` validates both codex kinds against the merged schema (canonical docs and the `sources/` layer), and `lore codex` create/edit accept declared custom keys at write time. A malformed or rule-breaking overlay surfaces as a single clean `scan_failed` health issue, never a stack trace, with every other check still running.
- **`OverlayError` and public API** — overlay-construction failures raise `OverlayError(ValueError)` (mirroring `GlossaryError`/`ImpactsError`), surfaced as `scan_failed` in health and propagating through codex create/edit's existing `ValueError` contract. `resolve_merged_schema`, `project_validator_for`, `OverlayError`, and `validate_entity(..., project_root=...)` are exported through `lore.api.__all__` at CLI↔API parity (additive, minor bump per the semver policy).
- **`new-custom-schema` skill** — a seeded authoring skill that interviews for the target kind and custom fields, enforces the add-only rules before writing, writes the overlay, then runs `lore health` for immediate confirmation.

## [0.8.0] - 2026-06-09

### Added

#### Rite — procedural-memory entity

A new file-backed entity type — the seventh audited by `lore health`. A **rite** is procedural memory: how to do or diagnose a recurring task, stored as YAML under `.lore/rites/`, a sibling of the codex.

- **Rite storage, schemas, and loader** — two rite kinds. **Main rites** (`main/`) are node-graphs carrying `summary`, `trigger`, branching `nodes`, and typed `conclusions`. **Shared steps** (`shared/`) are pure single-exit procedures (`id, title, summary, do`) reused by main rites via a node's `use:` reference. New schemas `lore://schemas/main-rite` and `lore://schemas/shared-step`; the loader resolves `use:` by inlining the shared step's body.
- **`lore rite list` and `lore rite search`** — `list` browses main rites (`ID GROUP TRIGGER SUMMARY`) or shared steps (`--shared`); `search` is a keyword browse over main rites' `id / title / summary / trigger`.
- **`lore rite show` with shared-step inlining** — render one or many rites in full, inlining each `use:`d shared step's body into the document.
- **`lore rite new` / `edit` / `delete`** — full write path following the watcher/doctrine/knight/artifact model: validate-then-write, subtree-wide duplicate-id detection, and soft-delete by `.yaml.deleted` rename (ADR-015). `--shared` selects the shared-step schema and subfolder.
- **Codex `rites:` frontmatter field and one-way link direction** — codex docs name the rites they govern via an optional `rites:` array. The edge is one-way — codex→rite — fixed by ADR-014 (`decisions-014-link-direction`); rites carry no back-links (`related`/`binds` rejected on the rite side). A `rites:` id with no matching rite is a health error; an orphan main rite is not (it is still found via `lore rite list`).
- **Rite Python API parity and models** — `Rite`, `RiteNode`, `RiteBranch`, `RiteConclusion`, and `SharedStep` dataclasses; rite CRUD, scan, and read callables exported through `lore.api.__all__` at parity with the other file-backed entities.
- **Rite health checks** — graph well-formedness per main rite (single entry node, reachability, defined-and-reached conclusions), reference integrity (dangling `use:`, dangling `then:`, dangling codex `rites:`), duplicate-id detection, and an orphan-shared-step warning.
- **Recursive discovery, grouping, and global id uniqueness** — rites are discovered recursively under `main/` and `shared/` with a `group` derived from the subfolder path; identity is the `id:` field, globally unique across the entire tree (ADR-016). JSON envelopes carry `group` (root → `null`), with the `main`/`shared` kind surfaced via distinct envelope keys.
- **Default rite templates and design guide** — `rite-main` and `rite-shared-step` template artifacts plus the `rite-design` guide seeded into `src/lore/defaults/`.
- **`new-rite` skill and docs** — the `new-rite` skill drafts, creates, or updates a rite and links the codex docs it governs; rites documented in the seeded `LORE-AGENT.md` and `codex.md`.
- **`explore-rite` and `explore-codex-rite` skills** — read-path counterparts to `new-rite`, seeded into `src/lore/defaults/skills/`. `explore-rite` browses, matches (AI-as-matcher on `trigger` + `summary`), and follows a rite via `lore rite list / search / show`. `explore-codex-rite` researches a question across both memory surfaces at once — codex (what-is-true) and rites (how-to) — classifying the question, traversing each, and bridging codex→rite via the doc's `rites:` field. Both are auto-discovered by `lore init`; no manifest change.
- **Rite surfaced in `lore --help`** — Rite listed among the entity types in `lore --help`; `lore health` now audits seven file-backed entity types.
- **`summary` on shared steps** — shared steps gained a required `summary` field (field order `id, title, summary, do`, `minLength: 1`), bringing them in line with the cross-entity summary convention every other entity already follows. Surfaced as a new `SUMMARY` column in `lore rite list --shared`, in that command's JSON envelope, and in `lore rite show`. `summary` is a what-it-does description, not a retrieval cue — `trigger` stays main-rite-only, so shared steps remain pure single-exit procedures.

#### `tdd-feature` doctrine

- **New `tdd-feature` doctrine** — a spec pipeline that consumes a pre-existing PRD (it does not produce one): Branch → Scout → Tech Spec → ADR reconciliation → human Spec Gate → parallel Tech Planning + Codex Apply → Group Stories → dynamically-created grouped TDD dev cycles (Red → Green → Refactor → Dev Commit, one chain per story group, run sequentially) → a final Defaults Review reconciling `src/lore/defaults/`. Its knights are namespaced under a `tdd-feature/` group (`adr-standards-enforcer`, `defaults-reviewer`, `story-grouper`, `tech-planner`), reusing the shared `feature-implementation/` knights (scout, architect, tech-writer).

## [0.7.0] - 2026-05-27

### Added

#### Full file-backed entity CRUD parity

- **`feat(lore.codex): create / update / delete codex documents via lore.api and CLI`** (b6afe74) — codex documents reach full CRUD parity. `create_document`, `update_document`, and `delete_document` exported through `lore.api.__all__`; matching `lore codex new / edit / delete` subcommands ship on the CLI.
- **`feat(lore.frontmatter_edit): field-level frontmatter editing for file-backed entities`** (edbb5d3) — new `update_frontmatter_fields` callable exported through `lore.api.__all__`, providing a cross-entity primitive for editing individual frontmatter fields on any file-backed entity without rewriting the whole file.
- **`feat(lore.glossary): create / update / delete glossary items via lore.api and CLI`** (f60cb7c) — glossary items can now be mutated through `lore.api` and the CLI. `create_glossary_item`, `update_glossary_item`, and `delete_glossary_item` exported through `lore.api.__all__`; matching `lore glossary new / edit / delete` subcommands ship on the CLI.

#### `lore.api` public API facade

- **New `lore.api` module** — pure re-export facade and the only supported import surface for external consumers (Realm, Citadel, third parties, the future Lore Server). Zero `def`, zero `class`: every name in `lore.api.__all__` is re-exported from an internal module. Per ADR-010 (amended), `lore.api.__all__` replaces `lore.models.__all__` as the stable public API contract. Three-section layout: types & enums, project root, then domain-grouped operational callables (validators → db quest/mission CRUD → status transitions → dependencies → board → dashboard/stats → envelopes → priority → knight → doctrine → artifact → watcher → codex → glossary → impacts → health → schemas → init/reports/config). See `tech-arch-api-facade`.
- **Full operational surface exported through `lore.api.__all__`** — every CRUD, lifecycle, traversal, validator, schema, health, impacts, priority, and reporting callable that consumers may call. Knight, doctrine, and artifact now reach full CRUD parity in the public surface: `update_knight`, `delete_knight`, `update_doctrine`, `delete_doctrine`, `update_artifact`, and `delete_artifact` are all in `__all__`, joining the create/read/list helpers landed previously. The CLI exposes the matching `lore <entity> edit` and `lore <entity> delete` subcommands at full parity (ADR-011).
- **Underscore-aliased CLI re-exports** — `lore.api` carries a small block of leading-underscore namespace aliases (`_paths`, `_graph`, `_knight`, `_validators`, `_watcher`, `_glossary`, `_impacts`, `_doctrine`, `_health`, `_lore_version`, `_validate_frontmatter`) consumed only by Lore's own `cli.py` and unit-test monkeypatches. The underscore prefix keeps them out of `dir(lore.api)` and excludes them from `from lore.api import *` per Spec §1, so they are not part of the public surface even though they are importable.
- **New `tech-arch-api-facade` codex doc** — covers the pure re-export pattern, the three-section `__all__` layout, and the underscore-aliased namespace re-exports. Binds to `src/lore/api.py`.

#### `inquest` skill

- **New `inquest` default skill** — a backward audit of finished work. Given a closed quest and one precise issue (a missing requirement, or a skipped codex mandate), the skill reconstructs the doctrine chain, collects evidence (quest description, transient docs, board handoffs, commit history, and codex obligations surfaced via `lore impacts`), walks each link with a two-part custody question — present inbound? present outbound? — and writes a **verdict**: a blame file naming the culprit link, the failure mode, the responsible party, and the evidence. The verdict is written as a transient codex doc at `.lore/codex/transient/inquest-<slug>.md` (not `.lore/reports/`, which `oracle` wipes on every run). Seeded into `.lore/skills/` on `lore init`; auto-listed in the generated `skills/.gitignore`.
- **New `inquest-design` artifact** — `lore-design-documents` group. The chain-of-custody tracing procedure the `inquest` skill follows: pin the requirement to its origin (the external request, or a codex mandate found via `lore impacts`), reconstruct the chain link by link, walk it with the two-part custody question, and classify the failure mode — Drop, Never-captured, Distortion, Override, or Instruction gap. The Instruction-gap mode blames the doctrine itself rather than any agent; Override is surfaced for a human ruling rather than condemned. Carries the verdict-file template. Retrieve with `lore artifact show inquest-design`.

#### `lore-update` skill

- **New `lore-update` default skill** — reconciles a project's customized `.lore/codex/CODEX.md` and agent instruction file (`CLAUDE.md`, `AGENTS.md`, …) against the freshly seeded templates after the `lore` package is upgraded. `lore init` overwrites the *seed* copies (`.lore/artifacts/default/codex/CODEX.md`, `.lore/LORE-AGENT.md`) on every run but never the project's customized files, so generic "how Lore works" guidance drifts stale — a project whose CODEX.md predated the `binds:` field carried no mention of it, and stale wording could outright conflict with the new seed. The skill runs `lore init`, diffs seed-vs-project, and merges new generic mechanics (frontmatter fields, commands, layers, conventions) section by section while preserving every project-specific customization, applying a generic-vs-project classification rule and flagging deliberate-customization conflicts for the user to rule on. It identifies the agent instruction file from the running agent's own provider (Claude Code → `CLAUDE.md`, OpenAI Codex → `AGENTS.md`, …). The skill does not upgrade the `lore` package itself — the user does that first. Seeded into `.lore/skills/` on `lore init`; auto-listed in the generated `skills/.gitignore`.

### Changed

- **BREAKING: `lore.api` public-surface renames.** Per the public-API-stability policy, these are explicit breaking-change notices in lieu of a major bump:
  - `edit_quest` → `update_quest`, `edit_quest_full` → `update_quest_full`, `edit_mission` → `update_mission`, `edit_mission_full` → `update_mission_full` (`edit_*` → `update_*` across quest and mission CRUD).
  - `get_quest` → `read_quest`, `get_mission` → `read_mission` (read-side aligned with the rest of the `read_*` family).
  - `get_board_messages` → `list_board_messages` (list-side aligned with the rest of the `list_*` family).
  - `get_mission_depends_on` / `get_mission_depends_on_details` → `list_mission_depends_on`; `get_mission_blocks` / `get_mission_blocks_details` → `list_mission_blocks` (dependency reads collapsed into one `list_*` callable per direction).
  - `scan_artifacts` → `list_artifacts`, `scan_codex` → `list_codex` (`scan_*` → `list_*` for the file-backed list surface).
  - `show_doctrine` → `read_doctrine` (doctrine read aligned with the `read_*` family).
- **BREAKING: removed from `lore.api.__all__`.** `find_knight`, `find_watcher`, `load_watcher`, and the `DoctrineError` exception class are no longer part of the public surface. Use `read_knight`, `read_watcher`, and standard exception types respectively.
- **Added to `lore.api.__all__`** — `update_frontmatter_fields` (field-level frontmatter editing), `entity_location` (canonical on-disk path resolver from `lore.paths`), `create_glossary_item` / `update_glossary_item` / `delete_glossary_item` (glossary CRUD), and `create_document` / `update_document` / `delete_document` (codex CRUD).
- **`create_mission` parent inference now applies to direct-Python callers** — calling `create_mission(project_root, title)` from `lore.api` (or `lore.db`) with no `quest_id` and exactly one open quest in the project now auto-attaches the new mission to that sole-open-quest. Previously only the CLI handler inferred the parent; direct-Python callers received a standalone mission. The behaviour is now identical across CLI and Python per ADR-011 parity (FLAG #4 in the facade Review Ledger).
- **Public API contract relocated from `lore.models.__all__` to `lore.api.__all__`** (per ADR-010 amendment and ADR-011). `lore.models` still hosts the dataclasses and enums, but its `__all__` is no longer the consumer-facing contract. Realm and other consumers must import exclusively from `lore.api`. Codex docs `ref-lore_api-core`, `standards-public-api-stability`, `standards-facade`, `tech-arch-source-layout`, and `tech-cli-entity-crud-matrix` have been rewritten to anchor on the new facade. See ADR-010, ADR-011, and the ADR-007 Amendment (artifact mutation via `lore.api`).
- **ADR-007 Amendment — Artifact mutation via `lore.api`** — artifacts (instances and templates) may now be created, updated, and deleted through `lore.api` like any other file-backed entity. The communication protocol described in ADR-007 is unaffected; the prior implicit "mutation is on-disk" constraint is removed in line with the full-CRUD-parity sweep above.
- **BREAKING: `lore.models` legacy re-exports removed (per ADR-010).** Twelve names that were re-exported through `lore.models` purely for pre-`lore.api` backward compatibility are gone from `lore.models.__all__`: `HealthIssue`, `HealthReport`, `health_check`, `SchemaIssue`, `load_schema`, `validate_entity`, `validate_entity_file`, `CodeBinding`, `CodexBinding`, `ImpactsError`, `ImpactsResult`, `impacts`. All twelve remain available — and have always been available — through `lore.api`. `lore.models` is now a leaf type module: dataclasses + enums, no operational-module dependencies. (`befa0a5`)
- **`lore.cli` multi-value flags now accept space-separated tokens (ADR-012 compliance).** `lore knight list`, `lore doctrine list`, `lore artifact list`, and `lore watcher list` previously rejected `--filter a b` with "Got unexpected extra argument (b)". They now mirror `lore codex list` and `lore health --scope` by accepting space-separated tokens. The legacy repeated-flag form (`--filter a --filter b`) still works, so this is additive at the CLI level. (`39ef098`)
- **Glossary-specific validators moved to `lore.validators`** (per `standards-dry`). The previously-inline `_validate_keyword_format`, `_validate_definition`, and `_validate_alias_list` helpers in `lore.glossary` are now `validate_glossary_keyword_format`, `validate_glossary_definition`, and `validate_glossary_alias_list` in `lore.validators`. Behaviour-preserving move — error messages and validation rules are identical. (`e7074ae`)
- **Seeded `CODEX.md` renamed to `codex.md`** (and `.lore/codex/conceptual/workflows/codex.md` → `conceptual-workflows-codex.md`). The uppercase filename held a lowercase `id: codex` in its frontmatter, which broke `lore codex edit codex` on case-sensitive filesystems (`_find_document` resolves by filename stem). The rename aligns every codex doc's filename stem with its frontmatter id, so `lore codex edit codex` now reaches the root index doc cleanly and the colliding workflows file is unambiguous. Affects both seed (`src/lore/defaults/artifacts/codex/codex.md`) and any project's live `.lore/codex/codex.md`. (`0f46924`)

#### Documentation

- **New `.lore/codex/api/` layer with `api-guide` + `api-reference`** — public Python API documentation under a dedicated codex layer. `api-guide` is the narrative entry point (per-entity walkthroughs, field-edit mode, error model, versioning); `api-reference` is the exhaustive per-symbol lookup, walking every name in `lore.api.__all__` (125 symbols) with signature, return shape, raises, and one example. `.lore/codex/codex.md` registers the layer in its layer table. The seeded template is NOT touched — the `api/` layer is Lore-specific (not every Lore-managed project ships a Python API). (`0f9230d`)
- **Seeded bootstrap docs reshaped: `LORE-AGENT.md` owns the Lore mental model; `codex.md` owns codex instructions.** The mental-model Entities section (Quest, Mission, Knight, Doctrine, Codex, Glossary, Artifact, Watcher, Board message, Dependency — each with primary CLI verbs and a one-line example) now lives in the seeded `LORE-AGENT.md`. `codex.md` is back to being codex-specific (layout, three content classes, reading/writing, impacts engine, sources rules, ref docs, what NOT to put in the codex). Skills (`update-codex`, `explore-codex`, `ingest-source`, `refresh-source`) carry the deep guidance. Dangling references to non-seeded doc IDs (`conceptual-workflows-impacts`, `conceptual-workflows-glossary`, `conceptual-workflows-help`, `conceptual-workflows-claim`, `conceptual-entities-glossary`) cleaned up across skills, knights, doctrines, and `init.py`. (`3859c28`, `5436c2c`)

## [0.6.0] - 2026-05-19

### Added

#### Codex hygiene

- **`conceptual-workflows-schema-migrations` now binds the migration modules** — `binds:` declares `src/lore/migrations/__init__.py` + `v1_to_v2.py` through `v5_to_v6.py` and `src/lore/db.py`. Previously these files were dark code reachable only via the catch-all `src/lore/**/*.py` glob in `tech-arch-source-layout`. `lore impacts src/lore/migrations/<file>.py` now surfaces the workflow doc directly.

#### `lore health --scope bindings`

- **New `bindings` scope on `lore health`** — audits the `binds:` field of every codex entry for reference integrity. Two checks: `dead_binding` (error) when a literal path in `binds:` does not exist on disk, and `empty_glob_binding` (warning) when a glob pattern matches zero files in the repo. `dead_binding` flips exit code 1 via `has_errors`; `empty_glob_binding` is warning-only and leaves exit 0. No orphan detection in either direction — unbound files and unbound codex docs are both legitimate.
- **Valid scope tokens** for `lore health --scope`: `codex`, `artifacts`, `doctrines`, `knights`, `watchers`, `schemas`, `glossary`, `bindings`. Multi-scope per ADR-012 (space-separated). Default (no `--scope`) runs all eight.
- **`_walk_repo_files` repo walker** — lazy single walk per `health_check()` call, built only when at least one glob binding is encountered. Skip list `{.git, .lore, node_modules, __pycache__}`. Symlink containment via `Path.resolve().relative_to(project_root)` — symlinks escaping the project root are dropped. `PermissionError` / `OSError` on individual `iterdir` calls swallowed so a single unreadable directory does not abort the walk. Paths are POSIX-joined, sorted ascending.
- **`_check_bindings` reuses `lore.impacts` helpers** — `_has_glob_chars`, `_normalize_slashes`, `_pattern_to_regex`, and `_load_codex_binds_index` are imported rather than duplicated. Exact-vs-glob classification matches the `lore impacts` precedent byte-for-byte.
- **`HealthIssue` shape** for both new checks: `entity_type="codex"`, `id=<codex-doc-id>`, `check="dead_binding"` or `"empty_glob_binding"`, `schema_id` / `rule` / `pointer` all `null`. Detail strings are exact: `'"<path>" — file not found'`, `'"<path>" — resolves outside project root'`, `'"<pattern>" — pattern matches zero files'`.
- **Python API parity** — `lore.models.health_check(scope=["bindings"])` returns rows row-for-row identical to the CLI (per ADR-011). No new exports in `lore.models.__all__`.
- **Codex docs** — `conceptual-workflows-health` documents the new scope, the bindings checker, and the severity-split rationale; `conceptual-workflows-impacts` Out-of-Scope updated to point at `bindings` scope for dead-binding detection; `tech-cli-entity-crud-matrix`, `ref-lore_cli-commands`, and `ref-lore_api-core` register the new scope token and check names.

#### Codex impacts

- **`lore impacts` command** — bidirectional surfacing primitive over the new `binds:` codex frontmatter field. `lore impacts <codex-id>` lists the entry's bound code paths in declaration order; `lore impacts <path>` returns every codex entry whose `binds:` matches that path, annotated `exact` or `glob`. Token classification routes `/` or `.` to the path branch, everything else to the codex-id branch.
- **`binds:` codex frontmatter field** — optional list of repo-root-relative paths or globs declaring which code files a codex entry governs. Schema rejects non-strings, empty strings, absolute paths, and `..` traversal; `additionalProperties: false` preserved. Absent and `binds: []` are semantically identical (entry appears in no path lookups). `validate_binds_entry` and `is_glob_pattern` added to `lore.validators`.
- **Exact-vs-glob match semantics** for path lookups — entries containing `*`, `?`, or `[` are treated as globs and matched via stdlib `fnmatch` + manual `**` recursive bridge (no filesystem walk, symlink-safe). Per codex ID, an exact match wins over a glob match. Results sort alphabetically by codex ID; codex-seed output preserves declaration order.
- **`--json` and `--direct-links` flags on `lore impacts`** — `--json` emits `{"impacts": [...]}` with `{"path", "kind"}` rows for codex-seed and `{"id", "match"}` (plus `pattern` for glob rows) for code-seed. `--direct-links` restricts code-seed output to exact matches; no-op on codex-seed. Unknown codex ID or path resolving outside the repo exits 1 with the error on stderr (text or `{"error": ...}` JSON).
- **`lore.impacts` Python module re-exported via `lore.models`** — `impacts(token, *, project_root, direct_links=False) -> ImpactsResult` with frozen `CodexBinding` / `CodeBinding` items and an `ImpactsError(ValueError)` for both error paths. `dataclasses.asdict` output matches the CLI `--json` envelope byte-for-byte.
- **Codex docs** — new `conceptual-workflows-impacts` workflow; `binds:` field documented across `codex`, `tech-arch-schemas`, `tech-arch-frontmatter`, `tech-arch-source-layout`, `tech-arch-validators`, `tech-cli-entity-crud-matrix`, `ref-lore_cli-commands`, `ref-lore_api-core`, `conceptual-workflows-codex`, `conceptual-workflows-validators`, `conceptual-entities-knight`, `tech-overview`, and `vision-benchmarks` (Layer-3 retrieval primitive).
- **Seed defaults updated** — packaged `CODEX.md` artifact gained the `binds:` paragraph; `scout` and `architect` knight personas instruct agents to run `lore impacts <path>` when sizing or mapping a change; `tech-writer` is told to populate `binds:` on code-governing docs; `new-artifact`, `update-codex`, `ingest-source`, and `refresh-source` skills carry the same guidance; 15 codex-doc artifact templates (standards, ADRs, technical/architecture, technical/ref, conceptual workflows, runbooks, security) ship with a commented `# binds: []` placeholder. Existing `.lore/` instances are untouched on `lore init`; new projects pick up the seeds.
- **Lore's own `.lore/codex/` bound to source and tests** — 58 codex docs now declare `binds:` against `src/lore/**` and `tests/**` patterns: `technical/architecture/*` to their modules, `technical/cli` / `technical/api` / `technical/database` / `technical/doctrine` / `technical/oracle` refs to their handler modules, all CLI-backed `conceptual/workflows/*` docs to `src/lore/cli.py` + the underlying module + matching e2e tests, and the ADRs that constrain specific files (002, 003, 004, 005, 007, 010, 011, 013) to those files. Cross-cutting workflows (`error-handling`, `json-output`, `help`, `concurrent-access`, `typical-workflow`, `mission-type`, `python-api`, `schema-migrations`) and pure-policy ADRs (001, 006 both, 008, 009, 012) deliberately stay unbound. `lore impacts src/lore/<module>.py` now returns every governing doc for that module — this repo is the worked example of the feature.

### Changed

- **`lore health` glossary scope — `do_not_use_collision` now also catches cross-item duplicates.** When two glossary items declare the same surface form under `do_not_use:` (e.g. both items list `bot mission`), `lore health --scope glossary` emits a `do_not_use_collision` error. The previous family-2 rule only caught a `do_not_use` term colliding with another item's `keyword` or `alias`; the cross-item duplicate-deprecation case slipped through.

### Fixed

- **`tech-arch-schemas` dead binding repaired.** `binds:` referenced `src/lore/schemas.py`, which no longer exists — the schemas module became a package (`src/lore/schemas/__init__.py`) when the YAML resources moved into the same directory. Updated to bind `src/lore/schemas/__init__.py` and added the previously-missing `src/lore/schemas/codex-source-frontmatter.yaml`. `lore health` is now clean on the bindings scope.

### Removed

- **Non-canonical `stability` frontmatter field purged.** The `stability` codex-frontmatter field was never part of `codex-frontmatter.yaml` (which is `additionalProperties: false` and allows only `id`, `title`, `summary`, `related`, `binds`), but it had leaked into `CODEX.md` (both as a required-field claim and a dedicated description paragraph), the `tech-arch-schemas` allowed-fields table, and two transient docs that carried `stability: experimental` in their own frontmatter. All references removed; `lore health` no longer reports `additionalProperties` errors against `/stability`. The `new-doctrine` skill in defaults also drops the negative `never type, stability` clause from its frontmatter rule — positive enforcement only, since not mentioning the field gives an AI no reason to invent it.

- **Cross-codex deprecated-term scan removed from `lore health`.** Glossary scope no longer walks every codex body looking for `do_not_use` token-tuple hits — the scan emitted too many false positives (ADRs explaining the deprecation, quoted historical text, and any prose discussing the deprecated form would all trigger `glossary_deprecated_term` warnings). `do_not_use` field in `glossary.yaml` is preserved as documentation; the intra-file `do_not_use_collision` check stays (and now also catches cross-item duplicates, see above). Glossary scope now runs two families instead of three: schema validation and intra-file collisions.
- **`lore.glossary.find_deprecated_terms` deleted.** The Python helper that powered the cross-codex scan is gone. `lore.glossary._normalise_tokens`, `_build_lookup`, `_iter_runs`, `_scan_runs`, and `match_glossary` (the shared tokeniser, still used by `lore codex show` auto-surface) all remain. `find_deprecated_terms` was not in `lore.models.__all__`, so the public API surface is unchanged.
- **`glossary_deprecated_term` removed from `_ESCALATED_WARNING_CHECKS`.** The escalation set in `lore.health` shrinks to `frozenset({"alias_keyword_collision"})`. No remaining check produces the `glossary_deprecated_term` warning name.
- **Codex docs** — `conceptual-workflows-health` drops the family-3 section under glossary scope and reframes `do_not_use` as documentation-only; `conceptual-entities-glossary` drops the "cross-codex scan" surface count (3 → 2); `conceptual-workflows-glossary` drops `find_deprecated_terms` from its Python API listing; `tech-arch-source-layout` drops `find_deprecated_terms` from the `glossary.py` module symbol list; `ref-lore_api-core` drops the function from its covers-line.

## [0.5.0] - 2026-05-17

### Added

- **Reference Docs convention** documented in `CODEX.md` — `technical/<domain>/ref/` subdirectories with `ref-<system>-<concept>` IDs hold intent (history, gotchas, non-enforced constraints) around concrete artifacts; schema stays in the source of truth.
- **`update-codex` skill** for direct chat doc edits outside the feature-implementation flow. Treats `.lore/codex/CODEX.md` as a primary input *and* a maintenance responsibility — the skill must read it for project-specific rules and update it when a change introduces a new convention, layer, or project-wide rule. CODEX.md is lean by design; only structural/rule-level changes warrant an edit.
- **`lore init` seeds `.lore/codex/CODEX.md`** from the packaged `artifacts/codex/CODEX.md` default, rewriting the artifact's `id: example-codex` frontmatter to `id: codex`. Idempotent: an existing `CODEX.md` is left byte-for-byte untouched. Like `glossary.yaml` and `config.toml`, CODEX.md is a user-tracked skeleton seeded directly under `.lore/codex/` (not under `.lore/codex/default/`), making it a second carve-out from the "init never writes to `.lore/codex/`" rule. `lore health` recognises the seeded doc and the new `paths.codex_md_path()` helper exposes its location to other modules.

### Changed

- **BREAKING: `lore codex map` default output is now a list-shape table** mirroring `lore codex list` (columns: ID, GROUP, TITLE, SUMMARY) instead of full markdown bodies. The default `--json` envelope key is now `"codex"` (was `"documents"`). The seed document is no longer included in the result set; results are deduplicated by ID and sorted alphabetically. Use `--full` to restore full-body output — the `--full --json` envelope keeps the `"documents"` key for backward compatibility, with `group` and `related` added per entry alongside the existing `id`, `title`, `summary`, `body`.
- **BREAKING: `lore codex map` traversal is now bidirectional by default** — outbound `related` edges plus inbound backlinks at depth 1 each. New directional flags `--depth-out N` and `--depth-in N` control each axis independently and can be combined freely (e.g. `--depth-out 2 --depth-in 1`). `--depth N` sets both axes to N and is mutually exclusive with `--depth-in`/`--depth-out` — combining them exits 2 with the usage error `--depth cannot be combined with --depth-in or --depth-out. Use --depth for symmetric traversal, or --depth-in and/or --depth-out for directional traversal.` Under `--json` the same error is emitted as `{"error": "..."}` on stderr with exit 2. All depth values use `click.IntRange(min=0)`. Previous outbound-only behaviour is now `--depth-out N`.
- **BREAKING: `lore.codex.map_documents` Python API parity per ADR-011** — signature changes to `(codex_dir, start_id, *, depth_out=1, depth_in=1, full=False) -> list[dict] | None`. The legacy positional `depth` parameter is removed. Default-mode records have keys `{id, group, title, summary}`; `--full` mode records have `{id, title, summary, group, related, body}`. Returns `None` only for an unknown seed; an empty neighbourhood returns `[]`. Negative depth values raise `ValueError`.
- **New `ConflictingDepthFlags(ValueError)` exception** exported from `lore.codex` for Python callers building their own depth-conflict logic. The CLI uses `click.UsageError` for the text path and a direct JSON envelope for `--json`; the exception class exists for parity-conscious API consumers.
- **Internal: `lore.codex._build_adjacency(index, docs) -> (outbound, inbound)`** helper extracted and shared between `map_documents` (which picks per-direction edges) and `chaos_documents` (which unions both into the undirected adjacency it already used). `chaos_documents` behaviour is byte-for-byte unchanged.
- **`CODEX.md` default artifact** (`src/lore/defaults/artifacts/codex/CODEX.md`) updated to describe the new `lore codex map` ergonomics (bidirectional default, directional flags, `--full`). The Reference Docs section's example body-shape block is removed — readers wanting a concrete example browse existing `ref-*` docs (`lore codex search ref-`) instead of reading an inline template.
- Lore's own internal docs migrated to the new pattern: schema/internals dumps for database, API, CLI, and doctrine replaced by `ref-*` cluster docs; `related:` links across the codex updated; seeded default codex template now ships a `ref/` example instead of `schemas/`.
- `explore-codex` and `ingest-source` skills note the new `ref-*` routing.
- **`tech-writer` knight, `ingest-source` skill, and `refresh-source` skill** now treat `.lore/codex/CODEX.md` as a primary input *and* a maintenance responsibility, matching the `update-codex` skill. Each must read CODEX.md before writing codex content (to pick up project-specific layers, conventions, and rules) and propose updates to it when their work introduces a new convention, layer, or project-wide rule. CODEX.md remains lean by design — only structural/rule-level changes warrant an edit.

### Fixed

- **`lore codex map` and `lore codex chaos` no longer drop documents with multi-line `summary:` continuations** — the internal `_parse_doc_robust` / `_scan_codex_robust` helpers in `lore.codex` stripped leading whitespace per frontmatter line, which corrupted YAML plain-scalar continuations (e.g. a `summary:` wrapped across two indented lines) and made the affected docs invisible to map/chaos traversal with `Document "<id>" not found`. The robust parser duplicated `lore.frontmatter` against the `tech-arch-frontmatter` single-parser intent; both helpers are removed and map/chaos now route through `scan_codex` / `frontmatter.parse_frontmatter_doc[_full]` like `show`/`list`/`search`. Test fixtures rebuilt to not depend on `textwrap.dedent` over interpolated multi-line list items.
- **Wheel build now ships `src/lore/schemas/*.yaml`** — `[tool.hatch.build.targets.wheel].artifacts` extended so packaged installs can resolve schema YAMLs via `importlib.resources`. Without this, `lore.schemas` was empty in the built wheel.
- **`test_conceptual_entities_artifact_has_required_outbound_related`** updated to expect `ref-lore_cli-commands` after the rename from `tech-cli-commands` in the Reference Docs convention migration.
- **Duplicate `CODEX.md` seed source removed.** `src/lore/defaults/docs/CODEX.md` was being copied verbatim to `.lore/CODEX.md` in parallel with the canonical `defaults/artifacts/codex/CODEX.md`. The artifact is now the single source: it lands at `.lore/artifacts/default/codex/CODEX.md` (overwritten on every init like other defaults) and seeds `.lore/codex/CODEX.md` (idempotent, with `id: example-codex` → `id: codex` rewrite). `lore init` no longer produces `.lore/CODEX.md`.

## [0.4.0] - 2026-04-30

### Added

#### Glossary

- **New `Glossary` codex artefact** — single canonical YAML file at `.lore/codex/glossary.yaml` holding short, project-specific term definitions keyed by `keyword`. Each item has a `keyword` and `definition` plus optional `aliases` and `do_not_use` lists. The `keyword` is the natural key — no `id` field. See `conceptual-entities-glossary`.
- **`lore glossary` CLI group (read-only)** — three subcommands:
  - `lore glossary list` (alias `lore glossary`) — list every entry alphabetically by keyword. `--json` supported.
  - `lore glossary search <query>` — case-insensitive match against `keyword`, `aliases`, `do_not_use`, and `definition`. Multi-word queries supported with quoting.
  - `lore glossary show <keyword> [<keyword>...]` — return full entries by canonical keyword (case-insensitive lookup; aliases are NOT accepted as lookup keys).
  No `new`/`edit`/`delete` — maintainers edit the YAML directly. Mirrors the artifact CLI pattern.
- **Auto-surface on `lore codex show`** — when `show-glossary-on-codex-commands = true` (default) in `.lore/config.toml` and `--skip-glossary` is not passed, the system tokenises every returned codex document body, matches against keyword + alias token-tuples, and appends a trailing `## Glossary` section listing each matched item alphabetically. Multi-doc dedup at two levels: within-body and across-bodies. JSON envelope gains an always-present `"glossary": [...]` array. `do_not_use` matches do NOT auto-surface — they only surface in `lore health`. Fail-soft: a malformed glossary emits one stderr `glossary unavailable: <reason>` line and continues; `lore codex show` still exits 0.
- **`--skip-glossary` flag on `lore codex show`** — per-call escape hatch that suppresses the `## Glossary` section unconditionally and returns an empty `"glossary"` array in JSON mode.
- **`.lore/config.toml` (new project config file)** — generic, forward-compatible TOML config loader. Unknown keys are accepted and ignored to enable additive evolution. First (and only) MVP setting: `show-glossary-on-codex-commands` (bool, default `true`). Missing file → defaults silently. Malformed file → defaults + one stderr warning per process. Loaded by a new `lore.config` module; `Config` is internal-only and not exported via `lore.models.__all__`.
- **`lore health --scope glossary`** — runs glossary-only checks: schema validation, intra-file collision audits (duplicate keyword case-insensitive → error; alias-keyword collision → warning escalated to error; `do_not_use` overlap with another item's keyword/alias → error), and a cross-codex `glossary_deprecated_term` scan that emits one warning per occurrence of any `do_not_use` term in any codex document body. The `glossary` token combines with other scopes per ADR-012 (e.g. `lore health --scope codex glossary`).
- **`lore.glossary` Python module** — exports `scan_glossary`, `read_glossary_item`, `search_glossary`, `match_glossary` (canonical-only matches, alphabetised, deduplicated), `find_deprecated_terms` (per-occurrence health scan), `GlossaryError`. Built on a single shared word-boundary tokeniser (`re.compile(r"[^\w]+", re.UNICODE)` + `str.casefold()`) and lookup primitive reused by both surfaces.
- **`GlossaryItem` exported from `lore.models`** — frozen immutable dataclass with `keyword`, `definition`, `aliases`, `do_not_use`. `from_dict` classmethod constructs from raw YAML.
- **`glossary` JSON Schema** — packaged at `src/lore/schemas/glossary.yaml` (`$id: lore://schemas/glossary`). `_check_schemas` extended to support literal-filename globs (single fixed file at a known path) alongside `**/*.yaml` patterns.
- **ADR-013 — TOML for project config; YAML for glossary content** — `.lore/config.toml` uses TOML for ergonomic single-file key/value editing; `.lore/codex/glossary.yaml` uses YAML to match all other codex content (frontmatter, schemas, doctrines). Records the `lore init` carve-out below.
- **`conceptual-entities-glossary` codex doc** — full lifecycle, surfaces, properties, edge cases, and a "What Belongs Here" section gating glossary additions through three questions (project-specific? not an entity? not a named workflow?). Links to the design-doc artifact.
- **`conceptual-workflows-glossary` codex doc** — read-side workflows for `list`, `search`, `show`, auto-surface, and `--skip-glossary`. Test-anchor for every E2E scenario.
- **`glossary-design` design-document artifact** — checklist agents must run before adding any glossary entry. Contains the three-question gate, worked good/bad examples (Constable passes; Quest, ADR, Soft-delete, Auto-surface, Weapon all fail), YAML stanza template, and a "where to put it instead" table. Retrievable via `lore artifact show glossary-design`. Referenced from `tech-writer` knight, `ingest-source`/`refresh-source` skills, the seeded `CODEX.md`, and the seeded `glossary.yaml` header — every default that writes to the codex now points at the gate.

#### `lore init` and seeded defaults

- **`lore init` seeds `.lore/codex/glossary.yaml`** with a project-agnostic skeleton (`items: []` + a header pointing at `lore artifact show glossary-design`). The Glossary is the only file `lore init` seeds under `.lore/codex/` — a deliberate carve-out from the prior "init never writes to `.lore/codex/`" rule. The skeleton lands directly at `.lore/codex/glossary.yaml`, NOT under `.lore/codex/default/`, because the file is user-tracked vocabulary and a `default/` placement would be gitignored and overwritten on every re-init. Idempotent: existing files are left byte-for-byte untouched.
- **`lore init` seeds `.lore/config.toml`** with `show-glossary-on-codex-commands = true` and a header comment naming known keys. Idempotent.
- **`!config.toml` added to the seeded `.lore/.gitignore`** so the new config file is git-tracked alongside the rest of `.lore/`.
- **Seeded default skills and knights gained glossary references** — `explore-codex/SKILL.md` (added `lore glossary list/search/show` to the command table), `start-quest/SKILL.md` (vocabulary-alignment line), `feature-implementation/scout.md` (glossary added as a primary input alongside PRD and codex), `LORE-AGENT.md` (orientation surface), `CODEX.md` (rewrote the glossary guidance with the strict three-question gate). Dev knights (`tdd-red`, `tdd-green`, `tdd-refactor`, `tech-lead`) deliberately untouched — they don't write codex content.
- **`.lore/skills/.gitignore` seeded at init** — `lore init` now writes a `.gitignore` inside `.lore/skills/` listing every Lore-shipped skill directory. When a user copies the skills directory into their project's `.claude/skills/`, the bundled skills are ignored automatically without needing manual gitignore edits. User-added skills in the same directory are unaffected. The list is generated dynamically from `src/lore/defaults/skills/`, so newly shipped defaults are picked up on the next init.

### Changed

- **Python minimum bumped to 3.11** — required for stdlib `tomllib` to load `.lore/config.toml` without vendoring `tomli`.
- **`lore codex show` JSON envelope** — now always includes a `"glossary"` key (empty array when skipped, disabled, no-match, or fail-soft). Existing `"documents"` key unchanged.
- **`lore health --scope` accepts multiple values** per ADR-012 (`lore health --scope codex glossary`). Previous single-value form still works.
- **`_ALL_SCOPES` and `_SCHEMA_KINDS` extended** with `glossary`. `_check_schemas` resolves literal-filename globs (no `*` in pattern) via `entity_root / glob` instead of `glob()`, supporting single-fixed-file schema kinds.

## [0.3.1] - 2026-04-22

### Fixed

- **Packaging** — removed redundant `[tool.hatch.build.targets.wheel.force-include]` block that duplicated `src/lore/schemas/` in the wheel (the directory was already packaged via `packages = ["src/lore"]`). The 0.3.0 build emitted `Duplicate name:` warnings and the resulting wheel was rejected by PyPI with `400 Invalid distribution file. ZIP archive not accepted: Duplicate filename in local headers`. 0.3.1 is the first release of the 0.3 line available on PyPI; no behavior changes vs 0.3.0.

## [0.3.0] - 2026-04-22

### Added

#### Codex sources layer

- **New `sources/` codex content class** — third layer alongside stable and in-flight, for ingesting raw upstream material (Jira tickets, meeting transcripts, pasted docs, Confluence pages) as point-in-time snapshots under `.lore/codex/sources/<system>/<id>.md`. Sources are deletable at any time — any fact worth keeping lives in a canonical doc.
- **`codex-source-frontmatter` JSON Schema** — required `id`, `title`, `summary`, and non-empty outbound `related` listing every canonical codex doc the source touched; `additionalProperties: false`. `lore codex map <source-id> --depth 1` surfaces touched canonical docs via this list.
- **`lore health` schema dispatch** — files under `.lore/codex/sources/**/*.md` are now validated against `codex-source-frontmatter` instead of `codex-frontmatter`, surfacing with `entity_type="codex-source"` in the report.
- **Island-node skip for sources** — sources are inbound-orphans by design under the one-way link rule, so the island-node pass now excludes their IDs (previously would emit noisy `no documents link here` warnings).
- **`canonical_links_to_source` health error** — fires when any non-source codex doc includes a source ID in its `related` list, enforcing the canonical→source back-link ban at validation time.
- **`ingest-source` skill** — default agent-executed skill for first-time source capture. Access-method agnostic (pasted text, local file, URL, MCP tool). Writes a verbatim snapshot, identifies affected canonical docs, and populates the snapshot's outbound `related` with the touched canonical IDs.
- **`refresh-source` skill** — mirror of `ingest-source` for re-ingestion. Diffs fresh content vs stored snapshot, propagates approved changes into canonical docs, rewrites `related` from scratch each run (additions + removals), and overwrites the snapshot in place (no history file — git holds prior state).

#### Other additions

- **`lore artifact new`** — scaffold a new artifact file under `.lore/artifacts/` from the CLI.
- **`--group` flag on `lore knight new`, `lore watcher new`, and `lore doctrine new`** — create the entity directly inside a nested group/subfolder at creation time.
- Enriched `--help` output on all `new` and `list` subcommands, documenting the group/filter grammar and showing usage examples.
- `create_knight()` extracted as a reusable Python API entry point alongside the CLI command.
- **Schema validation across every entity** — codex, artifacts, doctrines, knights, and watchers are now validated against bundled YAML schemas on every `lore health` run. Invalid frontmatter, missing required fields, and bad field types are reported as structured errors.
- **`lore health --scope schemas`** — restrict an audit run to schema validation only, skipping graph and reference checks.
- Schema errors are rendered in both human-readable text and `--json` output, with the exact entity id, file path, field path, and rule that failed.
- Unparseable YAML and entity files missing frontmatter now surface as loud schema errors instead of being silently skipped.
- The transient health report written to `codex/transient/` gained a dedicated **Schema validation** section listing every schema issue found in the run.
- **`lore.schemas.load_schema()`** — bundled YAML schemas are now packaged as resources and loadable from the public Python API.
- **Python API parity** — schema validation is exposed through `lore.models`, so Realm and other importers can validate entities programmatically without going through the CLI.
- `parse_frontmatter_raw()` helper preserves every key on disk during parsing, enabling round-trip-safe validation against the schemas.

### Changed

- **Default `CODEX.md` restructured** — the "Stable vs In-Flight" section is now **The Three Content Classes** (Stable, In-Flight, Sources) with a deletion-test row per class, the sources layout, the four-field frontmatter rule, the verbatim rule, the one-way linking rule, and the refresh rule.
- **`conceptual-entities-artifact` gained outbound `related`** — closes an outbound-orphan hub so `lore codex map conceptual-entities-artifact --depth 1` now returns reachable docs.
- **Breaking:** `--filter` now uses slash-delimited path grammar (e.g. `--filter foo/bar`) across all list commands. Previous comma or dot-separated forms are no longer accepted.
- Group handling unified on slash-delimited paths throughout `paths.derive_group` and related helpers; list output displays groups using the slash form, and `--json` output reflects the same shape.
- New `validate_group` validator enforces the slash grammar at entity creation time, rejecting invalid group strings before they hit disk.
- Create-time validators for every entity now delegate to `lore.schemas`, so the same schema contract governs both file-on-disk audits and in-memory creation paths.
- `lore init` now produces a project that passes `lore health` schema validation out of the box; bundled default doctrines, knights, watchers, and artifacts were updated to satisfy the schemas.
- **Standards References section in `fi-user-story` template** — Tech Lead populates a `Standards References` block in every story's Tech Notes, listing relevant codex docs per role (Tester, Implementer). Red and Green agents read these before starting work, eliminating reliance on agents independently searching for standards.
- **Wiring scenarios and wiring stubs** — BA and Tech Lead steps in all three feature-implementation doctrines now explicitly require integration test scenarios and stubs for any page, container, or view that assembles child components. Component isolation tests are no longer sufficient.
- **`tdd-red` and `tdd-green` personas** — Red reads `Standards References → Tester` before writing any test; Green reads `Standards References → Implementer` before touching any file. Acceptance criteria are the starting point, not the complete contract.
- **`tdd-implementation` doctrine** — Red performs a wiring and coverage check against the Tech Spec file tree before marking done; Green verifies E2E test files are matched by the runner config; Refactor audits runner coverage as a quality check.

### Fixed

- Restored the `_validator_for` cache in `_check_schemas` via a dependency-injection seam, eliminating repeated schema compilation on large `lore health` runs.
- **CODEX.md default artifact** — frontmatter documentation now matches the actual schema enforced by `lore health`. Removed non-existent `type`, `stability`, `persona`, and `entities_involved` fields; corrected required fields to `id`, `title`, `summary` with `related` as the only optional field.
- **`start-quest` skill** — `lore needs` step now instructs agents to use fully-qualified `q-xxxx/m-yyyy` mission IDs. Bare `m-yyyy` IDs caused "Mission not found" errors.
- **Feature-implementation PM and BA knights** — UI feature requests now correctly scope page integration. PM captures end-to-end user workflows when a page is mentioned; BA requires a page-integration story for every UI component.

## [0.2.0] - 2026-04-10

### Added

- **`lore health`** — full codebase health audit command. Scans all five file-based entity
  types: codex documents (broken related links, missing `id` field, island nodes), artifacts
  (missing required frontmatter), doctrines (orphaned files, broken knight/artifact refs in
  steps), knights (active missions referencing absent knight files), and watchers (invalid
  YAML, broken doctrine refs).
- **`lore health --scope <type> [<type> ...]`** — limit the audit to one or more entity
  categories (e.g. `lore health --scope codex watchers`). Valid scopes: `codex`,
  `artifacts`, `doctrines`, `knights`, `watchers`.
- **`lore health --json`** — machine-readable JSON output of all issues found.
- **`lore health` exit codes** — `0` if clean or warnings only; `1` if any errors are
  present.
- Health report written as a markdown file to `codex/transient/` on every run, so the
  audit history is accessible through the codex.
- **`health_check()` Python API** — call `from lore.models import health_check` to run
  the audit programmatically; returns a `HealthReport` with structured `HealthIssue`
  entries. Both `HealthReport` and `HealthIssue` are now part of `lore.models.__all__`.
- **`lore <entity> list --filter <subtree>`** — filter listing output by folder subtree
  for artifacts, codex documents, doctrines, knights, and watchers.
- All list commands now accept an optional path argument to scope results to a specific
  group or subfolder.
- `lore doctrine show` accepts `--json` for machine-readable output.
- New doctrines are created with a companion `.design.md` file recording the doctrine's
  `id`, `title`, and `summary` alongside the YAML definition.
- **Doctrine redesign** — doctrines now cleanly separate knight personas from task
  definitions; updated default doctrine templates, knight files, and `lore doctrine show`
  output to reflect the new structure.

### Changed

- **Breaking:** `Doctrine` model fields renamed — `name` → `id`, `description` split into
  `title` and `summary`. Code importing `Doctrine.name` or `Doctrine.description` must
  update field references.
- **Breaking:** `DoctrineListEntry` model updated to match — `name` → `id`, `description`
  replaced by `title` and `summary`; `errors` field removed; `filename` now points to the
  `.design.md` file instead of the YAML file.
- Built-in knight personas reorganized into per-workflow subdirectories (e.g.
  `knights/feature-implementation/`); existing custom knights are unaffected.
- Default doctrines updated to use the new schema with explicit `id`, `title`, and
  `summary` fields.

## [0.1.0] — 2026-03-31

First release. Lore is the task engine and project memory system at the base of the
Camelot stack. It was built entirely by AI agents tracking their own work in Lore itself.

### Added

#### Task Engine
- **Quests** — named bodies of work with priorities (0–4), statuses (`open`, `in_progress`,
  `closed`), and optional auto-close when all missions are done
- **Missions** — individual executable tasks attached to a quest or standalone; support
  `open`, `in_progress`, `blocked`, and `closed` states with block reasons
- **Dependencies** — `lore needs` / `lore unneed` create directed "blocks" edges between
  missions; `lore ready` only surfaces work whose dependencies are fully closed
- **Claim / done / block / unblock** — lifecycle commands for orchestrators and worker agents
- **Board messages** — lightweight async communication channel per quest or mission

#### Project Memory (Codex)
- **Codex** — queryable knowledge graph of typed markdown documents stored in `.lore/codex/`;
  documents carry `id`, `title`, `summary` frontmatter and a `related` list for graph links
- **`lore codex search`** — case-insensitive keyword search across titles and summaries
- **`lore codex map`** — BFS traversal up to N hops from any document
- **`lore codex chaos`** — random-walk traversal with configurable coverage threshold (30–100%)

#### Knight Personas
- Knights are markdown files that define how an agent should behave for a class of work
- `lore show <mission-id>` returns the assigned Knight's full content alongside mission details,
  so agents receive persona and task in a single call

#### Doctrine Workflow Templates
- Doctrines are YAML templates that define ordered, dependency-linked steps for a body of work
- Cycle detection prevents invalid dependency graphs at creation time
- The `/start-quest` skill reads a doctrine and materialises it as a quest with missions

#### Artifacts & Watchers
- **Artifacts** — reusable document templates agents scaffold new files from
- **Watchers** — YAML definitions for agents that monitor and react to project state

#### CLI & Python API
- Full Click-based CLI (`lore [command]`) covering every operation
- Immutable frozen-dataclass public API in `lore.models.__all__` — stable across semver minor
  versions; internal modules are not part of the public contract
- `--json` flag on all read commands for machine-readable output
- `lore init` bootstraps a project with default doctrines, knights, artifacts, watchers, and
  the Claude skills needed for Realm integration

#### Infrastructure
- SQLite backend with WAL mode, 5-second busy timeout, and foreign-key enforcement
- Schema auto-migration (v1 → v6) on first connection
- Soft deletion throughout — entities carry `deleted_at` and are excluded from normal listings
  without losing referential integrity
- `lore oracle` generates human-readable markdown reports in `.lore/reports/`
- `lore stats` provides aggregate counts across all quests and missions