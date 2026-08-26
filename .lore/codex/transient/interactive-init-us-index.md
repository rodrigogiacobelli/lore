---
id: interactive-init-us-index
title: Interactive lore init and Skill Catalogue Consolidation — User Story Index
summary: Twenty-four sized stories across seven epics covering the interactive lore
  init flow, the hash install manifest and its reconciliation, the ten-skill catalogue,
  the adjacent corrections and the release obligations — with a coverage map from every
  PRD functional requirement and every Tech Spec ruling to the story that delivers it.
type: user-story-index
related:
- interactive-init-prd
- interactive-init-tech-spec
- interactive-init-technical-map
- interactive-init-business-map
- interactive-init-us-001
- interactive-init-us-002
- interactive-init-us-003
- interactive-init-us-004
- interactive-init-us-005
- interactive-init-us-006
- interactive-init-us-007
- interactive-init-us-008
- interactive-init-us-009
- interactive-init-us-010
- interactive-init-us-011
- interactive-init-us-012
- interactive-init-us-013
- interactive-init-us-014
- interactive-init-us-015
- interactive-init-us-016
- interactive-init-us-017
- interactive-init-us-018
- interactive-init-us-019
- interactive-init-us-020
- interactive-init-us-021
- interactive-init-us-022
- interactive-init-us-023
- interactive-init-us-024
---

# Interactive `lore init` and Skill Catalogue Consolidation — User Story Index

**Author:** Tech Lead — Tech Planning
**Date:** 2026-08-25
**Status:** final
**PRD:** `lore codex show interactive-init-prd`
**Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## How the feature is carved

The Tech Spec is three joined deliverables sitting on one new architectural seam — the plan/apply split. The carve follows that seam rather than the three deliverables, because every one of them meets at `plan_init`.

Seven epics, twenty-four stories:

1. **Type and data foundations** — the vocabulary and the shipped data every later story reads. No behaviour.
2. **Rendering the skills** — the access-mode renderer, the ten authored skills, and the generated instruction text.
3. **Manifest and reconciliation** — the record, the algorithm over it, and the fallback for projects that have none.
4. **Plan and apply core** — placement, marker writers, `plan_init`, `apply_init`.
5. **Configuration** — the four `init-*` keys and the regenerated header.
6. **CLI surface** — flags, validators on both surfaces, the prompt layer, the orchestration.
7. **Adjacent corrections and release obligations** — the health scope, the schema-version message, the API surface, the packaging.

Three stories are fully independent and can be batched anywhere: **US-022** (schema-version message), **US-024** (packaging) and **US-021** (health scope, needing only US-003 and US-008).

One ordering constraint is not reversible by `git checkout`: **US-010 must capture the pre-consolidation skill hashes before US-005 and US-006 delete the thirteen retired directories.** Either run `scripts/update_legacy_hashes.py` and commit its output ahead of those two stories, or recover the hashes from git history afterwards.

---

## Stories by Epic

### Epic 1 — Type and data foundations

_The vocabulary and shipped data everything else reads._

| ID | Title | Complexity | Status | Codex ID |
|----|-------|------------|--------|----------|
| US-001 | Plan and result types on a stdlib-only leaf module | S | final | `interactive-init-us-001` |
| US-002 | The agent registry ships as data, not as code | M | final | `interactive-init-us-002` |
| US-003 | The skill catalogue ships as data with a retirement ledger | M | final | `interactive-init-us-003` |

### Epic 2 — Rendering the skills

_One authored source per skill, two access modes, ten skills, one generated instruction text._

| ID | Title | Complexity | Status | Codex ID |
|----|-------|------------|--------|----------|
| US-004 | One authored skill source, two access modes | M | final | `interactive-init-us-004` |
| US-005 | The memory family — one skill to store knowledge, one to retrieve it | L | final | `interactive-init-us-005` |
| US-006 | The machinery and workflow families | M | final | `interactive-init-us-006` |
| US-007 | The agent instruction text is rendered, not copied | M | final | `interactive-init-us-007` |

### Epic 3 — Manifest and reconciliation

_What Lore installed, what it would install now, and what is on disk._

| ID | Title | Complexity | Status | Codex ID |
|----|-------|------------|--------|----------|
| US-008 | An install manifest records every file Lore writes and its hash | M | final | `interactive-init-us-008` |
| US-009 | Three-way reconciliation, correct for any version hop | L | final | `interactive-init-us-009` |
| US-010 | Projects that predate the manifest still reconcile | M | final | `interactive-init-us-010` |

### Epic 4 — Plan and apply core

_Where every module meets._

| ID | Title | Complexity | Status | Codex ID |
|----|-------|------------|--------|----------|
| US-011 | Skills install only where the selected agent reads them | M | final | `interactive-init-us-011` |
| US-012 | Lore owns a marked block inside files the user owns | M | final | `interactive-init-us-012` |
| US-014 | `plan_init` computes an initialisation without performing it | L | final | `interactive-init-us-014` |
| US-015 | `apply_init` performs a computed plan, and `run_init` still takes no arguments | L | final | `interactive-init-us-015` |

### Epic 5 — Configuration

_The answers, recorded and documented._

| ID | Title | Complexity | Status | Codex ID |
|----|-------|------------|--------|----------|
| US-013 | The answers are recorded in `config.toml` and reused | M | final | `interactive-init-us-013` |
| US-020 | The config header documents every key, generated from the loader itself | M | final | `interactive-init-us-020` |

### Epic 6 — CLI surface

_Flags, validation, prompts, orchestration._

| ID | Title | Complexity | Status | Codex ID |
|----|-------|------------|--------|----------|
| US-016 | Every prompt has a flag, and multi-value flags are space-separated | L | final | `interactive-init-us-016` |
| US-017 | The same tokens are rejected on both surfaces | M | final | `interactive-init-us-017` |
| US-018 | A prompt layer that costs nothing when nobody prompts | M | final | `interactive-init-us-018` |
| US-019 | `lore init` asks, shows a summary, and writes nothing until confirmed | L | final | `interactive-init-us-019` |

### Epic 7 — Adjacent corrections and release obligations

_The three corrections the PRD folded in, plus what a release owes._

| ID | Title | Complexity | Status | Codex ID |
|----|-------|------------|--------|----------|
| US-021 | `lore health` audits the installed skills | M | final | `interactive-init-us-021` |
| US-022 | The init status message reports the real schema version | S | final | `interactive-init-us-022` |
| US-023 | Thirteen new names on the public API, with the changelog entry that must ship with them | M | final | `interactive-init-us-023` |
| US-024 | The package ships questionary, a verified Click floor, and the new data files | S | final | `interactive-init-us-024` |

---

## Dependency order

Stories are numbered in build order. The graph, for the Story Grouper:

```
US-001 ──┬─ US-002 ──┬─ US-011 ──┐
         ├─ US-003 ──┤           │
         │           └─ US-004 ──┼─ US-005 ──┐
         │                       ├─ US-006 ──┤
         │                       └─ US-007 ──┤
         ├─ US-008 ──┬─ US-009 ──┬─ US-010 ──┤
         │           └───────────┘           │
         └─ US-013 ──────────────────────────┼─ US-014 ─ US-015 ─┬─ US-020
                                 US-012 ─────┘                   │
                                                      US-016 ─┬─ US-017
                                                      US-024 ─┴─ US-018 ─ US-019
US-003 + US-008 ─ US-021          (independent: US-022)
everything ───────────────────────────────────────────────────── US-023
```

`US-024` is a release obligation but must land **early**: `US-018` cannot import `questionary` until the dependency is declared.

---

## PRD Coverage Map

Every functional requirement maps to at least one story.

| PRD Requirement | Story IDs |
|-----------------|-----------|
| FR-1: agents prompt | US-016, US-018, US-019 |
| FR-2: access-mode prompt | US-016, US-018, US-019 |
| FR-3: skill-families prompt | US-003, US-016, US-018, US-019 |
| FR-4: existing instruction file prompt | US-012, US-018, US-019 |
| FR-5: root `.gitignore` prompt | US-012, US-016, US-018, US-019 |
| FR-6: installed-skill tracking prompt | US-012, US-016, US-018, US-019 |
| FR-7: summary shown and confirmed before any write | US-019 |
| FR-8: a flag for every prompt; all prompting suppressible | US-016, US-017 |
| FR-9: no terminal, no prompt, defaults silently | US-014, US-015, US-019 |
| FR-10: recorded answers not re-asked; `--reconfigure` | US-013, US-014, US-018, US-019 |
| FR-11: registry seeded with the release | US-002 |
| FR-12: adding an agent is a data edit | US-002 |
| FR-13: every shipped registry entry is verified | US-002 |
| FR-14: skills where the agent reads them | US-011 |
| FR-15: marker section written and replaced | US-012 |
| FR-16: CLI-mode command layer | US-004, US-005, US-006, US-007 |
| FR-17: agent-native command layer | US-004, US-005, US-006, US-007 |
| FR-18: `codex map`, `codex chaos`, `impacts` in both modes | US-004, US-005, US-006 |
| FR-19: one authored source per skill | US-004, US-011 |
| FR-20: ten skills in three families | US-003, US-005, US-006 |
| FR-21: `store-memory` records knowledge | US-005 |
| FR-22: source snapshot only for an outside-authored artifact | US-005 |
| FR-23: `retrieve-memory` consults codex and rites | US-005 |
| FR-24: `update-*` skills create or edit | US-006 |
| FR-25: manifest records every file and its hash | US-008 |
| FR-26: removes an unchanged retired file | US-009 |
| FR-27: asks before overwriting an edited file; untouched if refused | US-009, US-016, US-018, US-019 |
| FR-28: never touches a file it did not install | US-009 |
| FR-29: reports the successor for every retired skill | US-003, US-009, US-015 |
| FR-30: legacy-hash fallback for pre-manifest projects | US-010 |
| FR-31: correct across any version gap, no migration chain | US-009, US-010 |
| FR-32: compute without performing | US-014 |
| FR-33: perform a previously computed initialisation | US-015 |
| FR-34: `run_init()` unchanged, zero arguments | US-015 |
| FR-35: `tech-arch-agents-md` and `conceptual-workflows-lore-init` describe what ships | **codex-apply mission `q-3c9c/m-d053`** — see the note below |
| FR-36: config header regenerated from the loader registry | US-020 |
| FR-37: `lore health` audits installed skills | US-021 |
| FR-38: real schema version in the init status message | US-022 |
| _Workflow: First initialisation — human developer_ | US-011, US-012, US-016, US-018, US-019 |
| _Workflow: Upgrade with renamed skills_ | US-005, US-006, US-009, US-015 |
| _Workflow: Headless initialisation — Realm and CI_ | US-014, US-015, US-016, US-019 |
| _Workflow: Changing the access mode_ | US-004, US-008, US-009, US-013 |
| _NFR: idempotency; interrupted run recoverable_ | US-015, US-020 |
| _NFR: reconciliation hashes only named files_ | US-008, US-009 |
| _NFR: a user-authored file is never lost without agreement_ | US-009, US-012 |
| _NFR: no network fetch; writes only inside the project root_ | US-002, US-003, US-010, US-012 |

---

## Tech Spec Coverage Map

Every ruling in the settled spec maps to at least one story.

| Tech Spec section | Ruling | Story IDs |
|---|---|---|
| §1 | Plan/apply split | US-014, US-015 |
| §1 | `run_init()` compatibility | US-015 |
| §1 | Three-way reconciliation, no migration chain | US-009 |
| §1 | A path in neither set is never touched | US-009 |
| §1 | `isatty` prompt gate in `cli.py` only | US-019 |
| §1 | Access-mode blocks, one authored source | US-004 |
| §1 | What agent-native mode covers (§7.3 table) | US-005, US-006 |
| §1 | Agent registry as packaged data | US-002 |
| §1 | Space-separated multi-value flags | US-016 |
| §1 | Conflict policy tokens `skip` / `overwrite` | US-009, US-016 |
| §1 | `InitPlan` in `src/lore/initplan.py` | US-001 |
| §2 | No database change; `SCHEMA_VERSION` stays 6 | US-022 |
| §2 | Three-layer validation (schema, `click.Choice`, `lore.validators`) | US-002, US-003, US-016, US-017 |
| §2.1 | One hash function; rendered bytes; section-only for marker entries | US-008 |
| §3.1 | `--json` on `lore init` declined; `--help` states it | US-016 |
| §3.2 | `--dry-run` | US-019 |
| §3.3 | The ten-flag table; no config-derived Click default | US-016 |
| §3.3 | `--agent none` exclusivity in `validators`, both surfaces | US-017 |
| §3.4 | `SpaceSeparatedChoice` | US-016 |
| §4.2 | Error table — exit codes, warnings, unlink failure, abort | US-008, US-015, US-016, US-017, US-019 |
| §4.3 | Output formats — plan summary, apply report, error text | US-015, US-019 |
| §5.1, §5.2 | The seven types and where they live | US-001 |
| §5.3 | `plan_init` / `apply_init` / `run_init` signatures; resolution order | US-014, US-015 |
| §5.4 | Thirteen `__all__` names; three underscore aliases | US-016, US-017, US-018, US-023 |
| §6.1, §6.2 | Manifest location and format; `owned` vs `section` | US-008 |
| §6.3 | Legacy hashes and the pre-flight script | US-010 |
| §6.4 | The eleven-row reconciliation table; ADR-003 boundary; directory pruning | US-009 |
| §6.5 | The operative reading of FR-28 | US-009 |
| §6.6 | The no-manifest fallback | US-010 |
| §6.7 | Apply ordering, manifest last | US-015 |
| §7.1 | The catalogue and the retirement ledger | US-003 |
| §7.2 | The access-mode renderer | US-004 |
| §7.3 | Per-entity native-mode carve-out | US-005, US-006 |
| §7.4 | Instruction-file rendering; generated skills table; FR-4 has two answers | US-007, US-012, US-018 |
| §7.5 | Where skills install | US-011 |
| §7.6 | Root and skills gitignore behaviour | US-012 |
| §8.1, §8.2 | Registry format, loading, `click.Choice` set, not overlayable | US-002, US-016 |
| §9.1 | The four `init-*` keys; list-typed key support | US-013 |
| §9.2 | Interactive vs headless family defaults | US-013, US-014, US-018 |
| §9.3 | Regenerated known-key header | US-020 |
| §10 | `lore health --scope skills` | US-021 |
| §11 | FR-38 schema version | US-022 |
| §11 | Stale codex rewrites | **codex-apply mission `q-3c9c/m-d053`** |
| §11 | Packaging, `click` floor, `questionary`, version bump | US-024 |
| §11 | `CHANGELOG.md` `0.10.0` entry | US-023 |
| §12 | Project structure — six new modules, three new data files, two new schemas | US-001, US-002, US-003, US-008, US-009, US-010, US-018 |
| §13 | Codex documents and ADR amendments | **codex-apply mission `q-3c9c/m-d053`** |
| §14.1 | E2E coverage and file assignment | every story's Test File Locations |
| §14.2 | Unit coverage per component | every story's Unit Test Scenarios |
| §14.3 | Test conventions; ADR-006 structural-only assertions; the `legacy_skills_project` fixture | US-003, US-005, US-006, US-009 |
| §15 | Migration and rollback; unrecognised `manifest_version` | US-008, US-009 |
| §16 | Ideas rejected | recorded in each story's Out of Scope |
| §18 Reconciled #1 | Click default `None`, config read in `plan_init` only | US-014, US-016 |
| §18 Reconciled #2 | `--agent none` exclusivity moved to `validators` | US-017 |
| §18 Reconciled #3 | Thirteen names, all four validators exported | US-017, US-023 |
| §18 Reconciled #4 | `CHANGELOG.md` entry mandatory | US-023 |
| §18 Reconciled #5 | `click>=8.3,<9.0` | US-024 |
| §18 Reconciled #6 | ADR-001's `--json` bullet narrowed | **codex-apply mission `q-3c9c/m-d053`** |
| §18 Reconciled #7 | E2E file assignment, one anchor per file | every story's Test File Locations |
| §18 Reconciled #8 | `SpaceSeparatedChoice` cases are E2E, not unit | US-016 |
| §18 Reconciled #9 | `binds:` on the new codex documents | **codex-apply mission `q-3c9c/m-d053`** |
| §18 Reconciled #10 | `all` / `none` resolve in the business layer | US-003, US-014 |
| §18 Coverage #1 | ADR-003 boundary paragraph | US-009 |
| §18 Coverage #2 | Packaged schema kinds are not overlayable | US-002, US-003 |
| §18 Coverage #3–#6 | Codex documents named for update | **codex-apply mission `q-3c9c/m-d053`** |
| §19 Escalation 1 | Click floor upheld; no 8.0–8.2 verification mission | US-024 |
| §19 Escalation 2 | ADR-017 constraint 3 corrected in place | **codex-apply mission `q-3c9c/m-d053`** |
| §19 Note to Tech Planning | `--agent none` tested on both surfaces | US-017 |

---

## Requirements delivered outside a dev story

Three groups of Tech Spec work belong to the phase-5 **codex-apply** mission (`lore show q-3c9c/m-d053`), which runs in parallel with this planning mission and owns every `.lore/codex/` edit outside `codex/transient/interactive-init-us-*`. They are recorded here so the coverage map has no silent gap, not because a dev story is missing:

1. **FR-35 and the §11 stale-codex rewrites** — `conceptual-workflows-lore-init`, `tech-arch-agents-md`, `tech-arch-initialized-project-structure`, plus the updates to `tech-arch-source-layout`, `tech-overview`, `conceptual-workflows-health`, `ref-lore_cli-commands`, `ref-lore_api-core`, `api-reference`, `api-guide`, `standards-public-api-stability`, `tech-arch-api-facade`, `ops-installation`, `ops-publish-pypi`, `conceptual-workflows-json-output` and `tech-cli-entity-crud-matrix`.
2. **The four new codex documents** — `conceptual-workflows-init-interactive`, `conceptual-workflows-init-reconcile`, `tech-arch-install-manifest`, `tech-arch-skill-catalogue`. These are **preconditions**, not follow-ups: `technical-test-guidelines` §3 requires a `conceptual-workflows-*` document to exist before the E2E file citing it is written, and three new E2E files here depend on the first two.
3. **The five in-place ADR amendments plus one name correction** — ADR-001, ADR-006-id-references, ADR-012, ADR-013, ADR-017 amended in place with a dated `## Status History` row each; `decisions-018-overlays-are-path-discovered-config` takes a name-only body correction (`new-custom-schema` → `update-custom-schema`) with **no** Status History row. No superseding ADR is created and none is marked superseded.

---

## Notes for the Story Grouper and the TDD cycle

**Test-anchor precondition, satisfied.** `tests/e2e/test_init_interactive.py`, `tests/e2e/test_init_reconcile.py` and `tests/e2e/test_health_skills.py` each cite exactly one `conceptual-workflows-*` document, and `technical-test-guidelines` §3 requires that document to exist first. All four new codex documents — `conceptual-workflows-init-interactive`, `conceptual-workflows-init-reconcile`, `tech-arch-install-manifest`, `tech-arch-skill-catalogue` — were confirmed on disk at the time these stories were written, so no dev batch is blocked on them. Every stub citation below names a section heading that exists in the doc it cites.

**Prompt numbering follows the codex, not the Tech Spec.** `conceptual-workflows-init-interactive` numbers the eight prompts by fire order: 1 agents, 2 access mode, 3 skill families, 4 existing instruction file, 5a root `.gitignore`, 5b installed-skill tracking, **6 edited-skill conflict**, **7 apply this plan?**. The Tech Spec's §4.3 walkthrough labels the last two Q7 and Q6 respectively. The stories use the codex numbering throughout, because that is the document the tests cite.

**Six stories are unit-only by nature.** US-002, US-003, US-004, US-005, US-006 and US-011 have no CLI surface of their own — every scenario calls a `lore.*` function or reads packaged data directly. `technical-test-guidelines` §2 and §8 put those in `tests/unit/`, so none of the six creates or extends an E2E file, and none needs a codex anchor. Their user-visible halves are asserted in US-016, US-018 and US-019.

**One spec-tree discrepancy, resolved.** Tech Spec §12's test tree lists `tests/e2e/test_config.py` as extended for the four `init-*` keys and the header regeneration. That file's module docstring anchors it to `conceptual-workflows-glossary`, and `technical-test-guidelines` §3 allows one anchor per E2E file — reconciliation #7 in §18 exists to fix exactly this class of collision. US-013 and US-020 therefore route their E2E coverage to `tests/e2e/test_lore_init.py` (anchor `conceptual-workflows-lore-init`) and keep the loader-level coverage in `tests/unit/test_config.py`. The §14.1 file-assignment table is treated as authoritative over the §12 tree.

**ADR-006 shapes every catalogue story.** `decisions-006-no-seed-content-tests` forbids asserting a field value or a prose string from anything under `src/lore/defaults/`. US-003, US-005, US-006, US-007 and US-010 are written as existence, parseability and structural-completeness assertions throughout. The renderer (US-004) is proved on fixtures authored inside the test file.

**The both-surfaces rule.** US-017 exists because the ADR & Standards Enforcer moved `--agent none` exclusivity out of `cli.py` into `validators.validate_agent_selection`, and the spec gate's closing note requires acceptance criteria to test that rule through both the CLI and `lore.api`. Every criterion in that story is a matched pair. A reviewer who finds a CLI-only assertion there should reject the story as incomplete.

---

## Summary

| Total stories | Epics | Draft | Final |
|---------------|-------|-------|-------|
| 24 | 7 | 0 | 24 |

| Complexity | Count | Stories |
|---|---|---|
| S | 3 | US-001, US-022, US-024 |
| M | 15 | US-002, US-003, US-004, US-006, US-007, US-008, US-010, US-011, US-012, US-013, US-017, US-018, US-020, US-021, US-023 |
| L | 6 | US-005, US-009, US-014, US-015, US-016, US-019 |
| XL | 0 | — |

---

## Dev Cycle Groups

- G1: [interactive-init-us-001, interactive-init-us-002, interactive-init-us-024] — the stdlib-only type layer, the first packaged registry that reads it, and the pyproject declaration (questionary, the click floor, the data glob, 0.10.0) every later story is built against
- G2: [interactive-init-us-003, interactive-init-us-004] — both land in `src/lore/skills.py`: the catalogue data with its retirement ledger, then the access-mode renderer every authored skill body is proved against
- G3: [interactive-init-us-008] — the manifest format and the one hash function — whole-file, rendered-bytes and section digests — that reconciliation, apply and the health scope all read
- G4: [interactive-init-us-009] — L alone: the eleven-row reconciliation table and directory pruning, the algorithm the rest of the feature turns on
- G5: [interactive-init-us-010] — the legacy-hash fallback and its capture script must run while the thirteen pre-consolidation skill directories are still on disk, so it precedes the catalogue rewrite
- G6: [interactive-init-us-005] — L alone: the memory family absorbs seven skills into two authored sources, the largest single content rewrite in the feature
- G7: [interactive-init-us-006, interactive-init-us-007] — the six machinery and workflow renames complete the ten-skill catalogue, and the instruction file's generated table is filled from exactly those ten frontmatter descriptions
- G8: [interactive-init-us-011, interactive-init-us-012, interactive-init-us-013] — the three inputs `plan_init` composes: where skills install, the marked blocks Lore owns inside user-owned files, and the answers `config.toml` records
- G9: [interactive-init-us-014] — L alone: `plan_init` composes every module above into an `InitPlan` and writes nothing
- G10: [interactive-init-us-015] — L alone: `apply_init`, the apply ordering with the manifest written last, and the zero-argument `run_init` wrapper
- G11: [interactive-init-us-016] — L alone: `SpaceSeparatedChoice`, the ten `lore init` flags and the `--help` contract
- G12: [interactive-init-us-017, interactive-init-us-018] — the two thin layers between a raw answer token and `plan_init`: validation that rejects identically on both surfaces, and the lazy questionary prompts that collect the same values
- G13: [interactive-init-us-019] — L alone: the isatty gate, prompt orchestration, the plan summary, the confirm, `--dry-run` and `--reconfigure`
- G14: [interactive-init-us-020, interactive-init-us-021, interactive-init-us-022] — the three adjacent corrections the PRD folded in: the generated config header (FR-36), `lore health --scope skills` (FR-37) and the real schema-version message (FR-38)
- G15: [interactive-init-us-023] — release close-out: the thirteen `lore.api.__all__` names and the `CHANGELOG.md` 0.10.0 entry, which can only land once every one of those names exists
