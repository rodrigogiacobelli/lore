---
id: group-param-business-map
title: Context Map — --group param for lore new commands (business)
summary: Business-lens context map for adding --group param to lore doctrine/knight/watcher/artifact new commands, plus switching list GROUP column display from '-' to '/' separator.
type: context-map
lens: business
---
# Context Map — --group param for `lore new` commands (business)

**Author:** Scout (business lens)
**Date:** 2026-04-14
**Feature:** Add `--group` param to `lore doctrine|knight|watcher new` (and artifact creation) accepting nested paths (e.g. `seo-analysis/keyword-analysers`), auto-create subdirs, null group = entity root; switch all `list` GROUP column from `-` to `/` separator (audit `--json` too). Codex has no `new`, list display only.
**Lens:** _business_

---

## Relevant Documents

| ID | Title | Why relevant |
|----|-------|-------------|
| `conceptual-entities-doctrine` | Doctrine | Defines the Doctrine entity, its two-file model (`.yaml` + `.design.md`), and its lifecycle — the primary entity `--group` must support on create. |
| `conceptual-entities-knight` | Knight | Defines the Knight entity (markdown persona) — second entity targeted by `--group` on `knight new`. |
| `conceptual-entities-watcher` | Watcher | Defines the Watcher entity (YAML trigger) — third entity targeted by `--group` on `watcher new`. |
| `conceptual-entities-artifact` | Artifact | Defines the Artifact entity and the two shipped namespaces (`transient/`, `codex/`); artifact is fourth entity in scope. Note: artifact currently has no CLI write path — confirm whether `new` is being added. |
| `conceptual-workflows-doctrine-new` | lore doctrine new Behaviour | Existing create workflow for doctrines — name validation rules, duplicate detection, atomic two-file write. Baseline the `--group` param must extend without breaking. |
| `conceptual-workflows-knight-crud` | Knight CRUD Operations | Existing create/edit/delete semantics for knights, including shared name validation rules. Baseline for `knight new --group`. |
| `conceptual-workflows-watcher-crud` | Watcher CRUD Operations | Existing create/edit/delete semantics for watchers — duplicate detection via rglob, name validation. Baseline for `watcher new --group`. |
| `conceptual-workflows-doctrine-list` | lore doctrine list Behaviour | Describes the GROUP column output and hyphen-joined group derivation from subdirectory path — directly impacted by the `-` → `/` display change. |
| `conceptual-workflows-knight-list` | lore knight list Behaviour | Same hyphen-joined group derivation and table/JSON output — impacted by GROUP display change and `--json` audit. |
| `conceptual-workflows-watcher-list` | lore watcher list Behaviour | Same GROUP column contract for watchers, table + JSON — impacted by display change. |
| `conceptual-workflows-artifact-list` | lore artifact list Behaviour | GROUP column for artifacts including nested-group examples (`default/codex/overview.md` → `default-codex`) — exact case the `-` → `/` switch targets. |
| `conceptual-workflows-filter-list` | lore * list --filter Behaviour | Spec of how group tokens are matched today (subtree prefix match on `-` joined tokens). Switching to `/` display must not regress `--filter` semantics; the doc will need updating in lock-step. |
| `conceptual-workflows-help` | Help Output Contract | Enriched `--help` is the primary teaching interface for agents — adding `--group` means updating the help contract for four `new` subcommands. |
| `decisions-008-help-as-teaching-interface` | CLI --help is the primary teaching interface for AI agents | ADR mandating enriched `--help`. New `--group` flag plus changed GROUP column must be taught here. |
| `decisions-011-api-parity-with-cli` | Python API must be safe and behaviourally equivalent to the CLI | Mandates that `--group` behaviour lives in the core module (not the CLI layer) so `lore.models`/`lore.doctrine`/`lore.knight`/etc. consumers (Realm) get the same create semantics. |
| `decisions-012-multi-value-cli-param-convention` | Multi-value CLI parameters use space-separated syntax | `--group` is single-valued; this ADR is relevant as the counter-example and to confirm the convention being followed here (scalar string, slash-delimited, not repeatable). |
| `conceptual-entities-quest` | Quest | Background: `quest new` already exists without a group concept — scope boundary check (feature explicitly excludes quest/mission). |
| `conceptual-entities-mission` | Mission | Same scope-boundary reason; missions have no group. |
| `conceptual-workflows-lore-init` | lore init Behaviour | `lore init` seeds default doctrines, knights, artifacts into nested subdirs — establishes the directory convention `--group` will mirror at create time. |
| `conceptual-workflows-typical-workflow` | Typical Workflow | End-to-end orchestrator journey; where `--group` fits (organising a growing set of knights/doctrines per feature area, e.g. `seo-analysis/`). |
| `conceptual-workflows-json-output` | JSON Output Mode | Envelope contract; the `--json` audit for `list` GROUP and `new` confirmation output falls under this contract. |
| `decisions-001-dumb-infrastructure` | Dumb infrastructure design principles | Design principle check — `--group` is trivial path glue, must not become clever. Directly drives the "just auto-mkdir the subtree" decision. |

---

## How to Use This Map

Every agent that receives this map should:
1. Run `lore codex show <id1> <id2> ...` with all IDs in the table above
2. Read every document listed before starting their mission
3. Do not explore the codex independently — this map is your entry point

---

## Scout Notes

- Codex already uses hyphen-joined group tokens across list commands, `--filter`, and group derivation in `paths.derive_group`. Switching display to `/` affects three surfaces: human table column, `--json` output, and any doc examples. The underlying filter matching algorithm uses hyphen tokens today — either the algorithm switches to `/` or the display layer translates on output only. This is a business-visible decision (users will type `--filter seo-analysis/keyword-analysers` vs `--filter seo-analysis-keyword-analysers`).
- `conceptual-workflows-filter-list` documents group tokens correspond to subdirectory names joined with hyphens — it will need an update in lock-step with whatever delimiter policy ships.
- Artifact has no existing CLI write path per `tech-cli-entity-crud-matrix`. The mission says "doctrine/knight/watcher/artifact" — this implies artifact is also getting a `new` command, which is a larger scope than just adding `--group`. PRD author should confirm.
- No glossary, persona, or user-research docs found in the codex — the "business" side here is mostly the entity definitions and the public workflow contracts (list/new behaviours + help teaching contract).
- Quest/mission explicitly out of scope (they are DB entities, not file entities, and have no group concept).
