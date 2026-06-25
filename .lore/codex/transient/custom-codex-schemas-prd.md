---
id: custom-codex-schemas-prd
title: Custom Codex Frontmatter Schemas — PRD
summary: Lets a project extend the packaged codex frontmatter schemas with its own add-only overlay files under .lore/custom-schemas/, validated by lore health and lore codex create/edit, plus a skill to scaffold those overlays.
type: prd
---

# Custom Codex Frontmatter Schemas — PRD

**Author:** Product Manager
**Date:** 2026-06-18
**Supersedes:** _none — first PRD for this feature_

---

## Executive Summary

Lore ships two packaged JSON-Schemas that validate codex doc frontmatter — `codex-frontmatter` (canonical docs) and `codex-source-frontmatter` (source docs under `sources/`). Both set `additionalProperties: false`, so any project-specific frontmatter key a team adds (e.g. `owner`, `reviewed`, `jira`) is reported by `lore health` as `Unknown property` and is rejected at `lore codex` create/edit time. Teams have no supported way to add their own fields.

This feature lets a project declare **custom frontmatter overlays** — small add-only schema files dropped into `.lore/custom-schemas/`, auto-discovered by filename. An overlay extends the matching packaged schema: it adds new typed properties (and optionally marks them required) while the packaged core fields stay authoritative and untouched. A companion skill scaffolds a valid overlay so authors don't hand-write JSON-Schema.

### What Makes This Special

Custom keys gain **typed validation and typo protection**, not just permission. `additionalProperties` stays `false` after the merge, so a misspelled custom key (`onwer:`) still errors — the overlay declares exactly which extra keys are legal and what shape they take. Defaults can never be weakened.

---

## Project Classification

| Attribute | Value |
|-----------|-------|
| Project type | CLI tool + Python library (Lore) |
| Primary users | Teams running a Lore-managed project who customize their codex; agents and humans running `lore health` |
| Scale | Per-project: a handful of overlay files (one per schema kind), low frequency of change |

---

## Success Criteria

### User Success

- A team adds a custom frontmatter key to their codex docs, declares it once in an overlay, and `lore health` passes — while a typo in that key still fails.
- An author creates a valid overlay via a skill in under a minute without knowing JSON-Schema internals.
- The packaged defaults remain enforced: no overlay can drop `id`/`title`/`summary` or redefine them.

### Technical Success

| Metric | Baseline | Target | Timeline |
|--------|----------|--------|----------|
| Custom frontmatter keys supported on codex docs | 0 (all rejected) | unlimited, per declared overlay | this feature |
| `lore health` false-positives on declared custom keys | one error per custom key | 0 | this feature |
| Typo detection on custom keys | n/a | undeclared key still errors | this feature |
| Code paths consuming the merged schema | n/a | both health audit and codex create/edit | this feature |

---

## Product Scope

### MVP

- **Overlay discovery** — `.lore/custom-schemas/<kind>.yaml` auto-loaded by filename, no config. Supported kinds for v1: `codex-frontmatter` and `codex-source-frontmatter`.
- **Add-only merge** — overlay may add new `properties` and add entries to `required`; packaged core fields are authoritative and cannot be redefined or weakened.
- **Strict result** — merged schema keeps `additionalProperties: false`; declared custom keys pass, undeclared keys still error.
- **Project-aware resolver** — a single new layer in `lore.schemas` builds the merged validator from packaged default + project overlay, cache-keyed on overlay mtime.
- **`lore health` integration** — the schema audit uses the merged validator for codex/codex-source files; a malformed or rule-breaking overlay surfaces as a clean `scan_failed` issue, never a stack trace.
- **`lore codex` create/edit integration** — custom keys pass validation at write time, consistent with the health audit.
- **Scaffolding skill** — a new skill that drafts a valid overlay (collects the custom field names/types, enforces the add-only rules, writes the file to `.lore/custom-schemas/`).

### Post-MVP

- Overlays for other entity kinds (knight, artifact, doctrine) — the resolver is generic, so this is incremental.
- Per-doc-type overlays (different custom keys for tech-spec vs ADR) — deferred; doc_type resolves by path/group, not frontmatter.
- An inspect command to print the effective merged schema.

### Out of Scope

- A new top-level CLI command group for schemas (no `lore schema ...`). Discovery is convention + docs + the skill.
- Overlays that override or relax packaged core fields.
- Overlays for non-codex entity kinds in v1.
- Letting an overlay set `additionalProperties: true` to allow arbitrary keys.

---

## User Workflows

### Add a custom frontmatter field — Codex maintainer

**Persona:** Maintainer on a team that tags every codex doc with an `owner`.
**Situation:** They add `owner: alice` to a doc; `lore health` reports `Unknown property 'owner'`.
**Goal:** Make `owner` a first-class, validated frontmatter field across canonical codex docs.

**Steps:**
1. Run the scaffold skill and answer prompts (field `owner`, type `string`, required yes).
2. The skill writes `.lore/custom-schemas/codex-frontmatter.yaml` with the add-only overlay.
3. Run `lore health` — the `owner` key now passes; docs missing `owner` are flagged as missing-required.
4. A typo (`onwer:`) on any doc still errors as an unknown property.

**Critical decision points:** Whether the field is required (adds to merged `required`) or optional.
**Success signal:** `lore health` passes on docs with `owner`, and `lore codex` create accepts the field.

### Health audit honors the overlay — Agent or CI

**Persona:** An agent or CI job running `lore health`.
**Situation:** A project ships a `codex-source-frontmatter` overlay adding `ingested_at`.
**Goal:** Validate every codex/source doc against the merged schema without project-specific code.

**Steps:**
1. `lore health` resolves the merged validator per kind (packaged + overlay).
2. Source docs validate against `codex-source-frontmatter` ∪ overlay; canonical docs against `codex-frontmatter` ∪ overlay.
3. A broken overlay yields a single `scan_failed` issue identifying the overlay, not a crash.

**Critical decision points:** Overlay present vs absent; overlay valid vs malformed.
**Success signal:** Custom keys validated, defaults enforced, malformed overlay reported cleanly.

---

## Functional Requirements

### Overlay discovery and loading

- **FR-1:** The system discovers overlay files at `.lore/custom-schemas/<kind>.yaml`, where `<kind>` matches a packaged schema kind. v1 recognizes `codex-frontmatter` and `codex-source-frontmatter`.
- **FR-2:** When no overlay file exists for a kind, validation behaves exactly as today (packaged schema only) — zero behavior change.
- **FR-3:** Overlay resolution is project-aware and cache-keyed on the overlay file's mtime, so an edited overlay is re-read within a long-running process (e.g. Realm importing `lore.models`).

### Merge semantics (add-only, strict)

- **FR-4:** An overlay may declare new entries under `properties`; each is merged into the packaged schema's `properties`.
- **FR-5:** An overlay may declare `required` entries; each is appended to the packaged schema's `required`. Every overlay `required` entry must name a property declared in the same overlay.
- **FR-6:** The merged schema retains `additionalProperties: false`: declared custom keys pass; any undeclared key still errors.
- **FR-7:** An overlay property whose key collides with a packaged property (e.g. `id`, `title`, `summary`, `related`, `binds`, `rites`) is rejected — overlays are add-only and cannot redefine or weaken defaults.

### Validation integration

- **FR-8:** `lore health` validates codex canonical docs against the merged `codex-frontmatter` schema and source docs against the merged `codex-source-frontmatter` schema.
- **FR-9:** `lore codex` create and edit validate frontmatter against the merged schema, so custom keys are accepted at write time consistently with the health audit.
- **FR-10:** A malformed overlay (unparseable YAML, non-object, or a rule violation per FR-5/FR-7) is reported as a single clean health issue (e.g. `scan_failed`) identifying the overlay; the audit never raises an unhandled exception and other checks still run.

### Scaffolding skill

- **FR-11:** A new skill drafts a custom-schema overlay: it collects the target kind, the custom field names and types, and which are required, then writes a valid `.lore/custom-schemas/<kind>.yaml`.
- **FR-12:** The skill enforces the add-only rules before writing — it refuses to emit a property colliding with a packaged field, and refuses a `required` entry not declared in the overlay.
- **FR-13:** After writing, the skill validates the result (e.g. via `lore health`) so the author gets immediate confirmation the overlay is well-formed.

---

## Non-Functional Requirements

### Performance

- Overlay resolution adds at most one file stat + parse per kind per audit run; negligible versus the existing per-file validation cost.

### Security

- Overlays are local project files authored by the team. They are parsed with `yaml.safe_load`. Overlays cannot weaken packaged invariants (add-only), bounding blast radius.

### Reliability

- A malformed overlay degrades gracefully to a reported issue; it never crashes `lore health` and never silently disables validation of the affected kind.
- With no overlay present, behavior is byte-for-byte identical to today.

### Compatibility / Parity

- Every behavior is reachable from both the CLI and the Python API (`lore.models` / `lore.schemas`), per Lore's CLI↔API parity guardrail.
- The resolver layer is added inside `lore.schemas` so both consumers (health audit, codex create/edit) share one implementation.

---

## Change Log

| Version | Change | Reason |
|---------|--------|--------|
| 1.0 | Initial PRD | Captures the three locked design decisions from the design session: strict declared-only (`additionalProperties` stays false), add-only (defaults protected), per-kind overlays. Location `.lore/custom-schemas/`, no new CLI command, plus a scaffolding skill. |

---

## Pre-Architecture Notes

_(Appended by the user after reviewing this PRD — do not edit until sign-off phase)_
