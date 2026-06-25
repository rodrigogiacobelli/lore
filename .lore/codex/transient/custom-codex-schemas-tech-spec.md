---
id: custom-codex-schemas-tech-spec
title: Custom Codex Frontmatter Schemas — Tech Spec
summary: >
  Architect Tech Spec for project-aware custom codex frontmatter overlays. Adds
  a single resolver layer in lore.schemas that merges packaged codex / codex-source
  schemas with .lore/custom-schemas/<kind>.yaml overlays (add-only, strict,
  defaults-authoritative, mtime-cached), wires the merged validator into both
  lore health (_check_schemas) and lore codex create/edit, surfaces malformed
  overlays as clean scan_failed health issues, and seeds a scaffolding skill.
  Every decision traces to a PRD FR. Honors ADR-010/011 parity and ADR-006.
type: tech-spec
related:
  - custom-codex-schemas-prd
  - custom-codex-schemas-technical-map
  - tech-arch-schemas
  - conceptual-workflows-health
  - decisions-010-public-api-stability
  - decisions-011-api-parity-with-cli
  - decisions-014-link-direction
  - decisions-006-no-seed-content-tests
  - standards-dry
  - standards-dependency-inversion
---
# Custom Codex Frontmatter Schemas — Tech Spec

**Author:** Architect
**Date:** 2026-06-18
**Supersedes:** _none — first Tech Spec for this feature_
**Input:** `custom-codex-schemas-prd`

> This Tech Spec is self-contained. It implements the locked PRD decisions:
> strict declared-only (`additionalProperties` stays `false`), add-only (defaults
> protected), per-kind overlays at `.lore/custom-schemas/<kind>.yaml`, no new CLI
> command group, plus a scaffolding skill. The human Spec Gate is skipped; this
> spec flows to Tech Planning ∥ Codex Apply via the ADR Enforcer.

---

## Core Architectural Decisions

| Priority | Decision | Choice | Rationale (PRD trace) |
|----------|----------|--------|-----------------------|
| Critical | Where the merge logic lives | One new resolver module-region inside `lore.schemas` (`schemas/__init__.py`): `resolve_merged_schema(kind, project_root)` → dict, plus `merge_overlay(base, overlay, kind)` (pure) and `project_validator_for(kind, project_root)` → `Draft202012Validator`. No second copy. | DRY (`standards-dry`): `lore.schemas` is the single authoritative validation home. PRD NFR Compatibility: "resolver layer added inside lore.schemas so both consumers share one implementation." |
| Critical | Overlay discovery contract | File at `.lore/custom-schemas/<kind>.yaml`, where `<kind>` ∈ {`codex-frontmatter`, `codex-source-frontmatter`} for v1. Discovered by filename, zero config. Path helper `paths.custom_schemas_dir(root)` + `paths.custom_schema_path(root, kind)`. | FR-1, FR-2. Mirrors existing `glossary_path` / `config_path` helper pattern (`tech-arch-source-layout`). |
| Critical | Merge semantics | Add-only: overlay `properties` keys merged in; overlay `required` appended; `additionalProperties` forced to `false`; any overlay property colliding with a packaged property rejected (raises `OverlayError`); every overlay `required` entry must name a property the same overlay declares. | FR-4, FR-5, FR-6, FR-7. Defaults authoritative — the merge never reads a value out of the packaged `properties`/`required`, only adds. |
| Critical | Cache strategy | `project_validator_for` cached on key `(kind, str(project_root), overlay_mtime_ns)`. `overlay_mtime_ns` = `os.stat(overlay).st_mtime_ns` or sentinel `-1` when no overlay exists. Edited overlay → new key → re-read within a long-running process (Realm). | FR-3. The kind-only `lru_cache` on `_validator_for` cannot be reused (project-blind). |
| Critical | Health wiring | `_check_schemas`'s `get_validator` seam stays. A new module-level seam `project_get_validator(kind, project_root)` is added in `health.py` re-exporting `schemas.project_validator_for`. `_check_schemas` calls `project_get_validator(kind, project_root)` for the two codex kinds (`codex-frontmatter`, `codex-source-frontmatter`) and the existing `get_validator(kind)` for all other kinds. | FR-8, FR-10. Keeps the monkeypatch seam (Scout note) and the in-loop source override unchanged in shape. |
| Critical | Codex create/edit wiring | `validate_entity` gains an optional keyword `project_root: Path | None = None`. When provided, it validates against `project_validator_for(kind, project_root)` for the two codex kinds; when `None` (or kind not overlay-eligible) it falls through to today's packaged validator. `codex.py` create/edit pass `project_root=project_root` (already in scope). | FR-9. ADR-011 parity: same merged result whether reached via CLI or `lore.api`. ADR-010: keyword-with-default is an additive minor bump to the public `validate_entity`. |
| Critical | Malformed overlay handling | `resolve_merged_schema` raises `OverlayError` (new, subclass of `ValueError`) on: unparseable YAML, non-mapping top-level, missing/non-mapping `properties`, collision (FR-7), `required` entry not declared in the overlay (FR-5). Health's existing `try/except Exception` around `get_validator` catches it and emits one `scan_failed` issue naming the overlay; other checks continue. Codex create/edit let `OverlayError` propagate as a `ValueError` (existing create/edit error contract). | FR-10. Never a stack trace from `lore health`; `lore codex` already surfaces `ValueError`. |
| Important | Scaffolding skill | New skill `new-custom-schema` at `.lore/skills/new-custom-schema/` (seeded from `src/lore/defaults/skills/new-custom-schema/`). Collects kind + field names/types/required, enforces add-only rules before writing, writes `.lore/custom-schemas/<kind>.yaml`, then runs `lore health` for confirmation. | FR-11, FR-12, FR-13. Markdown-only src impact, reconciled by Defaults Review. |
| Important | No new CLI command | Discovery is convention + the skill + docs. `validate_entity`'s new keyword and the resolver are the only API additions. | PRD Out of Scope: no `lore schema ...` group. `tech-cli-entity-crud-matrix` confirms no codex CLI write command beyond create/edit. |
| Deferred | Overlays for knight/artifact/doctrine kinds | Resolver is kind-generic; extend the discovery kind allow-list later. | PRD Post-MVP. |
| Deferred | Per-doc-type overlays (tech-spec vs ADR) | doc_type resolves by path/group, not frontmatter; no clean hook today. | PRD Post-MVP. |
| Deferred | `lore codex schema --show` inspect path | Not required for the two MVP workflows. | PRD Post-MVP. |

---

## Data Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | Plain YAML overlay files on disk under `.lore/custom-schemas/`. No DB rows, no migration. | PRD: per-project, low frequency, convention-discovered. Overlays are project files, not Lore state. |
| Parsing | `yaml.safe_load` only. | NFR Security: overlays are local files; `safe_load` bounds blast radius. Matches `load_schema`. |
| Schema of an overlay | A JSON-Schema fragment: top-level mapping with `properties` (object, required) and optional `required` (array of strings). All other top-level keys ignored (we never copy `$id`, `additionalProperties`, etc. from the overlay). | Add-only: only `properties` and `required` are honored; the merge synthesizes everything else from the packaged base. |
| Merge output | A deep-copied dict from the packaged base, with overlay `properties` injected, overlay `required` appended, `additionalProperties` pinned `false`, and `$id` left as the packaged `$id`. | FR-6, FR-7. Packaged base never mutated (cache integrity). |
| Validation engine | Existing `jsonschema.Draft202012Validator` over the merged dict. | No new dependency. The merged dict is a valid draft-2020-12 schema by construction. |

---

## API & Communication

| Decision | Choice | Rationale |
|----------|--------|-----------|
| New public names | `resolve_merged_schema(kind, project_root)`, `project_validator_for(kind, project_root)`, `OverlayError`. Added to the `# --- Schemas ---` import block in `api.py` and to `lore.api.__all__`; the facade stays a pure re-export module (zero `def`/`class`) per `tech-arch-api-facade`. `validate_entity` gains keyword `project_root`. | ADR-010: any new public name is deliberate and re-exported; `validate_entity` is already public (it is in `lore.api.__all__` and `schemas.__all__` today), the keyword is additive (minor bump). |
| Parity | The merged validator is reached identically from CLI (`lore health`, `lore codex create/edit`) and from `lore.api` (`validate_entity(kind, data, project_root=...)`, `project_validator_for`). | ADR-011: behaviourally equivalent; no consumer re-implements the merge. |
| Dependency direction | Resolver imports only stdlib (`os`, `pathlib`, `copy`), `yaml`, `jsonschema`, and `lore.paths` for the overlay path helper. `lore.paths` has no `lore.*` cycle into schemas. `validators.py` stays untouched (zero `lore.*` imports preserved). | `standards-dependency-inversion`. The resolver needs `project_root` but reaches it as a passed-in `Path`, not by importing CLI/config layers. |
| Error response format | Health: `HealthIssue(severity="error", check="scan_failed", detail="<overlay-path>: <reason>", schema_id="lore://schemas/<kind>")`. Codex create/edit: a malformed overlay makes `validate_entity(kind, meta, project_root=root)` raise `OverlayError` during validator construction (before it returns its `list[SchemaIssue]`); because `OverlayError` subclasses `ValueError`, it propagates unchanged out of `create_document` / `update_document`, both of which already document "Raises `ValueError` on any … schema failure" (`codex.py:132`). Ordinary validation failures (declared-key typo, missing required) still return the `list[SchemaIssue]`, which create/edit join into the existing `ValueError("\n".join(i.message …))`. | FR-10. Matches the existing `scan_failed` pattern (`health.py:558`) and the codex create/edit `ValueError` contract (`codex.py:153`). |
| Versioning | Minor (additive) version bump: new public names + new keyword with default. No breaking change; no-overlay behavior is byte-for-byte identical. | ADR-010 semver table; FR-2, NFR Reliability. |

---

## Implementation Patterns

### Naming Conventions

**Files:** overlay = `.lore/custom-schemas/<kind>.yaml` (kind matches packaged schema kind exactly).
**API / CLI:** no new command. Public functions: `resolve_merged_schema`, `project_validator_for`. Health seam: `project_get_validator`.
**Code:** resolver lives in `src/lore/schemas/__init__.py`; pure merge helper `merge_overlay`; exception `OverlayError(ValueError)`. Path helpers in `paths.py` follow the `glossary_path`/`config_path` shape.

### Error Handling

- `resolve_merged_schema(kind, project_root)`:
  - No overlay file → return packaged `load_schema(kind)` unchanged (deep-copied not required; callers don't mutate).
  - Unparseable YAML → `OverlayError(f"{overlay_path}: invalid YAML: {exc}")`.
  - Top-level not a mapping → `OverlayError(f"{overlay_path}: overlay must be a mapping")`.
  - `properties` missing or not a mapping → `OverlayError(f"{overlay_path}: overlay 'properties' must be a mapping")`.
  - Collision: overlay property key already in packaged `properties` → `OverlayError(f"{overlay_path}: property '{key}' collides with a packaged field and cannot be overridden")`.
  - `required` entry not declared in overlay `properties` → `OverlayError(f"{overlay_path}: required entry '{name}' is not declared in this overlay")`.
- `project_validator_for` builds the merged schema via `resolve_merged_schema`, constructs the validator, caches it; `OverlayError` propagates to caller.
- Health: existing `try/except Exception` around `get_validator(schema_kind)` (now `project_get_validator`) catches `OverlayError` → one `scan_failed` issue per affected kind; the per-file loop is skipped for that kind (`validator is None`), other kinds and other checks run.
- Codex create/edit: `validate_entity(..., project_root=root)` calls `project_validator_for`; an `OverlayError` surfaces as the `ValueError` raised by create/edit (caller sees the message, no traceback).

### Output Formats

**Overlay YAML shape (`.lore/custom-schemas/codex-frontmatter.yaml`):**
```yaml
# Add-only overlay for codex canonical-doc frontmatter.
# Merged onto the packaged codex-frontmatter schema. New keys only.
properties:
  owner:
    type: string
    minLength: 1
    description: Team or person accountable for this doc.
required:
  - owner
```

**Merged schema (effective `codex-frontmatter` for that project):**
```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
$id: "lore://schemas/codex-frontmatter"      # unchanged from packaged
title: Codex Frontmatter
type: object
additionalProperties: false                  # pinned false (FR-6)
required: [id, title, summary, owner]         # packaged + appended overlay (FR-5)
properties:
  id: {...}                                   # packaged, untouched
  title: {...}
  summary: {...}
  type: {...}
  related: {...}
  binds: {...}
  rites: {...}
  owner:                                      # injected from overlay (FR-4)
    type: string
    minLength: 1
    description: Team or person accountable for this doc.
```

**Success — `lore health` with a valid overlay (doc has `owner: alice`):**
```
schemas: OK
```

**Error — typo `onwer:` on a doc, overlay declares `owner` (FR-6, undeclared key still errors):**
```
codex  .lore/codex/foo.md  schema  Unknown property 'onwer' — allowed keys are id, title, summary, type, related, binds, rites, owner.  rule=additionalProperties  pointer=/onwer
```
(The error lists `owner` among allowed keys because the merged schema's `properties` contains it — `_unexpected_keys`/`_format_message` read `schema.properties`.)

**Error — missing required overlay key (doc lacks `owner`, overlay marks it required, FR-5):**
```
codex  .lore/codex/foo.md  schema  Missing required property 'owner'.  rule=required  pointer=/
```

**Error — collision overlay (overlay declares `title:`), malformed-overlay path (FR-7, FR-10):**
```
codex  lore://schemas/codex-frontmatter  scan_failed  .lore/custom-schemas/codex-frontmatter.yaml: property 'title' collides with a packaged field and cannot be overridden  schema_id=lore://schemas/codex-frontmatter
```

**Error — unparseable overlay YAML (FR-10):**
```
codex  lore://schemas/codex-frontmatter  scan_failed  .lore/custom-schemas/codex-frontmatter.yaml: invalid YAML: ...  schema_id=lore://schemas/codex-frontmatter
```

**Error — `lore codex create` with a custom key but no overlay (still rejected, FR-2):**
```
Unknown property 'owner' — allowed keys are id, title, summary, type, related, binds, rites.
```

---

## Project Structure

```
lore/
  src/lore/
    schemas/
      __init__.py                       # MODIFY: add resolve_merged_schema,
                                         #   merge_overlay, project_validator_for,
                                         #   OverlayError; add project_root kwarg
                                         #   to validate_entity; extend __all__.
      codex-frontmatter.yaml            # UNCHANGED (packaged default)
      codex-source-frontmatter.yaml     # UNCHANGED (packaged default)
    paths.py                            # MODIFY: add custom_schemas_dir(root),
                                         #   custom_schema_path(root, kind).
    health.py                           # MODIFY: add module-level seam
                                         #   project_get_validator; route the two
                                         #   codex kinds through it in _check_schemas.
    codex.py                            # MODIFY: pass project_root into
                                         #   validate_entity at create/edit calls.
    api.py                              # MODIFY: re-export resolve_merged_schema,
                                         #   project_validator_for, OverlayError.
    defaults/
      skills/
        new-custom-schema/
          SKILL.md                      # NEW (seed): scaffolding-skill contract.
  .lore/
    skills/
      new-custom-schema/
        SKILL.md                        # NEW: copied counterpart (this repo).
    custom-schemas/                     # NEW dir (created by the skill on demand;
                                         #   not seeded — absent by default, FR-2).
  tests/
    e2e/
      test_custom_schema_overlay.py     # NEW: E2E scenarios (both workflows).
    unit/
      test_schema_overlay_resolver.py   # NEW: resolver/merge unit tests.
      test_health_schema_overlay.py     # NEW: health integration unit tests.
      test_codex_create_overlay.py      # NEW: codex create/edit unit tests.
```

> No `.lore/custom-schemas/` directory is seeded by `lore init` — its absence is the FR-2 zero-overlay baseline. The skill creates it when first used.

---

## Test Strategy

### E2E Coverage

| Workflow (from PRD) | Workflow codex ID | Test scenario | Priority |
|---------------------|-------------------|---------------|----------|
| Add a custom frontmatter field (Codex maintainer) | `lore codex show conceptual-workflows-health` | `init` a project; write `.lore/custom-schemas/codex-frontmatter.yaml` adding required `owner`; create a codex doc with `owner` via `lore codex create` (accepted); `lore health` passes; a doc with `onwer` typo fails as unknown property; a doc missing `owner` fails as missing-required. | High |
| Health audit honors the overlay (Agent/CI) | `lore codex show conceptual-workflows-health` | Ship a `codex-source-frontmatter` overlay adding `ingested_at`; a source doc with `ingested_at` passes; canonical docs validate against the canonical merged schema; a malformed (collision) overlay yields exactly one `scan_failed` issue naming the overlay and `lore health` still runs every other check (exit non-zero, no traceback). | High |
| No-overlay baseline (NFR Reliability / FR-2) | `lore codex show conceptual-workflows-health` | With no `.lore/custom-schemas/` present, `lore health` output is identical to pre-feature behavior; a custom key is still rejected at create and health. | High |

### Unit Coverage

| Component | Workflow codex ID | Scenarios to cover |
|-----------|-------------------|--------------------|
| `schemas.merge_overlay` / `resolve_merged_schema` | `lore codex show conceptual-workflows-health` | (a) overlay adds `properties` → merged schema contains them (FR-4); (b) overlay `required` appended to packaged `required` (FR-5); (c) `additionalProperties` stays `false` after merge (FR-6); (d) collision with each packaged key (`id,title,summary,type,related,binds,rites` for codex; `id,title,summary,type,related` for source) → `OverlayError` (FR-7); (e) `required` entry not in overlay `properties` → `OverlayError` (FR-5); (f) no overlay file → returns packaged schema unchanged (FR-2); (g) packaged base dict not mutated across calls. |
| `schemas.project_validator_for` (cache) | `lore codex show conceptual-workflows-health` | (a) two calls, unchanged overlay → same cached validator; (b) overlay file rewritten (mtime_ns bumped) → new validator reflecting the change (FR-3); (c) no-overlay key uses sentinel and does not collide with overlay key. |
| `schemas.validate_entity(project_root=...)` | `lore codex show conceptual-workflows-health` | (a) custom declared key passes; (b) undeclared key errors with `Unknown property` listing the custom key among allowed (FR-6); (c) `project_root=None` → packaged behavior; (d) `OverlayError` propagates for a malformed overlay. |
| `health._check_schemas` integration | `lore codex show conceptual-workflows-health` | (a) merged validator used for both `codex-frontmatter` and `codex-source-frontmatter` kinds (FR-8); (b) malformed overlay → one `scan_failed` HealthIssue naming the overlay, no exception, other kinds still scanned (FR-10); (c) source-file override still routes `sources/*` to the merged source schema; (d) monkeypatch of `project_get_validator` seam works (test seam preserved). |
| `codex.create_document` / `update_document` | `lore codex show conceptual-workflows-health` | (a) create accepts a declared custom key (FR-9); (b) create rejects an undeclared key; (c) create with collision overlay raises `ValueError` carrying the `OverlayError` text; (d) update preserves and re-validates against the merged schema; (e) no-overlay create unchanged. |
| `paths.custom_schema_path` | `lore codex show conceptual-workflows-health` | resolves `<root>/.lore/custom-schemas/<kind>.yaml` for both kinds. |

### Test Conventions

- E2E under `tests/e2e/`, unit under `tests/unit/`, matching the repo split. Click CLI tested via `CliRunner` reading `result.stdout`/`result.stderr` separately (no `mix_stderr`).
- Per ADR-006 (`decisions-006-no-seed-content-tests`): tests assert merge **behavior and structure** (merged `properties` contains the custom key, `additionalProperties is False`, validation outcomes), never the literal byte content of the packaged `codex-frontmatter.yaml` / `codex-source-frontmatter.yaml` or of the seeded `new-custom-schema` SKILL.md.
- Fixtures build overlays in a `tmp_path` `.lore/custom-schemas/` so mtime-cache tests can bump file mtimes deterministically (`os.utime`).
- The scaffolding skill is markdown (no Python contract) — covered only by the E2E "create via skill output" path indirectly; its content is not pinned (ADR-006).

---

## Crazy Tech Spec Findings

_No separate Crazy Tech Spec was produced for this feature; the design session locked three decisions captured directly in the PRD._

| Idea | Decision | Rationale |
|------|----------|-----------|
| Let overlay set `additionalProperties: true` for arbitrary keys | Rejected | PRD Out of Scope + FR-6: defaults can never be weakened; the value proposition is typo protection. |
| New `lore schema` CLI command group | Rejected | PRD Out of Scope: discovery is convention + skill. |
| Reuse the kind-only `_validator_for` lru_cache | Rejected | Project-blind and mtime-blind; FR-3 needs a `(kind, project_root, mtime)` key — separate cache. |

---

## Migration & Rollback

- **Migration:** none. No DB schema change, no data migration. New code paths are inert until a project creates `.lore/custom-schemas/<kind>.yaml` (FR-2). Existing projects behave byte-for-byte identically until they opt in.
- **Rollback:** revert the code change; any existing overlay files become dormant (their custom keys revert to `Unknown property` errors, exactly the pre-feature state). No cleanup of project data required.
- **Stale-doc flag for Codex Apply:** `tech-arch-schemas` states "User-extensible / project-local schemas are explicitly post-MVP. There is no runtime override path." — this feature reverses that. The Codex Apply mission must update that paragraph and the Dependency Rules section. (Carried from the technical map Scout Notes.)

---

## Change Log

| Version | Change | Reason |
|---------|--------|--------|
| 1.0 | Initial Tech Spec | Locks: resolver in `lore.schemas` (`resolve_merged_schema`/`merge_overlay`/`project_validator_for`, `OverlayError`); overlay at `.lore/custom-schemas/<kind>.yaml`; add-only/strict/defaults-authoritative merge; `(kind, project_root, mtime_ns)` cache; `validate_entity` gains `project_root` kwarg; health routes the two codex kinds through `project_get_validator`; malformed overlay → `scan_failed`; `new-custom-schema` skill seeded under `src/lore/defaults/skills/`. Honors ADR-010/011 parity and ADR-006. |

---

## ADR & Standards Audit

_Appended by the ADR & Standards Enforcer (2026-06-18). The spec was reconciled in place against every doc in the `decisions/` group and the `standards-*` / `tech-arch-*` convention docs. The human Spec Gate is skipped for this quest; this audit flows directly to Tech Planning (`m-d235`) and Codex Apply (`m-984e`)._

### Reconciled (old → new + ADR id)

| # | Location | Old | New | Forcing rule |
|---|----------|-----|-----|--------------|
| R-1 | API & Communication → "New public names" | "Re-exported through `lore.api.__all__`." | "Added to the `# --- Schemas ---` import block in `api.py` and to `lore.api.__all__`; the facade stays a pure re-export module (zero `def`/`class`)." Also corrected the rationale to state `validate_entity` is already public *because it is in `lore.api.__all__` and `schemas.__all__` today* (verified `api.py:311`, `schemas/__init__.py:17`). | ADR-010 + `tech-arch-api-facade` (`api.py` is a pure re-export facade; the original line under-specified where the names land and how the no-`def` rule is honoured). |
| R-2 | API & Communication → "Error response format" | "Codex create/edit: `ValueError` whose message is the `OverlayError` text." | Spelled out the real path: `validate_entity(kind, meta, project_root=root)` raises `OverlayError` during validator construction (before returning its `list[SchemaIssue]`); `OverlayError` subclasses `ValueError`, so it propagates unchanged out of `create_document`/`update_document` (`codex.py:132`); ordinary validation failures still return `list[SchemaIssue]` that create/edit join into the existing `ValueError` (`codex.py:153`). | ADR-011 + `tech-arch-schemas`. `validate_entity` returns `list[SchemaIssue]` and never raised for validation failures; the old line implied it raised. Reconciled to the actual two-mode contract so parity (CLI ≡ API) is exact. |

### Coverage filled

| Standard / ADR | Gap | Filled |
|----------------|-----|--------|
| ADR-011 / ADR-010 parity | The exact public-surface placement (which import block, `__all__` membership, facade purity) was implicit. | R-1 names the `# --- Schemas ---` block + `__all__` + the zero-`def` facade rule. The merged validator is reached identically via CLI (`lore health`, `lore codex create/edit`) and `lore.api` (`validate_entity(..., project_root=…)`, `project_validator_for`) — no consumer re-implements the merge (resolver is the single home in `lore.schemas`, satisfying `standards-dry`). |
| Codex create/edit error contract | Whether `validate_entity` raises or returns on a malformed overlay was ambiguous. | R-2 pins it to the verified `codex.py` `ValueError`-on-schema-failure contract; no traceback escapes `lore codex`, no traceback escapes `lore health` (existing `try/except Exception` at `health.py:558`). |
| ADR-013 (TOML config vs YAML content) — verified, no edit | Enforcer must confirm the format split. | Overlay files are JSON-Schema content mirroring the packaged `src/lore/schemas/*.yaml` (all YAML), parsed with `yaml.safe_load` — **YAML is correct**. They are schema content, not flat key-value config, so they do NOT belong in `.lore/config.toml`. No conflict; recorded here so the split is auditable. |
| ADR-012 (space-separated multi-value) & ADR-017 (`click.Choice`, exit 2) — N/A | Enforcer must verify CLI flag conventions. | The spec adds **no new CLI flag** (no `lore schema` group, no new option). ADR-012 and ADR-017 have no surface to govern here. Confirmed against `tech-cli-entity-crud-matrix` (no codex write command beyond create/edit). |
| ADR-008 (enriched `--help`) — N/A | Enforcer must verify new command groups carry concept help. | No new command group is added, so the ADR-008 group-help obligation is not triggered. |
| ADR-014 (link direction) — N/A | Enforcer must verify any new link edge. | The feature introduces no new codex link edge (`related`/`binds`/`rites` unchanged). Overlays are not graph nodes. Not triggered. |

### Unrecorded decisions (need an ADR — tech-writer to record; NOT written here)

1. **Overlays are path-discovered project config, not ID-addressable entities — the ADR-006 boundary.** ADR-006 ("agents reference entities by ID via the CLI, never by file path") governs *retrievable Lore-managed entities* (artifacts, codex docs, knights, doctrines), each surfaced by a `lore <x> show <id>` command. An overlay has **no** ID-addressable CLI retrieval path (the PRD forbids a `lore schema` group), so it is reached by its filename convention `.lore/custom-schemas/<kind>.yaml`. This is the **same precedent as `.lore/config.toml` and `.lore/codex/glossary.yaml`** (ADR-013): user-owned project files addressed by canonical path, not by ID. The spec does **not** violate ADR-006 — overlays simply are not the class of entity ADR-006 covers — but no existing ADR explicitly classes "schema overlay" as config-class-addressed-by-path rather than entity-class-addressed-by-ID. Record an ADR fixing that classification so a future author does not (a) read this as an ADR-006 violation or (b) add a `lore schema show` path that the PRD rejected. (The spec's Change Log line "Honors … ADR-006" is accurate under this reading and was left intact.)
2. **The `project_get_validator(kind, project_root)` health seam** is a new module-level monkeypatch seam added to `health.py` alongside the existing kind-only `get_validator` (= `schemas._validator_for`). It is internal (not in `lore.api.__all__`, matching how `get_validator` is internal today). No ADR governs the health-seam pattern; record one so the two-seam arrangement (kind-only for non-codex kinds, project-aware for the two codex kinds) is a documented convention rather than an accident.
3. **`OverlayError(ValueError)` as the overlay-resolution failure type**, surfaced as `scan_failed` in health and as a propagating `ValueError` in codex create/edit. Mirrors the `GlossaryError(ValueError)` / `ImpactsError(ValueError)` precedent but is a new public exception in `lore.api.__all__`; worth an ADR line confirming the "domain error subclasses `ValueError`, propagates as the existing create/edit `ValueError` contract" convention.

### Deferral violations

None. The PRD Out-of-Scope set — new `lore schema` CLI group, overlays that override/relax core fields, overlays for non-codex kinds in v1, `additionalProperties: true` allow-anything overlays — is honoured throughout. The "Crazy Tech Spec Findings" table explicitly rejects all three corresponding temptations, and the three `Deferred` rows (knight/artifact/doctrine kinds, per-doc-type overlays, the `--show` inspect path) are marked Post-MVP with no design or implementation in the spec.

### Carried stale-doc flag (for Codex Apply, already in the spec)

`tech-arch-schemas` → Dependency Rules currently states "User-extensible / project-local schemas are explicitly post-MVP. There is no runtime override path." This feature **reverses** that sentence. The spec already routes this to Codex Apply under "Migration & Rollback → Stale-doc flag." Re-flagged here so `m-984e` does not miss it: that paragraph and `tech-arch-schemas`' Schema-Kinds / Public-Interface sections must be updated to describe the resolver, the overlay path, and the `validate_entity(project_root=…)` / `project_validator_for` surface.

### Escalations

None. Every conflict was mechanically reconcilable against a settled ADR; the three items above are forward-looking ADR records, not blocking conflicts, and require no product/architectural judgment the existing ADRs leave open.

### Verdict

`RECONCILED`
