---
id: group-param-technical-map
title: Context Map — --group param for lore new commands (technical)
summary: Technical-lens context map for implementing --group on lore doctrine/knight/watcher/artifact new, covering modules, validators, paths helper, list display switch, and Python API parity.
type: context-map
lens: technical
---
# Context Map — --group param for `lore new` commands (technical)

**Author:** Scout (technical lens)
**Date:** 2026-04-14
**Feature:** Add `--group` param to `lore doctrine|knight|watcher|artifact new` with nested path support, auto-mkdir subtree, null group = entity root. Switch list GROUP column display from `-` to `/`; audit `--json`. CLI + Python API parity.
**Lens:** _technical_

---

## Relevant Documents

| ID | Title | Why relevant |
|----|-------|-------------|
| `tech-arch-source-layout` | Source Layout | Canonical module map. Identifies exactly where create logic lives — `doctrine.py` (`create_doctrine`), `knight.py` (`list_knights`, `find_knight`, no create yet), `watcher.py` (`create_watcher`/`update_watcher`/`delete_watcher`), `artifact.py` (read-only today), `paths.py` (`derive_group`). |
| `tech-doctrine-internals` | Doctrine Module Internals | Exact signature of `create_doctrine(name, yaml_src, design_src, doctrines_dir)` that must gain a `group` param and write to `doctrines_dir / group / <name>.*` with mkdir. Also shows `list_doctrines(doctrines_dir, filter_groups=None)` output shape including the `group` key fed from `paths.derive_group`. |
| `tech-arch-knight-module` | Knight Module Internals | `knight.py` current public surface — `list_knights`, `find_knight` with path-traversal guard. Creating a knight today is inlined in `cli.py`; the feature must either extract a `create_knight()` helper or thread `--group` through existing inline code. Path-traversal guard is the template for group validation. |
| `tech-arch-validators` | Validators Module Internals | Location for a new `validate_group` (analogous to `validate_name`). Must reject `..`, absolute paths, backslashes, leading/trailing slashes, empty segments — same hardening style as the existing knight path-traversal guard. Must have zero `lore.*` imports. |
| `tech-api-surface` | Python API Entity CRUD Matrix | Enumerates every public Python API create entrypoint. Shows which functions Realm calls and must stay in parity. Baseline for the new `group=` kwarg surface area. |
| `tech-cli-entity-crud-matrix` | CLI Entity CRUD Matrix | Current CLI create commands for each entity. Shows Artifact and Codex have no create path — confirms artifact `new` is a new subcommand, not an extension. |
| `tech-cli-commands` | CLI Command Reference | Full reference agents rely on. Every flag addition, help text, and JSON schema change for `new` and `list` commands must land here in lock-step. |
| `conceptual-workflows-doctrine-new` | lore doctrine new Behaviour | Full behavioural spec of `doctrine new` — validation order, failure modes, JSON success envelope. The `--group` flag must slot into step 2 (duplicate check across the whole subtree, already rglob) and step 5 (write path is subtree, must mkdir). |
| `conceptual-workflows-knight-crud` | Knight CRUD Operations | Current create/edit/delete contract for knights. Name validation rules are shared with doctrine. Duplicate detection and subtree lookup semantics define how `--group` interacts with `edit`/`delete` lookups. |
| `conceptual-workflows-watcher-crud` | Watcher CRUD Operations | Baseline for `watcher new`; rglob duplicate-detect pattern to replicate. |
| `conceptual-workflows-filter-list` | lore * list --filter Behaviour | Filter uses hyphen-joined tokens today. Switching GROUP display to `/` forces a decision: translate at display-only or migrate the filter input grammar too. Direct blocker on the `-` → `/` change. |
| `conceptual-workflows-doctrine-list` | lore doctrine list Behaviour | GROUP column rendering spec for doctrines — exact site of the `-` → `/` display change. |
| `conceptual-workflows-knight-list` | lore knight list Behaviour | Same, for knights. |
| `conceptual-workflows-watcher-list` | lore watcher list Behaviour | Same, for watchers; covers `--json` envelope. |
| `conceptual-workflows-artifact-list` | lore artifact list Behaviour | Contains the clearest nested-group example (`default/codex/overview.md` → `default-codex`) that must render as `default/codex`. |
| `conceptual-workflows-json-output` | JSON Output Mode | Envelope contract; defines which keys change when GROUP switches to `/`. Required reading for the `--json` audit. |
| `conceptual-workflows-help` | Help Output Contract | Enriched help is a hard contract. `--group` must be taught in each `new` subcommand help text. |
| `conceptual-workflows-validators` | Input Validation | Where `validate_name` is wired (CLI + db). Same wiring pattern applies to the new `validate_group`. |
| `conceptual-workflows-lore-init` | lore init Behaviour | `lore init` seeds defaults into subtree (`doctrines/feature-implementation/...`, `knights/default/...`, `artifacts/transient/...`, `artifacts/codex/...`). The directory layout `--group` produces must match what init already lays down. |
| `tech-arch-initialized-project-structure` | Initialized Project Structure | Authoritative on-disk layout of `.lore/`; defines the target directory each `new` command writes into. |
| `standards-single-responsibility` | Single Responsibility | CLI handler translates terminal I/O only; `--group` semantics (mkdir, path building, validation) live in core modules, not in `cli.py`. |
| `standards-separation-of-concerns` | Separation of Concerns | Mandates `cli.py` does not own business rules. `create_doctrine`/`create_knight`/etc. own the group path, not the click handler. |
| `standards-dependency-inversion` | Dependency Inversion | `validators.py` stays free of `lore.*` imports — `validate_group` follows that rule. |
| `standards-dry` | DRY — Don't Repeat Yourself | Canonical homes: path construction in `paths.py`, validation in `validators.py`. Group path join/mkdir logic must be added to `paths.py`, not reimplemented per entity. |
| `decisions-011-api-parity-with-cli` | Python API must be safe and behaviourally equivalent to the CLI | Mandates `create_doctrine(..., group=None)` etc. enforce group validation + mkdir internally; CLI is a thin wrapper. No CLI-only pre-validation allowed. |
| `decisions-012-multi-value-cli-param-convention` | Multi-value CLI parameters use space-separated syntax | `--group` is single-valued scalar — this ADR rules it out of the multi-value convention and sets the precedent that multi-value flags stay reserved for list params. |
| `decisions-008-help-as-teaching-interface` | CLI --help is the primary teaching interface for AI agents | Every new flag must update the enriched help block for its command group. Non-negotiable. |
| `decisions-001-dumb-infrastructure` | Dumb infrastructure design principles | Guardrail: `--group` should be a thin path wrapper. No clever group metadata store, no symlinks, no rename on group change. |
| `technical-test-guidelines` | Test Authorship Guidelines | Two-tier model (unit + E2E) and codex anchoring — every new behaviour (group validation, nested mkdir, `/` display) needs both tiers plus a codex anchor reference. |
| `tech-overview` | Technical Overview | Technology stack (Click, PyYAML). Confirms `--group` must be wired as a Click option on the four `new` handlers. |
| `conceptual-workflows-health` | lore health Behaviour | Audits on-disk entity trees. New `--group` subtree writes must remain valid under `lore health` scans. |

---

## How to Use This Map

Every agent that receives this map should:
1. Run `lore codex show <id1> <id2> ...` with all IDs in the table above
2. Read every document listed before starting their mission
3. Do not explore the codex independently — this map is your entry point

---

## Scout Notes

- `paths.derive_group(filepath, base_dir)` currently joins directory components with `-`. That is the single source of the hyphen token used everywhere — list display, filter matching, JSON envelopes. Options for the `/` switch: (a) add a sibling `derive_group_display` (or param) that joins with `/` and keep `derive_group` hyphen-based for filter keys, or (b) migrate the group canonical form to `/` and update filter matching. Option (a) is lower blast radius; option (b) is cleaner semantically. PRD needs to pick.
- `create_doctrine` currently writes flat into `doctrines_dir` (see `tech-doctrine-internals`). Adding `group` means writing to `doctrines_dir / Path(group) / <name>.yaml` and mkdir'ing with `parents=True, exist_ok=True`. Duplicate check is already `rglob` so a name collision anywhere in the subtree still fires — good.
- Knight create is NOT in `knight.py` today — it's still inline in `cli.py` per the source layout. The feature is a natural moment to extract `create_knight()` into `knight.py`, matching the `doctrine.py` / `watcher.py` shape. Same for artifact if `artifact new` is being added (artifact.py is currently read-only).
- `validate_name` in `validators.py` is the template for `validate_group`. Key differences: groups may contain `/`, must not contain `..`, `\\`, leading/trailing `/`, empty segments, or absolute paths. Reuse the per-segment alphanumerics+hyphen+underscore rule from `validate_name` on each segment.
- `find_knight` has a path-traversal guard rejecting `/` and `\\` in names — that guard assumes names are stems, not paths. Adding groups does NOT change that invariant; the group is a separate parameter, not part of the name. Preserve the guard.
- `lore health` scans on-disk entities; confirm it already handles arbitrarily deep subdirs (it does — `filter_list` and list commands use `rglob`). No health change expected.
- Test anchoring per `technical-test-guidelines` will need E2E tests for: nested group create, mkdir idempotency, duplicate across subtree, null group = root, display `/` in table + JSON, `--filter` behaviour under the chosen delimiter policy, Python API parity.
- No dedicated `paths.py` codex doc exists — `tech-arch-source-layout` is the only authoritative reference for `derive_group` and `paths.py` helpers. Consider adding a `tech-arch-paths` doc after this feature ships.
