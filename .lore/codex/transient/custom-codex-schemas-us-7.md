---
id: custom-codex-schemas-us-7
title: US-7 — new-custom-schema scaffolding skill
summary: >
  A new skill new-custom-schema authored at .lore/skills/new-custom-schema/SKILL.md
  with a seed copy at src/lore/defaults/skills/new-custom-schema/SKILL.md. It
  collects the target kind + field names/types/required, enforces the add-only
  guard (refuse a packaged-field collision, refuse an undeclared required) BEFORE
  writing .lore/custom-schemas/<kind>.yaml, then runs lore health for post-write
  confirmation. Markdown only — not TDD-testable production code; Defaults Review
  reconciles the seed.
type: user-story
related:
  - custom-codex-schemas-tech-spec
  - custom-codex-schemas-us-4
---

## Metadata

- **ID:** US-7
- **Status:** final
- **Epic:** Authoring experience
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-06-18
- **PRD:** `lore codex show custom-codex-schemas-prd`
- **Tech Spec:** `lore codex show custom-codex-schemas-tech-spec`

---

## Story

As a **codex maintainer who does not know JSON-Schema internals**, I want **a skill that interviews me for the kind, field names/types, and which are required, then writes a valid add-only overlay and confirms it with `lore health`**, so that **I can add a custom frontmatter field in under a minute without hand-writing JSON-Schema or risking a malformed overlay**.

## Context

FR-11/FR-12/FR-13 and the Tech Spec's Scaffolding-skill Important decision. A new skill `new-custom-schema` drafts the overlay: it collects the target kind (`codex-frontmatter` / `codex-source-frontmatter`), the custom field names + types, and which are required (FR-11); enforces the add-only rules **before** writing — refuses a property whose key collides with a packaged field for that kind, refuses a `required` entry not declared in the overlay (FR-12); writes `.lore/custom-schemas/<kind>.yaml`; then runs `lore health` so the author gets immediate confirmation (FR-13). This mirrors the user workflow "Add a custom frontmatter field — Codex maintainer" in the PRD. The skill is **markdown, not Python production code** — it is not TDD-testable; its content is not pinned by tests (`decisions-006-no-seed-content-tests`). The repo copy under `.lore/skills/` and the seed under `src/lore/defaults/skills/` are kept byte-identical and reconciled by Defaults Review.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Skill authored in both locations and discoverable

**Given** the repo after this story
**When** an author opens `.lore/skills/new-custom-schema/SKILL.md`
**Then** the file exists with valid SKILL frontmatter (`name: new-custom-schema`, a one-line `description`), and an identical seed exists at `src/lore/defaults/skills/new-custom-schema/SKILL.md` (so a freshly `lore init`-ed project receives it).

#### Scenario 2: Skill enforces the add-only guard before writing (documented procedure)

**Given** the skill's written procedure
**When** read end to end
**Then** it instructs: (a) collect kind + fields (name, type, required?), (b) reject any field whose key is a packaged field of that kind (`id, title, summary, type, related, binds, rites` for `codex-frontmatter`; `id, title, summary, type, related` for `codex-source-frontmatter`), (c) reject a `required` entry not among the collected fields, (d) only then write `.lore/custom-schemas/<kind>.yaml` in the add-only shape (`properties:` + optional `required:`, no `additionalProperties`, no `$id`), (e) run `lore health` and report the result (FR-12, FR-13).

#### Scenario 3: Indirect overlay validity (via the existing E2E health path)

**Given** an overlay written following the skill's documented shape
**When** `lore health --scope schemas` runs (the US-4 E2E path)
**Then** a well-formed overlay passes and a guard-violating one is caught — confirming the skill's output shape is the one the resolver accepts. (No separate Python test pins the skill text.)

### Unit Test Scenarios

_None — the skill is markdown, not a Python contract. Per `decisions-006-no-seed-content-tests` its literal content is not tested; its output shape is exercised indirectly by the US-4 health E2E. The only structural checks are the two files existing with valid SKILL frontmatter (Scenario 1), which `lore health`'s skill/structure scan and the Defaults Review cover._

---

## Out of Scope

- The resolver, cache, `validate_entity` keyword, health, and codex wiring (US-1..US-6) — the skill only writes an overlay file those consume.
- A `lore schema` CLI command (PRD Out of Scope — discovery stays convention + skill + docs).
- Seeding `.lore/custom-schemas/` itself — the dir is created on demand by the skill, never by `lore init` (FR-2 zero-overlay baseline).
- Pinning the skill's prose with byte-content tests (`decisions-006-no-seed-content-tests`).

---

## References

- PRD: `lore codex show custom-codex-schemas-prd`
- Tech Spec: `lore codex show custom-codex-schemas-tech-spec`
- `lore codex show decisions-006-no-seed-content-tests` — seed/skill content is not byte-tested
- `lore codex show decisions-014-link-direction` — protected key set the guard must reject

---

## Tech Notes

### Implementation Approach

- **Files to create:**
  - `.lore/skills/new-custom-schema/SKILL.md` — the working skill in this repo. Frontmatter `name: new-custom-schema` + `description`. Body follows the same shape as existing skills (e.g. `src/lore/defaults/skills/new-rite/SKILL.md` — `---`/`name`/`description` then `## Steps`). Steps: (1) pick the kind; (2) collect each field's name, JSON-Schema type, required flag; (3) run the add-only guard — collision check against the per-kind packaged key set, undeclared-required check; (4) write `.lore/custom-schemas/<kind>.yaml` in the add-only YAML shape (header comment, `properties:`, optional `required:`); (5) run `lore health` and surface the result (FR-13).
  - `src/lore/defaults/skills/new-custom-schema/SKILL.md` — byte-identical seed so `lore init` ships it. (Existing seed skills live under `src/lore/defaults/skills/`; verified the dir holds `new-rite`, `new-artifact`, etc.)
- **Files to modify:** none in `src/lore/*.py`. The skill emits a file the US-1..US-5 code already validates.
- **Schema changes:** none — the skill writes an overlay, it does not change a packaged schema.
- **Dependencies:** the overlay shape and guard rules come from US-1 (merge semantics) and the resolver behaviour US-4 confirms; author this after the merge rules are settled so the guard mirrors them exactly. Defaults Review reconciles the seed copy.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_custom_schema_overlay.py` | the US-4 overlay E2E indirectly validates the skill's output shape; no skill-specific test file |
| Unit | — | none — markdown skill, `decisions-006-no-seed-content-tests` |

### Test Stubs

```python
# Structure — both skill files exist with valid SKILL frontmatter (Scenario 1)
# Exercises: lore codex show conceptual-workflows-health (skill/structure scan + Defaults Review)
def test_new_custom_schema_skill_present():
    # Then: .lore/skills/new-custom-schema/SKILL.md and
    #       src/lore/defaults/skills/new-custom-schema/SKILL.md exist;
    #       both parse a frontmatter name == "new-custom-schema". Do NOT assert body bytes.
    pass


# Indirect — an overlay in the skill's documented shape is accepted (Scenario 3)
# Exercises: lore codex show conceptual-workflows-health (schemas scope)
def test_skill_shaped_overlay_accepted_by_health(tmp_path):
    # Given: write an overlay matching the skill's add-only shape (properties + required)
    # When: lore health --scope schemas
    # Then: passes (reuses the US-4 happy-path assertion); a collision-shaped one is caught
    pass
```

### Complexity Estimate

**S** — Two byte-identical markdown files; no production code, no unit tests. The guard logic is documented prose mirroring US-1's rules, not executable. Defaults Review handles the seed reconciliation.

### Standards References

**Tester (Red):**
- `lore codex show decisions-006-no-seed-content-tests` — do not pin the skill's body; only the two-file existence + frontmatter, and the indirect overlay-shape E2E.

**Implementer (Green):**
- `lore codex show decisions-014-link-direction` — the packaged key set the guard must refuse (`related`/`binds`/`rites` plus `id`/`title`/`summary`/`type`).
- `lore codex show tech-arch-source-layout` — seed skills live under `src/lore/defaults/skills/`; keep the repo copy and seed in sync (Defaults Review).
