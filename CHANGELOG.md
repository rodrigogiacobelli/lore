# Changelog

All notable changes to lore-agent-task-manager are recorded here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

See standards-public-api-stability for the public API stability and semver policy.

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