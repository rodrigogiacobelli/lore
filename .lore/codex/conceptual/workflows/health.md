---
id: conceptual-workflows-health
title: lore health Behaviour
summary: What the system does internally when lore health runs — a full-scan or scoped audit across two kinds of scope. Seven scopes name a file-based entity type (codex, artifacts, doctrines, knights, watchers, glossary, rites); three cut across them (schemas, bindings, voice). Covers error/warning reporting, the markdown report written to codex/transient, --scope filtering, --json output, the exit-code contract, and the Python API via health_check(). Includes the glossary scope's schema and intra-file collision checks, the bindings scope's reference-integrity audit over codex `binds:` (dead-literal errors and empty-glob warnings), the rites scope's recursive id-collision, reference-integrity, graph-well-formedness, and orphan-asymmetry checks, and the voice scope's five warning-only prose checks over the canonical codex layers.
binds:
- src/lore/health.py
- src/lore/cli.py
- tests/e2e/test_health.py
- tests/e2e/test_health_glossary.py
- tests/e2e/test_health_schemas.py
- tests/e2e/test_health_bindings.py
- tests/e2e/test_health_rites.py
- tests/e2e/test_health_voice.py
- tests/unit/test_health.py
- tests/unit/test_health_schemas.py
- tests/unit/test_health_voice.py
related: ["conceptual-entities-artifact", "conceptual-entities-doctrine", "conceptual-entities-knight", "conceptual-entities-watcher", "conceptual-entities-glossary", "conceptual-entities-rite", "conceptual-workflows-codex", "conceptual-workflows-glossary", "conceptual-workflows-impacts", "conceptual-workflows-error-handling", "conceptual-workflows-json-output", "decisions-006-id-references", "decisions-012-multi-value-cli-param-convention", "decisions-013-toml-for-config-yaml-for-glossary", "decisions-014-link-direction", "decisions-017-constrained-flags-use-click-choice", "decisions-018-overlays-are-path-discovered-config", "decisions-019-overlay-scope-stops-at-transient", "decisions-020-codex-voice-is-enforced", "ref-lore_api-core", "ref-lore_cli-commands", "tech-arch-schemas"]
---

# `lore health` Behaviour

`lore health` audits a Lore project's knowledge base and reports every detected inconsistency as an error or a warning. It is the only command whose sole job is to prove that knowledge base internally consistent.

Its scopes divide into two kinds. **Seven name a file-based entity type**: codex, artifacts, doctrines, knights, watchers, the Glossary (lore codex show conceptual-entities-glossary), and Rites (lore codex show conceptual-entities-rite). **Three cut across entity types instead**: `schemas` validates every entity file's shape against its JSON Schema, `bindings` audits the codex↔code `binds:` edge, and `voice` audits canonical codex prose. A scope of the second kind names a question asked of the project, not a type of file it holds.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- The caller may optionally specify one or more scopes via `--scope`.

## Invocation

```
lore health
lore health --scope doctrines knights
lore health --scope watchers
lore health --scope glossary
lore health --scope codex glossary
lore health --scope bindings
lore health --scope bindings codex
lore health --scope rites
lore health --scope codex rites
lore health --scope voice
lore health --scope codex voice
lore health --json
lore health --scope codex --json
```

`--scope` accepts one or more space-separated tokens from the set: `codex`, `artifacts`, `doctrines`, `knights`, `watchers`, `schemas`, `glossary`, `bindings`, `rites`, `voice`. Omitting `--scope` runs every scope including `schemas`, `glossary`, `bindings`, `rites`, and `voice`.

`--json` prints machine-readable JSON to stdout instead of the human-readable table. The report file is always written regardless of `--json`.

## Steps

### 1. Resolve scope

The system determines which scopes to run:
- No `--scope`: all scopes run, including `schemas`, `glossary`, `bindings`, `rites`, and `voice`.
- `--scope SCOPE [SCOPE ...]`: only the listed scopes are checked; all others are skipped entirely.
- Valid scope tokens: `codex`, `artifacts`, `doctrines`, `knights`, `watchers`, `schemas`, `glossary`, `bindings`, `rites`, `voice`.

### 2. Run per-scope checkers

Each in-scope checker runs independently. A failure in one checker (e.g., the watchers directory is missing) does not abort other checkers — the failure is recorded as a `scan_failed` error and scanning continues.

#### Codex checks

- **Missing `id` field** (error): any `.md` file under `.lore/codex/` whose frontmatter lacks an `id` field.
- **Broken `related` link** (error): any codex document whose `related` list names an ID that does not exist in the codex.
- **Island node** (warning): any codex document that no other document references in its `related` list.

#### Artifact checks

- **Missing required frontmatter** (error): any `.md` file under `.lore/artifacts/` missing `id`, `title`, or `summary`. Reports the first absent field. `lore artifact list` silently skips these files — `lore health` makes the gap visible.

#### Doctrine checks

- **Orphaned file** (error): any `.yaml` with no matching `.design.md`, or any `.design.md` with no matching `.yaml`.
- **Broken knight ref in step** (error): any doctrine step whose `knight` field names a knight not present on disk (and not soft-deleted as `<name>.md.deleted`).
- **Broken artifact ref in step notes** (error): any doctrine step whose `notes` field contains a token matching the artifact ID pattern (`fi-[a-z0-9-]+`) that does not exist in the artifact index.

#### Knight checks

- **Missing file** (error): any active (non-closed, non-deleted) mission that names a knight whose `.md` file is absent from disk. A `.md.deleted` file means intentional soft-delete — not an error. A completely absent file is an error.

#### Glossary checks (scope: `glossary`)

The glossary scope runs two families of check over `.lore/codex/glossary.yaml`. See conceptual-entities-glossary (lore codex show conceptual-entities-glossary) for the entity model.

1. **Schema validation.** `lore.schemas.validate_entity_file(path, "glossary")` validates the file against `lore://schemas/glossary`. Schema errors are always errors (never warnings) and short-circuit the intra-glossary checks for that file (the unsafe-to-interpret rule). The `glossary` schema kind also runs as part of `--scope schemas`.
2. **Intra-glossary collisions:**
   - **`duplicate_keyword`** (error): two items share a casefolded `keyword`. `id=<glossary path>`, `detail="'<kw>' appears in items[i] and items[j]"`.
   - **`alias_keyword_collision`** (warning): an alias of item A casefold-equals the keyword of item B (B != A). `detail="alias '<a>' on '<kw>' collides with keyword '<other>'"`.
   - **`do_not_use_collision`** (error): a `do_not_use` term casefold-equals any other item's `keyword` or any `alias`. `detail="'<term>' in do_not_use of '<kw>' collides with keyword/alias '<other>'"`.

`--scope glossary` runs only those two families (no codex `related` checks, no doctrine checks, etc.). `--scope codex glossary` runs codex reference-integrity checks AND the glossary checks (multi-scope per ADR-012). `--scope schemas` continues to validate every schema kind, including `glossary`, so a malformed glossary surfaces in `--scope schemas` even without `glossary` in the scope set.

A missing `.lore/codex/glossary.yaml` is NOT an error — empty glossary is a valid state. Schema validation of an absent file is a no-op for this kind. The intra-glossary checks no-op on an empty/absent file.

There is no cross-codex deprecated-term scan. The `do_not_use` schema field on glossary items is now a documentation hint only — it is still validated for shape and still drives the intra-file `do_not_use_collision` check, but no automated audit scans codex bodies for occurrences of deprecated terms. The replacement signal during authoring is `lore codex show`'s glossary auto-surface, which lists canonical keywords and aliases inline.

#### Watcher checks

- **Invalid YAML** (error): any `.yaml` file under `.lore/watchers/` (excluding `.yaml.deleted` files) that fails YAML parsing. Reports the line number from the parse error.
- **Broken doctrine ref** (error): any watcher whose `action` field names a doctrine not found on disk.

#### Schema checks (scope: `schemas`)

Schema checks validate the *shape* of every on-disk entity file against its JSON Schema. They are complementary to the reference-integrity checks above — schema checks answer "is this file a valid `X`?", reference checks answer "does this link resolve?". Schema definitions live in `src/lore/schemas/*.yaml` and are the single authoritative contract shared with create-time validators in `doctrine.py`, `knight.py`, `watcher.py`, and `artifact.py` (see tech-arch-schemas).

Every schema violation is an **error** (never a warning) and each emits a `HealthIssue` with `check="schema"` and three extra fields: `schema_id`, `rule`, `pointer`. Multiple violations per file are collected via `jsonschema.Draft202012Validator.iter_errors` — no short-circuit.

Per-kind coverage:

- **`doctrine-yaml`** — every `.lore/doctrines/**/*.yaml` validated against `lore://schemas/doctrine-yaml`.
- **`doctrine-design-frontmatter`** — frontmatter of every `.lore/doctrines/**/*.design.md` validated against `lore://schemas/doctrine-design-frontmatter`.
- **`knight`** — frontmatter of every `.lore/knights/**/*.md` validated against `lore://schemas/knight-frontmatter`.
- **`watcher`** — every `.lore/watchers/**/*.yaml` validated against `lore://schemas/watcher-yaml`.
- **`codex`** — frontmatter of every `.lore/codex/**/*.md` validated against `lore://schemas/codex-frontmatter` (optional `related`, `binds`, and `rites` arrays accepted; mapping form rejected). A malformed `rites:` (non-array, duplicates, empty string) is a schema error with `entity_type="codex"`. Source docs under `.lore/codex/sources/` are validated against `lore://schemas/codex-source-frontmatter` via the in-loop per-file override. Docs under `.lore/codex/transient/` are validated against the **packaged** `lore://schemas/codex-frontmatter` via a second in-loop per-file override — never the merged one (`decisions-019-overlay-scope-stops-at-transient`). Both codex kinds are **overlay-aware** outside `transient/`: when the project ships a `.lore/custom-schemas/<kind>.yaml` overlay, the validator is the merged schema (packaged default + overlay), so declared custom keys pass while undeclared keys (e.g. a typo) still error — see "Project-local schema overlays" below.
- **`artifact`** — frontmatter of every `.lore/artifacts/**/*.md` validated against `lore://schemas/artifact-frontmatter`.
- **`glossary`** — the single file `.lore/codex/glossary.yaml` (full-YAML, not frontmatter) validated against `lore://schemas/glossary`. Unique among schema kinds: a literal file glob, not a `**/*.yaml` walk.
- **`main-rite`** — every `.lore/rites/main/**/*.yaml` (full-YAML, recursive) validated against `lore://schemas/main-rite`. Missing required fields (`id, title, summary, trigger, nodes, conclusions`) → error.
- **`shared-step`** — every `.lore/rites/shared/**/*.yaml` (full-YAML, recursive) validated against `lore://schemas/shared-step`. Missing `id, title, summary, do` → error; any branching/conclusions/retrieval key (`nodes`, `then`, `conclusions`, `use`, `goto`, `trigger`) → `additionalProperties` error, declaratively enforcing the pure-step / single-exit rule (`summary` is allowed — the universal what-it-does line — but `trigger` stays MAIN-rite-only).

Special error rules (beyond JSON Schema keywords):

- **`rule="yaml-parse"`** — file's YAML is unparseable. Single error emitted; validation of that file stops. `pointer="/"`, `message` is the YAML parser message.
- **`rule="missing-frontmatter"`** — frontmatter-validated file has no `---` block. Single error, `pointer="/"`, message `"File has no YAML frontmatter block"`.
- **`rule="read-failed"`** — I/O or Unicode failure on read. Single error, `pointer="/"`, `message=str(exc)`. Validation continues to the next file.

Files that the existing entity loaders today silently skip (unpaired doctrine designs, frontmatter-less knights, malformed artifacts) are surfaced here as schema errors instead of being silently dropped.

##### Project-local schema overlays

A project may add custom frontmatter keys to its codex docs by declaring them once in an add-only overlay at `.lore/custom-schemas/<kind>.yaml` (v1 kinds: `codex-frontmatter`, `codex-source-frontmatter`). For the two codex kinds the schema audit resolves its validator through the project-aware health seam `project_get_validator(kind, project_root)` (re-exporting `schemas.project_validator_for`); the other seven kinds use the kind-only `get_validator(kind)` seam. Both are internal module-level monkeypatch seams (neither is public API); the kind split — project-aware for the two codex kinds, kind-only for the rest — is the routing rule. The merged validator adds the overlay's declared properties (and any overlay `required` entries) onto the packaged schema while keeping `additionalProperties: false`. Effect on the audit:

- A **canonical or source** doc carrying a **declared** custom key (e.g. `owner:` named in the overlay) passes.
- An **undeclared** key — including a typo of a declared key (`onwer:`) — still errors as `additionalProperties`, now listing the custom key among the allowed keys.
- A **canonical or source** doc missing an overlay-`required` key errors as `required`, exactly like a missing packaged field.
- A doc under `.lore/codex/transient/` is **out of overlay scope** (`decisions-019-overlay-scope-stops-at-transient`): an overlay `required` field never fires on it, and because the packaged schema keeps `additionalProperties: false`, a transient doc that *carries* a declared custom key is rejected as `Unknown property`. Transient docs are exempt from the overlay, not from validation — a transient doc missing `summary` is still a schema error.
- A **malformed** overlay does not blind the transient subtree: it never consulted the overlay, so its packaged validation still runs while the canonical kind reports its single `scan_failed` (below).
- With **no** overlay present, output is byte-for-byte identical to the packaged-only behaviour.

A **malformed overlay** — unparseable YAML, non-mapping top-level, a property colliding with a packaged field, or a `required` entry not declared in the overlay — raises `OverlayError` during validator construction. `_check_schemas` catches it in its existing validator-construction `try/except` and emits **one** `scan_failed` error naming the overlay (`severity="error"`, `check="scan_failed"`, `detail="<overlay-path>: <reason>"`, `schema_id="lore://schemas/<kind>"`); the per-file loop for that kind is skipped, every other kind and check still runs, and no stack trace escapes `lore health`. The overlay file itself is project config, not a codex entity, and is never walked as a `.md` doc (`decisions-018-overlays-are-path-discovered-config`). The resolver and merge semantics live in `tech-arch-schemas`.

#### Bindings checks (scope: `bindings`)

The bindings scope audits the optional `binds:` frontmatter field that codex entries use to declare which on-disk paths they govern. The audit answers the integrity question implied by ADR-006 (lore codex show decisions-006-id-references): when a refactor renames or deletes a file, does any codex entry still claim to govern it? See conceptual-workflows-impacts (lore codex show conceptual-workflows-impacts) for the field's read-side semantics; this scope is the write-side integrity check.

The checker reuses the same codex binds index that `lore impacts` consumes — there is no second walk of the codex. Each `binds:` string is classified literal-vs-glob by the impacts-module rule (any of `*`, `?`, `[` in the string → glob; otherwise → literal). Schema-level validation of binds strings (non-empty, no `..`, not absolute, no duplicates) stays in `--scope schemas`; the bindings scope assumes well-formed input and audits filesystem truth only.

Two checks:

- **`dead_binding`** (error): a literal `binds:` string whose resolved path does not exist on disk. Resolution is anchored at `find_project_root()`; symlinks are followed only when the resolved target stays inside the project root. `HealthIssue(severity="error", entity_type="codex", id=<codex-id>, check="dead_binding", detail='"<binding>" — file not found')` for missing files; `detail='"<binding>" — resolves outside project root'` for symlink-escapers. Each dead literal in a single entry's `binds:` array emits its own row.
- **`empty_glob_binding`** (warning): a glob `binds:` pattern that matches zero files in the repo. Glob expansion walks the project root once per `health_check()` call (lazy — only built if at least one glob is seen), skipping `.git/`, `.lore/`, `node_modules/`, `__pycache__/`, and any symlink whose target escapes the repo. Pattern matching reuses the regex translation that `lore impacts` uses, so `**`, `*`, `?`, `[...]` semantics are byte-identical to the impacts command. `HealthIssue(severity="warning", entity_type="codex", id=<codex-id>, check="empty_glob_binding", detail='"<pattern>" — pattern matches zero files')`. A glob matching one or more files is silent.

A codex entry with no `binds:` field, or with `binds: []`, emits zero rows. A malformed `binds:` entry is silently skipped — the codex binds index already filters it, and `--scope schemas` reports the malformed shape separately.

Severity split is deliberate: `dead_binding` flips exit code 1 (refactor-induced governance drift fails CI), `empty_glob_binding` does not (forward-looking globs during feature bootstrap stay green). The warning never escalates to an error.

`--scope bindings` runs only this audit. `--scope bindings codex` runs both (multi-scope per ADR-012). `lore health` with no `--scope` runs bindings as part of the default-all-scopes execution.

#### Rite checks (scope: `rites`)

The rites scope audits the Rite entity (lore codex show conceptual-entities-rite) — main rites under `.lore/rites/main/` and shared steps under `.lore/rites/shared/`, both scanned **recursively** (`main/**/*.yaml`, `shared/**/*.yaml`). `.yaml.deleted` files are skipped (soft-delete). The checker is `health._check_rites(project_root)`; it walks each main rite's node-graph once. Rite identity is the `id:` field, resolved across the whole tree — `use:`, the shared-step index, and the orphan check all match by id regardless of subfolder. Schema validation of the rite YAML shape runs under `--scope schemas` (see Schema checks below), not here — this scope covers id-collision, reference integrity, graph well-formedness, and the orphan asymmetry. Orphan rules differ for main vs shared, and that asymmetry is the design point: a main rite is found via `lore rite list`, a shared step is reachable only via `use:`.

Every rite issue is a `HealthIssue(severity, entity_type, id, check, detail, schema_id=None, rule=None, pointer=None)` with `entity_type="rites"`; `schema_id`/`rule`/`pointer` are `null` (only `check="schema"` rows populate those). `id` is the rite id for graph/orphan checks, and the codex doc id for the `dangling_codex_rite` check.

**Id collision (error — flips exit 1):**

- **`duplicate_rite_id`** — the same `id:` appears in two files anywhere across the `main/` + `shared/` tree (two subfolders, or `main/` vs `shared/`). Rite ids are globally unique like codex ids; a collision makes `use: x` ambiguous. `detail='rite id "<id>" defined in multiple files: <rel-path>, <rel-path>'`, `id=<rite-id>`.

**Reference integrity (error — flips exit 1):**

- **`dangling_use`** — a node `use:`es a shared-step id that matches no shared step anywhere under `shared/` (resolved by id, recursively). `detail='node "<node-id>" uses missing shared step "<use-id>"'`, `id=<main-rite-id>`.
- **`dangling_then`** — a `then`/`goto` points to a node id or conclusion key that exists nowhere in the rite. `detail='node "<node-id>" routes to unknown target "<target>"'`, `id=<main-rite-id>`.
- **`dangling_codex_rite`** — a codex `rites:` field names a non-existent rite id (codex-side; mirrors `related`/`binds` validation). `detail='codex "<codex-id>" references missing rite "<rite-id>"'`, `id=<codex-id>`. This check runs under **both** the `rites` and `codex` scopes — it is a codex reference-integrity check that depends on the rite index, so it fires whenever either scope is active (mirrors how `bindings` ids are codex-typed but auditable on their own scope).

**Graph well-formedness (error — per main rite):**

- **`no_entry_node`** — every node has an inbound edge, so there is no start. `detail='no entry node — every node has an inbound edge'`.
- **`multiple_entry_nodes`** — more than one node has no inbound edge → ambiguous start. `detail='multiple entry nodes: <id>, <id>'`.
- **`unreachable_node`** — nothing routes to it and it is not the entry. `detail='node "<node-id>" is unreachable'`.
- **`conclusion_never_reached`** — a `conclusions:` key that no `then`/`goto` targets. `detail='conclusion "<key>" is defined but never reached'`.
- **`undefined_conclusion`** — a `then`/`goto` names a conclusion-like target with no `conclusions:` entry and no matching node id. `detail='node "<node-id>" routes to "<target>" — no node or conclusion'`. `undefined_conclusion` and `dangling_then` are the two faces of "target resolves to nothing", emitted as distinct check names so the report distinguishes "looked like a conclusion key" from "looked like a node id".

**Orphans — the asymmetry (design point):**

- **`orphan_shared_step`** (**warning**) — no main rite `use:`es this shared step (matched by id across the recursive tree). Shared exists only to be used; a warning, not an error (does not flip exit 1, matching codex `island_node`). `detail='no main rite uses this shared step'`, `id=<shared-step-id>`.
- **Orphan main rite — NOT flagged.** A main rite that no codex `rites:` points to emits **no issue**. It is found via `lore rite list`; `rites:` is secondary discovery (decisions-014-link-direction constraint 4). Same posture as inbound-orphan sources.

`--scope rites` runs only these rite checks. `--scope codex rites` runs codex reference-integrity AND rite checks (multi-scope per ADR-012); the `dangling_codex_rite` check fires under both. `lore health` with no `--scope` runs rites as part of the default-all-scopes execution.

#### Voice checks (scope: `voice`)

The voice scope audits canonical codex prose against the codex voice rules. Those rules are normative in one place: `lore artifact show codex-voice` holds the rule table, the two tests that settle a borderline sentence, and the worked examples. This section describes what the checker matches and how it reports; it does not restate the rules. `decisions-020-codex-voice-is-enforced` records the decision behind the artifact and the severity contract below.

The checker is `health._check_voice(project_root)`. It walks `.lore/codex/**/*.md` once and reads the `summary` frontmatter value plus the body. It does not read any other frontmatter value, fenced code blocks, inline code spans, or the generated `transient/health-*.md` reports — a report that quotes a violation has not committed one. Every issue is a `HealthIssue(severity="warning", entity_type="codex", id=<codex-id>, check=<voice check name>, detail='line <n>: "<phrase>" — <label>')` with `schema_id`, `rule`, and `pointer` all `null`. Rows sort by codex id, then line number, then the order the patterns are declared in.

Five checks run. Each is skipped in the layers whose purpose is the construct it flags:

| Check | Rules | Skipped in |
|---|---|---|
| `voice_past_narration` | V1, V2 | `decisions/`, `transient/`, `sources/`, `vision/` |
| `voice_expiry_hedge` | V3 | `transient/`, `sources/`, `vision/` |
| `voice_forward_promise` | V4 | `transient/`, `sources/`, `vision/` |
| `voice_dangling_deixis` | V5 | `sources/`, `vision/` |
| `voice_sales_register` | V9 | `sources/`, `vision/` |

A skip is a property of the layer directory, not of the document. No frontmatter key, comment marker, or filename pattern exempts an individual file (`decisions-020-codex-voice-is-enforced` constraint 3). Four of the ten voice rules — V6, V7, V8, and V10 — need judgment no pattern match supplies, and no check covers them.

**Severity: warnings only.** No `voice_*` check emits an error, and no `voice_*` id sits in `_ESCALATED_WARNING_CHECKS`, so `--scope voice` never raises the exit code. `decisions-020-codex-voice-is-enforced` fixes that as a contract: six matched rules cannot assert a verdict on four that need a reader, and a heuristic that breaks a build teaches authors to drop the scope from their `--scope` list. Promoting any `voice_*` issue to an error takes its own ADR. A voice warning is a prompt to read the flagged sentence against the two tests in the artifact, not proof of a defect.

**`vision/` is skipped, not exempt.** All five checks skip the layer because no rule has been decided for a document that states intent about a system nobody has built. `decisions-020-codex-voice-is-enforced` records the skip as an open question: a `vision/` document raises no voice warning and receives no voice guarantee. Ending the skip takes a decision on whether such a document marks intent explicitly or drops its forward-looking prose.

`--scope voice` runs only these checks. `--scope codex voice` runs codex reference-integrity AND voice checks (multi-scope per ADR-012). `lore health` with no `--scope` runs voice as part of the default-all-scopes execution.

### 3. Collect results

All checkers return a list of `HealthIssue` objects. The system partitions them into errors and warnings and assembles a `HealthReport`.

### 4. Write markdown report

The system always writes a markdown report to `.lore/codex/transient/health-{timestamp}.md`, even on clean runs. The timestamp uses UTC ISO 8601 with colons replaced by hyphens for filesystem compatibility (e.g., `health-2026-04-09T14-32-00.md`).

**Self-consistency.** Because the report lands in `transient/`, it is overlay-exempt (`decisions-019-overlay-scope-stops-at-transient`): an overlay `required` custom field never makes `lore health` fail on its own output, however many reports have accumulated on disk. The exit code is independent of how many times `lore health` has run.

Report frontmatter:
```yaml
id: health-2026-04-09T14-32-00
title: Health Report — 2026-04-09T14:32:00
summary: lore health report generated at 2026-04-09T14:32:00 UTC
```

Report body on issues found: a markdown table with columns Severity, Entity Type, ID, Check, Detail, followed by a `## Schema validation` section listing every schema error grouped by `kind` then file path. When there are zero schema errors, the section reads `No schema errors.`.

Report body on clean run: `No issues found.`

No retention policy is enforced — reports accumulate.

### 5. Render output

**Text mode (no `--json`):**

Issues present:
```
SEVERITY  ENTITY_TYPE  ID                CHECK
ERROR     doctrines    feat-auth         broken_knight_ref: 'senior-engineer' not found (step 2)
ERROR     watchers     on-quest-close    broken_doctrine_ref: 'feat-payments' not found
ERROR     rites        issue-refund      dangling_use: node "get-contact" uses missing shared step "read-contact-info"
ERROR     rites        ops-refunds       dangling_codex_rite: codex "ops-refunds" references missing rite "issue-refund"
WARNING   codex        proposals-draft   island_node: no documents link here
WARNING   rites        read-contact-info orphan_shared_step: no main rite uses this shared step
```

Schema violations use a dedicated multi-line ERROR block followed by a summary line:

```
ERROR .lore/knights/default/feature-implementation/pm.md
  kind: knight
  schema: lore://schemas/knight-frontmatter
  rule: additionalProperties
  path: /stability
  message: Unknown property 'stability' — allowed keys are id, title, summary.
Schema validation: 1 error
```

Clean run:
```
Health check passed. No issues found.
Schema validation: 0 errors
```

**JSON mode (`--json`):**

Issues present:
```json
{
  "has_errors": true,
  "issues": [
    {
      "severity": "error",
      "entity_type": "doctrines",
      "id": "feat-auth",
      "check": "broken_knight_ref",
      "detail": "'senior-engineer' not found (step 2)",
      "schema_id": null,
      "rule": null,
      "pointer": null
    },
    {
      "severity": "error",
      "entity_type": "knight",
      "id": ".lore/knights/default/feature-implementation/pm.md",
      "check": "schema",
      "detail": "Unknown property 'stability' — allowed keys are id, title, summary.",
      "schema_id": "lore://schemas/knight-frontmatter",
      "rule": "additionalProperties",
      "pointer": "/stability"
    },
    {
      "severity": "warning",
      "entity_type": "rites",
      "id": "read-contact-info",
      "check": "orphan_shared_step",
      "detail": "no main rite uses this shared step",
      "schema_id": null,
      "rule": null,
      "pointer": null
    }
  ]
}
```

Schema errors are strictly additive: every `HealthIssue` record carries the three new fields `schema_id`, `rule`, `pointer`, which are `null` for non-schema checks and populated for `check="schema"` rows.

Clean run:
```json
{
  "has_errors": false,
  "issues": []
}
```

### 6. Exit

- Exit `1` if `report.has_errors` is `True` (any error found).
- Exit `0` if clean or warnings-only.

## Python API

```python
from lore.models import health_check, HealthReport, HealthIssue
from pathlib import Path

report = health_check(project_root=Path("."), scope=None)
report = health_check(project_root=Path("."), scope=["codex"])
report = health_check(project_root=Path("."), scope=["doctrines", "watchers"])
report = health_check(project_root=Path("."), scope=["bindings"])
report = health_check(project_root=Path("."), scope=["rites"])
report = health_check(project_root=Path("."), scope=["codex", "rites"])
report = health_check(project_root=Path("."), scope=["voice"])

report.has_errors       # bool
report.errors           # tuple[HealthIssue, ...]
report.warnings         # tuple[HealthIssue, ...]
report.issues           # tuple[HealthIssue, ...] — errors then warnings
```

`health_check()` never prints to stdout or stderr. The report file is written by the CLI handler after calling `health_check()`, not inside `health_check()` itself. Python API callers that do not want the file side effect omit the `_write_report` call.

`health_check` is in `lore.models.__all__`. `HealthIssue` and `HealthReport` are also in `__all__`.

## Error Paths

| Condition | Behaviour |
|-----------|-----------|
| Value passed to `--scope` outside the token set | The flag is `click.Choice`-guarded, so Click raises `BadParameter` (a `UsageError` subclass) before the handler body runs. Exit **2**, stderr: `Error: Invalid value for '--scope': 'xyz' is not one of 'codex', 'artifacts', 'doctrines', 'knights', 'watchers', 'schemas', 'glossary', 'bindings', 'rites', 'voice'.` Adding a token to the set is non-breaking; rewording the message or changing the exit code is a breaking contract change (`decisions-017-constrained-flags-use-click-choice`, conceptual-workflows-error-handling). |
| Unknown token in the positional `extra_scopes` argument | The positional argument carries no `click.Choice`, so the token reaches `health_check(scope=...)`, which raises `ValueError`. The handler rewrites the prefix and exits **1**, stderr: `Invalid scope: 'xyz'. Valid scopes: codex, artifacts, doctrines, knights, watchers, glossary, schemas, bindings, rites, voice.` This is the only path that produces the exit-1 `Invalid scope:` text. |
| Authoritative schema file missing at load time | Propagated as a `scan_failed` error naming the missing schema id. No partial false-green. |
| Entity directory missing | `scan_failed` error added for that entity type; other types continue |
| Report directory missing | Created if absent (`.lore/codex/transient/` is created on first run) |
| Overlay declares a required field, transient doc lacks it | Not an error — `transient/` is out of overlay scope; the doc is validated against the packaged schema alone |
| No entities of a type on disk | Clean result for that type (no issues) |

## Scope Isolation

When `--scope` is provided, only the named scopes run. Nothing outside them is scanned. Example: `lore health --scope watchers` never reads codex, artifact, doctrine, or knight files.

## Out of Scope

- Missions and quests (DB entities) are outside the health perimeter.
- Auto-repair (`--fix`) is a post-MVP feature.
- Scheduling or periodic execution is handled by watchers or CI.

## Related

- health-check-prd-final (lore codex show health-check-prd-final)
- health-check-tech-spec (lore codex show health-check-tech-spec)
- conceptual-workflows-error-handling (lore codex show conceptual-workflows-error-handling)
- conceptual-workflows-json-output (lore codex show conceptual-workflows-json-output)
- decisions-012-multi-value-cli-param-convention (lore codex show decisions-012-multi-value-cli-param-convention)
- decisions-014-link-direction (lore codex show decisions-014-link-direction) — the codex → rite edge the dangling_codex_rite check audits
- conceptual-entities-rite (lore codex show conceptual-entities-rite) — the Rite entity these checks audit
- ref-lore_cli-commands (lore codex show ref-lore_cli-commands)
- ref-lore_api-core (lore codex show ref-lore_api-core)
