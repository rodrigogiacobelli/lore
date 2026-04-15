---
id: group-param-prd
title: PRD — --group param for lore entity creation
summary: Adds --group param to lore doctrine/knight/watcher/artifact new commands with nested-path support and auto-mkdir, switches list GROUP column display from hyphen to slash, and extends the Python API at parity. Codex list display updates to match.
type: prd
---
# --group param for `lore new` commands — PRD

**Author:** Product Manager
**Date:** 2026-04-14
**Supersedes:** _group-param-business-map, group-param-technical-map_

---

## Executive Summary

Lore users organise doctrines, knights, watchers, and artifacts into nested subdirectories under `.lore/` (e.g. `doctrines/feature-implementation/...`, `knights/default/...`, `artifacts/transient/...`). Today, every `lore <entity> new` command writes flat into the entity root — the only way to create a nested entity is to hand-edit files on disk, which bypasses validation, duplicate detection, and the Python API. This feature adds a single `--group` parameter (CLI) / `group=` kwarg (Python API) to the four entity `new` commands, auto-creates the target subtree, and switches the `list` GROUP column display from hyphen-joined (`default-codex`) to slash-joined (`default/codex`) so what users read in `list` matches what they type in `--group`.

### What Makes This Special

One parameter restores symmetry between how `lore init` already lays out the tree and how users create new entities in it — and does so through core modules, so Realm (via `lore.models`) gets identical behaviour without any CLI detour.

---

## Project Classification

| Attribute | Value |
|-----------|-------|
| Project type | CLI tool + Python library (`lore` / `lore.models`) |
| Primary users | AI orchestrator agents (Realm), human developers using `lore` CLI |
| Scale | Single-user local installs; entity counts in the low thousands per project |

---

## Success Criteria

### User Success

A user (human or agent) can create a doctrine, knight, watcher, or artifact directly into an arbitrarily nested subdirectory in one command, see it listed with a readable slash-joined group, and filter it back out using the same slash-delimited token they just typed. No manual `mkdir`, no hand-written files, no divergence between CLI and Python API.

### Technical Success

| Metric | Baseline | Target | Timeline |
|--------|----------|--------|----------|
| Entity `new` commands supporting `--group` | 0 of 4 | 4 of 4 (doctrine, knight, watcher, artifact) | This release |
| Python API create functions accepting `group=` | 1 of 4 (`create_doctrine` accepts no group today) | 4 of 4 (`create_doctrine`, `create_knight`, `create_watcher`, `create_artifact`) | This release |
| `list` commands rendering GROUP with `/` separator (table + JSON) | 0 of 4 | 4 of 4 | This release |
| `--filter` regression on nested groups | Pass | Pass (unchanged behaviour for existing users) | This release |
| E2E coverage for nested create + list display + filter | None | One E2E per entity covering create-nested, list-table, list-json, filter-match | This release |

---

## Product Scope

### MVP

- `--group <path>` option on `lore doctrine new`, `lore knight new`, `lore watcher new`, `lore artifact new`.
- `group=<str|None>` kwarg on the corresponding Python API functions: `create_doctrine`, `create_knight`, `create_watcher`, `create_artifact`. Null/omitted means entity root.
- Auto-creation of intermediate directories under the entity root (`mkdir(parents=True, exist_ok=True)`).
- New `validate_group` validator in `lore/validators.py` (zero `lore.*` imports) rejecting: `..`, backslashes, absolute paths, leading/trailing slash, empty segments, and any per-segment token that fails the existing `validate_name` character rule (alphanumerics + `-` + `_`).
- New `create_knight(name, persona_src, knights_dir, group=None)` and `create_artifact(name, body_src, artifacts_dir, group=None)` helpers in `lore/knight.py` and `lore/artifact.py`, extracting the currently-inline knight create logic from `cli.py` and adding the first artifact write path. `create_doctrine` and `create_watcher` gain `group=None` kwargs.
- Duplicate detection remains subtree-wide via `rglob` for all four entities — a name collision anywhere under the entity root still fires, regardless of group.
- `list` GROUP column display switches from `-` to `/` in both the human table and the `--json` envelope for `lore doctrine list`, `lore knight list`, `lore watcher list`, `lore artifact list`, and `lore codex list` (list-only change for codex — no `codex new` work).
- `--filter` grammar switches to slash-delimited tokens in lock-step: users type `--filter seo-analysis/keyword-analysers`, matching the new display. The filter matching algorithm is updated to split on `/` and compare segment-by-segment against the entity's subdirectory path.
- Enriched `--help` text updated on all four `new` subcommands to teach `--group`, with a nested-path example.
- Codex docs updated in lock-step: `conceptual-workflows-doctrine-new`, `conceptual-workflows-knight-crud`, `conceptual-workflows-watcher-crud`, `conceptual-workflows-doctrine-list`, `conceptual-workflows-knight-list`, `conceptual-workflows-watcher-list`, `conceptual-workflows-artifact-list`, `conceptual-workflows-filter-list`, `conceptual-workflows-help`, `conceptual-workflows-json-output`, `tech-cli-commands`, `tech-cli-entity-crud-matrix`, `tech-api-surface`, `tech-doctrine-internals`, `tech-arch-knight-module`, `tech-arch-validators`.
- E2E + unit tests per `technical-test-guidelines`: one E2E per entity (create nested, list table, list JSON, filter match), unit tests for `validate_group`, unit test for the `paths` group-display helper.

### Post-MVP

- None. The feature is deliberately scoped to one parameter and the matching display switch.

### Out of Scope

- Any `group` concept for `quest` or `mission` (they are DB entities, not file entities).
- Any `codex new` command (codex has no CLI write path today, and this feature explicitly excludes adding one — codex gets list-display changes only).
- Renaming or moving existing entities between groups (`edit --group`, `mv`, symlinks). Entities stay where they were created.
- A group-metadata store, group registry, or group aliases. Groups are nothing more than subdirectory paths.
- Any change to `lore init`'s seeded layout.
- Any change to `lore health` scanning behaviour (already handles nested subdirs via `rglob`).

---

## User Workflows

### Create a nested doctrine — AI orchestrator

**Persona:** Realm orchestrator agent organising a growing `seo-analysis` feature area.
**Situation:** Several SEO-related doctrines are accumulating under `doctrines/seo-analysis/` and the agent needs to add a new one without hand-editing files.
**Goal:** Create a doctrine at `.lore/doctrines/seo-analysis/keyword-analysers/keyword-ranker.yaml` + `.design.md` in one command.

**Steps:**
1. Agent runs: `lore doctrine new keyword-ranker --group seo-analysis/keyword-analysers --yaml-file ranker.yaml --design-file ranker.design.md`
2. System validates the name (`keyword-ranker`) and the group (`seo-analysis/keyword-analysers`) per-segment. Both pass.
3. System checks for duplicate doctrine named `keyword-ranker` anywhere under `.lore/doctrines/` via `rglob`. None found.
4. System creates `.lore/doctrines/seo-analysis/keyword-analysers/` (mkdir with `parents=True, exist_ok=True`), then writes `keyword-ranker.yaml` and `keyword-ranker.design.md` atomically into it.
5. System prints: `Created doctrine: keyword-ranker (group: seo-analysis/keyword-analysers)` and exits 0.
6. With `--json`, same action returns `{"ok": true, "data": {"id": "keyword-ranker", "group": "seo-analysis/keyword-analysers", "path": ".lore/doctrines/seo-analysis/keyword-analysers/keyword-ranker.yaml"}}`.

**Critical decision points:**
- Duplicate name anywhere in subtree → exit non-zero with `Error: doctrine 'keyword-ranker' already exists at <existing path>`.
- Group fails validation (e.g. `..`, leading `/`, empty segment) → exit non-zero with `Error: invalid group '<value>': <reason>`.
- Name fails validation → existing `validate_name` error path, unchanged.

**Success signal:** `lore doctrine list --filter seo-analysis/keyword-analysers` shows the new doctrine with `GROUP = seo-analysis/keyword-analysers`.

---

### Create a knight at the entity root — human developer

**Persona:** Developer adding a one-off top-level knight.
**Situation:** No grouping needed; the knight lives directly under `.lore/knights/`.
**Goal:** Create `.lore/knights/reviewer.md`.

**Steps:**
1. User runs: `lore knight new reviewer --persona-file reviewer.md`
2. System validates name; group is `None` (flag omitted).
3. Duplicate check via `rglob` over `.lore/knights/` — none found.
4. System writes `reviewer.md` directly under `.lore/knights/`.
5. System prints: `Created knight: reviewer` and exits 0.

**Critical decision points:** Same as nested case minus group validation.
**Success signal:** `lore knight list` shows `reviewer` with `GROUP = -` (empty-group sentinel, unchanged).

---

### Create a nested watcher — AI orchestrator

**Persona:** Realm agent wiring a watcher under an existing feature area.
**Situation:** `.lore/watchers/feature-implementation/` already exists.
**Goal:** Add a new watcher `on-prd-ready` into it.

**Steps:**
1. Agent runs: `lore watcher new on-prd-ready --group feature-implementation --yaml-file watcher.yaml`
2. System validates name and group.
3. Duplicate check via `rglob` over `.lore/watchers/`.
4. Target directory `.lore/watchers/feature-implementation/` already exists — `mkdir(parents=True, exist_ok=True)` is a no-op.
5. System writes `on-prd-ready.yaml` into it, prints `Created watcher: on-prd-ready (group: feature-implementation)`, exits 0.

**Critical decision points:** Duplicate anywhere in subtree fails; idempotent mkdir never fails on existing dir.
**Success signal:** Watcher appears in `lore watcher list` under `feature-implementation`.

---

### Create a nested artifact — AI orchestrator

**Persona:** Realm agent producing a new artifact template.
**Situation:** Artifact previously had no CLI write path; the feature adds `lore artifact new`.
**Goal:** Create `.lore/artifacts/codex/templates/fi-review.md`.

**Steps:**
1. Agent runs: `lore artifact new fi-review --group codex/templates --body-file review.md`
2. System validates name and group.
3. Duplicate check via `rglob` over `.lore/artifacts/`.
4. System creates `.lore/artifacts/codex/templates/` and writes `fi-review.md` into it.
5. System prints `Created artifact: fi-review (group: codex/templates)`, exits 0.

**Critical decision points:** Same as other entities.
**Success signal:** `lore artifact list --filter codex/templates` shows `fi-review` with `GROUP = codex/templates`.

---

### List + filter with slash-joined groups — any user

**Persona:** Any user inspecting or filtering an entity list.
**Situation:** Previously, `lore artifact list` rendered `.lore/artifacts/default/codex/overview.md` with `GROUP = default-codex`. Users had to type `--filter default-codex` to match.
**Goal:** See and filter groups using the same slash-delimited form they used on create.

**Steps:**
1. User runs: `lore artifact list`
2. System renders the table with `GROUP = default/codex` for the overview row. Root-level artifacts still render `GROUP = -`.
3. User runs: `lore artifact list --filter default/codex`
4. System matches any artifact whose directory path segments begin with `default/codex`, returning the same rows that were shown in step 2's subtree. Filter parsing splits on `/` and does a segment-prefix match.
5. `lore artifact list --json` returns `{"ok": true, "data": [{"id": "overview", "group": "default/codex", ...}, ...]}` — the `group` key is slash-joined in the envelope.

**Critical decision points:**
- User supplies a filter with trailing or leading `/` → treat as equivalent to the trimmed form (no error).
- User supplies an empty filter token → existing empty-filter error path, unchanged.

**Success signal:** What the user typed in `--group` on create is exactly what they read in `list` and pass to `--filter`.

---

## Functional Requirements

### Entity creation — `--group` parameter

- **FR-1:** User can pass `--group <path>` to `lore doctrine new`, `lore knight new`, `lore watcher new`, and `lore artifact new`.
- **FR-2:** User can omit `--group`; the entity is then written directly under the entity root.
- **FR-3:** System auto-creates any missing intermediate directories under the entity root before writing, using `mkdir(parents=True, exist_ok=True)`.
- **FR-4:** System rejects any group value containing `..`, a backslash, an absolute path prefix, a leading or trailing `/`, or any empty segment, with a clear `Error: invalid group` message and non-zero exit.
- **FR-5:** System rejects any group whose per-segment tokens contain characters outside the `validate_name` character set (alphanumerics, `-`, `_`).
- **FR-6:** System performs duplicate-name detection across the entire entity subtree via `rglob`, regardless of the supplied group. A name collision anywhere fails the create.
- **FR-7:** `lore artifact new <name> [--group <path>] --body-file <file>` is a newly introduced subcommand producing a single file at `.lore/artifacts/[<group>/]<name>.md`.

### Python API parity

- **FR-8:** `create_doctrine`, `create_knight`, `create_watcher`, and `create_artifact` accept `group: str | None = None` as a keyword argument and enforce FR-3 through FR-6 internally. CLI handlers are thin wrappers — no `--group` validation or mkdir happens in `cli.py`.
- **FR-9:** `create_knight` and `create_artifact` are newly added to `lore/knight.py` and `lore/artifact.py` with signatures symmetric to `create_doctrine` / `create_watcher`. The previously-inline knight create logic in `cli.py` is moved into `create_knight`.
- **FR-10:** A new `validate_group(group: str | None) -> str | None` function is added to `lore/validators.py` with zero `lore.*` imports. It returns the normalised group (identical string, or `None`) on success and raises `ValueError` on failure.
- **FR-11:** A new `paths` helper joins group segments for display using `/` and is the single source of the slash-joined form consumed by list rendering and JSON envelopes. Filesystem path construction continues to use `pathlib.Path` joins.

### List display + filter

- **FR-12:** `lore doctrine list`, `lore knight list`, `lore watcher list`, `lore artifact list`, and `lore codex list` render the GROUP column in the human table using `/` as the separator.
- **FR-13:** The `--json` output for all five list commands emits the `group` key using `/` as the separator. Entities at the entity root emit `group: null` (unchanged null semantics).
- **FR-14:** `--filter <token>` on all five list commands accepts slash-delimited tokens and performs segment-prefix matching against each entity's on-disk subdirectory path. Existing hyphen-delimited input is no longer accepted — this is a breaking change in the filter grammar, documented in the lock-step codex update.
- **FR-15:** `lore codex list` group display switches in lock-step with the other four, but no other codex behaviour changes. Codex remains read-only; no `codex new` is added.

### Help + teaching

- **FR-16:** Enriched `--help` on the four `new` subcommands teaches `--group`, including a nested-path example matching the User Workflows above.
- **FR-17:** Enriched `--help` on the five `list` subcommands reflects the slash-delimited filter grammar.

### Documentation

- **FR-18:** Every codex doc listed in the MVP bullet on codex updates is updated in the same commit/PR that ships the code change, so the codex never disagrees with shipped behaviour.

---

## Non-Functional Requirements

### Performance

- Group validation and mkdir add O(1) work per create — no measurable overhead versus baseline flat create.
- List rendering cost is unchanged: swapping a string join delimiter is O(n) in the number of segments per row.

### Security

- `validate_group` is the single chokepoint against path traversal. It must reject `..`, backslashes, absolute paths, and empty segments before any filesystem call is made.
- `find_knight` and the equivalent entity-find functions continue to reject `/` and `\` in names — the path-traversal guard on names is preserved; groups are a separate, validated parameter.
- `validators.py` stays free of `lore.*` imports per `standards-dependency-inversion`.

### Reliability

- `mkdir(parents=True, exist_ok=True)` is idempotent; re-running a create into an existing group never fails on the directory itself.
- Duplicate-name detection is subtree-wide via `rglob`, preventing two entities with the same name from coexisting under different groups.
- Atomic two-file writes (doctrine `.yaml` + `.design.md`) remain atomic; the mkdir happens before the write pair, and a failure between the two files surfaces the same error as today.
- `lore health` scans are unaffected — already walks subtrees recursively.

---

## Change Log

| Version | Change | Reason |
|---------|--------|--------|
| 1.0 | Initial PRD | Resolved open questions from the business + technical context maps: (1) artifact `new` IS in scope as a new subcommand; (2) `--filter` grammar migrates to `/` in lock-step with display (option b from the technical map), not display-only; (3) codex gets list-display changes only, no `codex new`; (4) knight create logic is extracted from `cli.py` into `create_knight` to match sibling modules; (5) `validate_group` is a new validator, not a reuse of `validate_name`. |

---

## Pre-Architecture Notes

_(Appended by the user after reviewing this PRD — do not edit until sign-off phase)_
