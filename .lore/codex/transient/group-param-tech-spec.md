---
id: group-param-tech-spec
title: Tech Spec — --group param for lore entity creation
summary: Concrete architectural decisions to add --group to doctrine/knight/watcher/artifact new, switch list GROUP display + filter grammar from hyphen to slash, extract create_knight and create_artifact, and reach CLI + Python API parity.
type: tech-spec
related:
  - group-param-prd
  - group-param-business-map
  - group-param-technical-map
  - tech-doctrine-internals
  - tech-arch-knight-module
  - tech-arch-validators
  - tech-api-surface
  - tech-cli-entity-crud-matrix
  - conceptual-workflows-doctrine-new
  - conceptual-workflows-knight-crud
  - conceptual-workflows-watcher-crud
  - conceptual-workflows-artifact-list
  - conceptual-workflows-filter-list
  - decisions-011-api-parity-with-cli
  - standards-single-responsibility
  - standards-dependency-inversion
---

# --group param for `lore new` commands — Tech Spec

**Author:** Architect
**Date:** 2026-04-15
**Supersedes:** _group-param-technical-map_
**Input:** _group-param-prd_

---

## Core Architectural Decisions

| Priority | Decision | Choice | Rationale |
|----------|----------|--------|-----------|
| Critical | Where `--group` semantics live | In core modules (`doctrine.py`, `knight.py`, `watcher.py`, `artifact.py`). CLI handlers are thin wrappers that pass `group=` through. | ADR-011 (API parity) and `standards-single-responsibility` forbid business logic in `cli.py`. PRD FR-8 requires Python API parity. |
| Critical | Canonical in-memory group form | Migrate to `/`-joined everywhere: `paths.derive_group` returns `"a/b/c"`, list dicts carry `group: "a/b/c"`, JSON envelopes emit `"a/b/c"`, `--filter` input splits on `/`. Option (b) from the Scout notes. | PRD FR-11..FR-14 pick lock-step migration over a dual `derive_group`/`derive_group_display`. Single canonical form removes skew. |
| Critical | Root-group representation | Empty string `""` in memory, `None` in JSON, `-` in the human table. No change to null semantics. | PRD FR-13 mandates `group: null` in JSON for root. Table `-` sentinel is existing behaviour. |
| Critical | Group validation | New `validate_group(group: str \| None) -> str \| None` in `validators.py`, zero `lore.*` imports. Rejects `..`, `\`, absolute path, leading/trailing `/`, empty segment, any segment that fails `_NAME_RE`. Returns normalised string or `None`. | PRD FR-4, FR-5, FR-10. `standards-dependency-inversion` keeps `validators.py` pure. Reuses existing `_NAME_RE` per-segment. |
| Critical | Filter grammar | Breaking change: `--filter` tokens are slash-delimited (`seo-analysis/keyword-analysers`). Parsing splits on `/`, segment-prefix match against each record's split group. Leading/trailing `/` stripped silently. Empty token still errors. | PRD FR-14. Keeps display form and filter form identical (the core UX claim of the feature). |
| Critical | Knight create path | Extract inline `cli.knight_new` logic into `lore.knight.create_knight(knights_dir, name, content, group=None)`. CLI becomes a formatter. | PRD FR-9. Matches sibling modules (`doctrine.create_doctrine`, `watcher.create_watcher`). |
| Critical | Artifact create path | New `lore.artifact.create_artifact(artifacts_dir, name, content, group=None)` plus new `lore artifact new` CLI subcommand. | PRD FR-7, FR-9. Artifact module was read-only; feature introduces the first write path. |
| Important | Directory creation strategy | `(base_dir / Path(group or ".")).mkdir(parents=True, exist_ok=True)` performed inside each `create_*` helper, after validation, before any file write. | PRD FR-3 (auto-mkdir). Idempotent mkdir matches `conceptual-workflows-watcher-crud` reliability clause. |
| Important | Duplicate detection | Unchanged: subtree `rglob` on the entity root for the collision pattern (`<name>.yaml`, `<name>.md`, `<name>.design.md`). Fires regardless of supplied group. | PRD FR-6. Preserves current knight/doctrine/watcher behaviour; extends it to artifacts. |
| Important | `paths.derive_group` signature | Signature unchanged (`derive_group(filepath, base_dir) -> str`), body returns `"/".join(relative.parts[:-1])`. One-line behavioural change, every call site unaffected. | `standards-dry`: one canonical join. Avoids adding a sibling helper. |
| Important | Filter helper | Replace `group_matches_filter(group, filter_groups)` with segment-based matching. New signature accepts the same `list[str]`; internally splits both sides on `/`. Empty `group` still always-matches (root inclusion rule, unchanged). | PRD FR-14. Preserves the filter-list module contract while switching the delimiter. |
| Important | Click option surface | `--group <path>` is a single-valued scalar Click option on the four `new` subcommands. No `nargs`, no repeat. | ADR-012: multi-value convention is space-separated lists, explicitly scoped out of scalar params. |
| Important | Help enrichment | Each `new` subcommand help block gains a `--group` line with one nested example matching the User Workflows. Each `list` subcommand help block gains a line noting slash-delimited filter tokens. | ADR-008 teaching contract, PRD FR-16, FR-17. |
| Deferred | `edit`/`mv --group` — moving entities between groups | Out of scope. PRD explicitly rejects it. | Would require atomic rename + duplicate re-check + CLI surface area; non-goal for this feature. |
| Deferred | `codex new` write path | Out of scope. Codex stays read-only; only list display + filter grammar change. | PRD FR-15. Codex has no CLI write path today and the feature explicitly does not add one. |
| Deferred | Group metadata store / registry | Out of scope. Groups remain subdirectory paths with no metadata. | ADR-001 dumb-infrastructure; PRD Out-of-Scope bullet. |

---

## Data Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | None (file-only feature) | Groups are subdirectory paths. No schema, no migration. |
| ORM / query layer | N/A | — |
| Migration approach | N/A for the DB. Behavioural migration: one commit changes `derive_group`, `group_matches_filter`, list JSON, filter parsing, and all codex docs in lock-step. | PRD FR-18: codex + code must ship in the same commit. |
| Data validation | `validate_name(name)` unchanged + new `validate_group(group)` for the group param. Duplicate detection remains filesystem-side via `rglob`. | PRD FR-4..FR-6, FR-10. |

---

## API & Communication

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API style | Python module functions imported from `lore.doctrine`, `lore.knight`, `lore.watcher`, `lore.artifact`; each takes `group: str \| None = None` as a keyword argument. | ADR-011 parity; PRD FR-8, FR-9. |
| Error response format | `DoctrineError` / `ValueError` raised from core; CLI catches and prints `Error: <message>` to stderr, exits 1. JSON mode emits `{"error": "<message>"}` to stderr. Unchanged from existing pattern. | `conceptual-workflows-error-handling`. |
| Versioning strategy | Pre-1.0 minor bump (additive CLI options + new `lore artifact new` subcommand + filter-grammar break). CHANGELOG documents the `--filter` grammar migration as a breaking note under "Changed". | ADR-010 public-API stability. Filter grammar break is user-visible, must be called out. |

---

## Implementation Patterns

### Naming Conventions

**Database:** n/a.

**API / CLI:** Click option is `--group`, kwarg is `group=`. Core helper functions named `create_<entity>` with signature `(base_dir, name, content_or_sources, *, group=None) -> dict`. `validate_group` mirrors `validate_name`.

**Code:** Group parsed with `Path(group)` for filesystem joins, with `group.split("/")` for filter segment comparison. Never mix hyphen and slash forms in the same call path — canonical is `/`.

### Error Handling

- `validate_group` returns `None` on success, error string on failure (mirrors `validate_name`).
- Each core create helper calls `validate_name`, then `validate_group`, then duplicate check, then source-file reads, then mkdir, then write. On any validation failure raise the entity's existing exception class (`DoctrineError` for doctrines, `ValueError` for knight/watcher/artifact — consistent with current `watcher.create_watcher`).
- CLI handlers catch the exception, print the message to stderr, exit 1. JSON mode wraps in `{"error": "..."}`.
- Group errors are prefixed `Error: invalid group '<value>': <reason>` per PRD FR-4.

### Output Formats

**Success — `lore doctrine new ranker --group seo-analysis/keyword-analysers -f ranker.yaml -d ranker.design.md`:**

```
Created doctrine ranker (group: seo-analysis/keyword-analysers)
```

**Success — JSON mode (same command):**

```json
{"name": "ranker", "group": "seo-analysis/keyword-analysers", "yaml_filename": "ranker.yaml", "design_filename": "ranker.design.md", "path": ".lore/doctrines/seo-analysis/keyword-analysers/ranker.yaml"}
```

**Success — `lore knight new reviewer --from reviewer.md`:** (root group — behaviour unchanged)

```
Created knight reviewer
```

JSON: `{"name": "reviewer", "group": null, "filename": "reviewer.md"}`

**Success — `lore artifact new fi-review --group codex/templates --from review.md`:** (new subcommand)

```
Created artifact fi-review (group: codex/templates)
```

JSON: `{"id": "fi-review", "group": "codex/templates", "filename": "fi-review.md", "path": ".lore/artifacts/codex/templates/fi-review.md"}`

**Success — `lore artifact list` (display change):**

```
  ID                GROUP                TITLE                      SUMMARY
  overview          default/codex        Codex overview             Master index
  fi-review         codex/templates      Feature review artifact    Review template
  transient-note                         Transient note             One-off
```

Note root-group rows render `GROUP` as the existing sentinel (empty column / `-`), unchanged.

**Success — `lore artifact list --json`:**

```json
{"artifacts": [
  {"id": "fi-review", "group": "codex/templates", "title": "Feature review artifact", "summary": "Review template"},
  {"id": "overview", "group": "default/codex", "title": "Codex overview", "summary": "Master index"},
  {"id": "transient-note", "group": null, "title": "Transient note", "summary": "One-off"}
]}
```

**Success — `lore artifact list --filter codex/templates`:** table shows only rows whose group splits as `["codex", "templates", ...]` plus root-group rows (unchanged inclusion rule).

**Error — invalid group:**

```
Error: invalid group '../etc': path traversal ('..') not allowed in group
```

Exit code 1. JSON: `{"error": "Error: invalid group '../etc': path traversal ('..') not allowed in group"}` on stderr.

**Error — duplicate name across subtree:**

```
Error: doctrine 'ranker' already exists at .lore/doctrines/seo-analysis/ranker.yaml
```

Exit code 1.

---

## Project Structure

```
lore/
  src/lore/
    validators.py                     # + validate_group(group) -> str | None; new _GROUP_SEGMENT_RE reuses _NAME_RE
    paths.py                          # derive_group joins with "/" not "-"; group_matches_filter splits on "/" and segment-prefix-matches
    doctrine.py                       # create_doctrine gains group=None kwarg; writes into doctrines_dir / Path(group) with mkdir(parents=True, exist_ok=True)
    knight.py                         # + create_knight(knights_dir, name, content, group=None) extracted from cli.knight_new
    watcher.py                        # create_watcher gains group=None kwarg; update_watcher unchanged (edit does not move)
    artifact.py                       # + create_artifact(artifacts_dir, name, content, group=None) — first write path
    cli.py                            # + --group option on doctrine_new, knight_new, watcher_new; new artifact_new subcommand; knight_new body reduced to thin wrapper; enriched --help on all four new and all five list subcommands
    codex.py                          # scan_codex: no logic change — derive_group migration is transparent since it still calls paths.derive_group
  tests/
    unit/
      test_validators.py              # + TestValidateGroup: valid paths, nested, None, root, rejected patterns (.., \, abs, leading/trailing /, empty segment, bad segment chars)
      test_derive_group.py            # update assertions hyphen → slash
      test_paths.py                   # new or update: group_matches_filter segment-prefix tests
      test_knight.py                  # + TestCreateKnight: root, nested, duplicate subtree, invalid group, invalid name, mkdir idempotency
      test_doctrine.py                # + nested create cases for create_doctrine
      test_watcher.py                 # + nested create cases for create_watcher
      test_artifact.py                # + TestCreateArtifact: root, nested, duplicate subtree, invalid group, invalid name
      test_filter_subtree.py          # update: slash-delimited tokens, segment-prefix match
    e2e/
      test_doctrine_new.py            # + nested create, list display, filter match scenarios
      test_knight_crud.py             # new file (no current e2e): + nested create, list display, filter match scenarios
      test_watcher_crud.py            # + nested create, list display, filter match scenarios
      test_artifact_new.py            # new file: nested + root creation, table + JSON list display, filter match
      test_artifact_list.py           # update: slash-joined group display + filter grammar
      test_doctrine_list.py           # update: slash-joined group display
      test_knight_list.py             # update: slash-joined group display
      test_watcher_list.py            # update: slash-joined group display
      test_filter_list.py             # update: slash-delimited filter input across all five list commands
      test_codex.py                   # update: slash-joined group display in codex list output
```

No new directories. No files are deleted. Every source file listed is an existing module.

### File-level change detail

- **`validators.py`**: add `_GROUP_SEGMENT_RE = _NAME_RE` (alias), and:

  ```python
  def validate_group(group: str | None) -> str | None:
      if group is None:
          return None
      if not group:
          return "Error: invalid group '': must not be empty (use None for root)"
      if "\\" in group:
          return f"Error: invalid group '{group}': backslash not allowed"
      if group.startswith("/"):
          return f"Error: invalid group '{group}': absolute paths not allowed"
      if group.startswith("/") or group.endswith("/"):
          return f"Error: invalid group '{group}': leading/trailing '/' not allowed"
      segments = group.split("/")
      for seg in segments:
          if seg == "":
              return f"Error: invalid group '{group}': empty segment not allowed"
          if seg == "..":
              return f"Error: invalid group '{group}': path traversal ('..') not allowed"
          if not _NAME_RE.match(seg):
              return f"Error: invalid group '{group}': segment '{seg}' must start with alphanumeric and contain only letters, digits, hyphens, underscores"
      return None
  ```

- **`paths.derive_group`**: body becomes `return "/".join(relative.parts[:-1])`. Return type unchanged (`str`; empty for root).

- **`paths.group_matches_filter`**: rewrite as segment-prefix match:

  ```python
  def group_matches_filter(group: str, filter_groups: list[str]) -> bool:
      if group == "":
          return True
      group_segs = group.split("/")
      for token in filter_groups:
          tok_segs = token.strip("/").split("/")
          if group_segs[:len(tok_segs)] == tok_segs:
              return True
      return False
  ```

- **`doctrine.create_doctrine`**: signature becomes `create_doctrine(name, yaml_source_path, design_source_path, doctrines_dir, *, group=None)`. After `validate_name`, call `validate_group(group)`; raise `DoctrineError` on failure. Duplicate check still `doctrines_dir.rglob(...)`. Before write, compute `target_dir = doctrines_dir if group is None else doctrines_dir / Path(group)` and `target_dir.mkdir(parents=True, exist_ok=True)`. Return dict gains `"group": group, "path": str(target_dir / f"{name}.yaml")`.

- **`knight.create_knight`**: new function `create_knight(knights_dir, name, content, *, group=None) -> dict`. Validates name, group; rglob duplicate; mkdir target; writes `target_dir / f"{name}.md"`. Raises `ValueError`. Returns `{"name": name, "group": group, "filename": f"{name}.md", "path": str(...)}`.

- **`watcher.create_watcher`**: add `group: str | None = None` kwarg. Validate group; compute target_dir; mkdir; write. Return dict gains `"group"` and `"path"`. `update_watcher` unchanged — edit preserves location.

- **`artifact.create_artifact`**: new function, signature mirrors `create_knight`. Validates name via `validate_name`, validates group via `validate_group`, duplicate check over `artifacts_dir.rglob("*.md")` matching stem, requires the content to start with a YAML frontmatter block containing `id`, `title`, `summary` (enforced by re-parsing via `frontmatter.parse_frontmatter_doc` on the written file path — consistent with `scan_artifacts` strict rule). Writes file, returns dict.

- **`cli.knight_new`**: body collapses to: read content (file or stdin), call `create_knight(knights_dir, name, content, group=group)` inside a `try/except ValueError`, format output. All duplicate/mkdir/validation logic leaves `cli.py`.

- **`cli.doctrine_new`**: add `--group` option, pass through to `create_doctrine(..., group=group)`. No duplicate/mkdir logic added to `cli.py`.

- **`cli.watcher_new`**: add `--group` option, pass through.

- **`cli.artifact_new`**: new subcommand, mirrors `watcher_new` structure.

- **`cli` list renderers**: GROUP column source is the list-dict's `group` key — already slash-joined after `derive_group` migrates. For the human table, an empty string still renders as the existing sentinel (current code); no change. For JSON, emit `group: None` when empty (audit pass required: `doctrine list`, `knight list`, `watcher list`, `artifact list`, `codex list` JSON envelopes — any that currently emit `""` switch to `None` per PRD FR-13).

---

## Test Strategy

### E2E Coverage

| Workflow (from PRD) | Workflow codex ID | Test scenario | Priority |
|---------------------|------------------|---------------|----------|
| Create a nested doctrine | `lore codex show conceptual-workflows-doctrine-new` | `lore doctrine new ranker --group seo-analysis/keyword-analysers -f … -d …` then `lore doctrine list` shows `group: seo-analysis/keyword-analysers`; `--filter seo-analysis/keyword-analysers` returns it; JSON envelope carries slash-joined group | High |
| Create a knight at entity root | `lore codex show conceptual-workflows-knight-crud` | `lore knight new reviewer --from …` with no `--group`; file lands at `.lore/knights/reviewer.md`; list shows root-group sentinel; JSON emits `group: null` | High |
| Create a nested watcher | `lore codex show conceptual-workflows-watcher-crud` | `lore watcher new on-prd-ready --group feature-implementation -f …`; pre-existing target dir does not fail (mkdir idempotent); list shows `feature-implementation` | High |
| Create a nested artifact | `lore codex show conceptual-workflows-artifact-list` | `lore artifact new fi-review --group codex/templates --from …`; file at `.lore/artifacts/codex/templates/fi-review.md`; list shows slash-joined group | High |
| List + filter with slash-joined groups | `lore codex show conceptual-workflows-filter-list` | For each of the five list commands: seed one nested entity + one root entity, run `list --filter <slash/token>`, assert nested row returned + root row always included | High |
| Duplicate name anywhere in subtree | `lore codex show conceptual-workflows-doctrine-new` | Create doctrine in group A, then attempt create with same name in group B → exit 1, error mentions existing path | High |
| Invalid group rejection | `lore codex show conceptual-workflows-validators` | Matrix: `..`, `\`, leading `/`, trailing `/`, empty segment (`a//b`), bad-char segment (`a/b!c`) — each rejected before any filesystem write | High |
| JSON envelope audit | `lore codex show conceptual-workflows-json-output` | For each of the five list commands plus the four `new` commands: assert `group` key slash-joined or null, never hyphen-joined, never `""` | High |
| Help teaches `--group` | `lore codex show conceptual-workflows-help` | `lore doctrine new --help` (and the other three) contains `--group` line and the nested example | Medium |

### Unit Coverage

| Component | Workflow codex ID | Scenarios to cover |
|-----------|------------------|---------------------|
| `validators.validate_group` | `lore codex show conceptual-workflows-validators` | None → None; `""` → error; `"a"` → None; `"a/b/c"` → None; `"a/b_c-d"` → None; `".."`, `"../x"`, `"x/.."` → error; `"\\x"` → error; `"/x"` → error; `"x/"` → error; `"a//b"` → error; `"a/!/b"` → error; `"-a"` → error (leading hyphen) |
| `paths.derive_group` | `lore codex show conceptual-workflows-filter-list` | Root file → `""`; one dir → `"a"`; nested → `"a/b/c"`; no hyphen appears in output ever |
| `paths.group_matches_filter` | `lore codex show conceptual-workflows-filter-list` | Root always matches; exact match; proper-prefix match; non-prefix rejected; trailing-slash token accepted; bare prefix that is not a full segment rejected (`"tech"` does not match `"technical/api"`); multi-token OR |
| `doctrine.create_doctrine` | `lore codex show conceptual-workflows-doctrine-new` | group=None writes flat (unchanged); group nested writes nested with mkdir; mkdir idempotent; duplicate subtree-wide fires; invalid group raises `DoctrineError`; return dict carries `group` and `path` |
| `knight.create_knight` | `lore codex show conceptual-workflows-knight-crud` | Same matrix as doctrine create |
| `watcher.create_watcher` | `lore codex show conceptual-workflows-watcher-crud` | Same matrix as doctrine create; existing YAML-parse validation still runs |
| `artifact.create_artifact` | `lore codex show conceptual-workflows-artifact-list` | Same matrix; missing required frontmatter fields in body rejected (strict artifact rule) |
| `cli.knight_new` (smoke) | `lore codex show conceptual-workflows-knight-crud` | Thin-wrapper test: mock `create_knight`, assert it is called with the parsed `group` kwarg and no validation runs in the handler |

### Test Conventions

- File naming follows `technical-test-guidelines` section 4: `test_<module>.py` for unit, `test_<workflow-slug>.py` for e2e.
- Each e2e test file carries a module docstring citing the single codex ID it anchors to.
- Fixtures: unit uses `bare_lore_dir` from `tests/unit/conftest.py`; e2e uses `project_dir` + `runner` from `tests/conftest.py`. No locally defined fixtures.
- Assertion style: `assert result.exit_code == 0` + `json.loads(result.output)` for JSON envelopes; direct filesystem `Path.exists()` checks for disk outcomes.
- No `US-N` / `SCENARIO-NNN` / `AC-N` references anywhere.

---

## Crazy Tech Spec Findings

No Crazy Tech Spec was produced for this feature — decision space was small and the technical map already enumerated the only two real option points (derive_group dual vs migrate; filter grammar display-only vs lock-step). Both resolved in the PRD.

| Idea | Decision | Rationale |
|------|----------|-----------|
| Add sibling `derive_group_display` helper and keep internal form hyphen-joined | Rejected | Doubles the canonical form; filter grammar has to pick one anyway (PRD FR-14). Lock-step migration is cleaner. |
| Thread `--group` into `edit`/`delete` as a rename vector | Rejected | Explicit PRD out-of-scope. Adds atomic rename + re-validation surface area for no user need. |
| Add a `groups` metadata table in `lore.db` | Rejected | ADR-001 dumb infrastructure. Group is just a subdirectory. |

---

## Migration & Rollback

**Code migration:** one commit changes `paths.derive_group`, `paths.group_matches_filter`, every list JSON emitter (audit), every `--filter` parser (split on `/`), plus the codex docs listed in PRD FR-18. No data migration — existing on-disk entities already sit in subdirectories; the join-string change is in-memory only.

**User-visible break:** `--filter` no longer accepts hyphen-delimited tokens. A user who had scripted `lore artifact list --filter default-codex` must update to `lore artifact list --filter default/codex`. Documented in CHANGELOG under "Changed" with an explicit "breaking" note.

**Rollback:** revert the single commit. On-disk layout is untouched, so rollback has no data impact — it only restores the hyphen display + filter grammar. The four `create_*` helpers become unused but harmless; the `lore artifact new` subcommand disappears with the revert.

---

## Change Log

| Version | Change | Reason |
|---------|--------|--------|
| 1.0 | Initial Tech Spec | Resolves every PRD requirement with concrete module, signature, and test plan. Picks option (b) slash-migration over the (a) dual-helper, extracts `create_knight` and introduces `create_artifact` to reach sibling-module symmetry, and migrates `--filter` grammar in lock-step to keep display and input identical. |
