---
id: ref-lore_doctrine-module
title: Lore doctrine module — internals
summary: Reference doc for `src/lore/doctrine.py` — the directory model (a design
  document plus a missions/ directory), the one skip rule that hides soft-deleted and
  staging directories, the strict/permissive resolver pair, the ten-rule validation
  order, and the staged directory write. Source of truth is the module plus its two
  JSON Schemas.
binds:
- src/lore/doctrine.py
- tests/unit/test_doctrine.py
- tests/unit/test_doctrine_crud.py
- tests/e2e/test_doctrine_list.py
- tests/e2e/test_doctrine_new.py
- tests/e2e/test_doctrine_show.py
- tests/e2e/test_doctrine_edit.py
related:
- conceptual-entities-doctrine
- conceptual-workflows-doctrine-edit
- ref-lore_cli-commands
- tech-arch-source-layout
- decisions-006-id-references
- decisions-029-doctrine-is-prose-not-a-graph
- decisions-031-staged-multi-file-entity-write
- tech-arch-schemas
---

# Lore doctrine module — internals

**Covers:** `lore.doctrine`, `list_doctrines`, `read_doctrine`, `create_doctrine`, `update_doctrine`, `delete_doctrine`, `load_mission_sources`, `_find_doctrine_dir`, `_resolve_doctrine_mission`, `_split_doctrine_mission_ref`, `_doctrine_dirs`, `_is_skipped`, `_mission_index`, `_mission_record`, `_validate_design_content`, `_validate_mission_sources`, `DoctrineListEntry`
**Source of truth:** `src/lore/doctrine.py` (logic), `src/lore/schemas/doctrine-design-frontmatter.yaml` and `src/lore/schemas/doctrine-mission-frontmatter.yaml` (schemas).

## Why this exists

A doctrine is a directory: `D` is one if and only if `D/<D.name>.design.md` exists, and its missions are the `.md` files under `D/missions/`. This module owns discovery, reading, creation, editing and deletion. Lore reads frontmatter for identity and treats every body as an opaque string — there is no workflow structure to parse (lore codex show decisions-029-doctrine-is-prose-not-a-graph). Most of the complexity is in the two resolvers and in delegating shape checks to JSON Schemas so create-time and audit-time validation never diverge.

## Gotchas

- **One skip rule hides three things.** `_is_skipped` returns true for any path segment that starts with `.` or ends `.deleted`. That single rule makes a soft-deleted doctrine directory, a soft-deleted mission file and the staging directory `create_doctrine` builds all invisible to discovery, to reads and to `lore health`, with no second mechanism.

- **The design file's name is derived from the directory name, not stored.** `doctrine_design_path(D)` returns `D / f"{D.name}.design.md"`. A design file whose name does not match its parent directory identifies no doctrine and is skipped by `_doctrine_dirs`. That equality is what makes the directory the unit of identity.

- **Two resolvers, deliberately asymmetric.** `_find_doctrine_dir` is **strict**: the name comes from a user, so a path separator is refused outright via `_reject_traversal`. `_resolve_doctrine_mission` is **permissive**: a stored reference legitimately carries the one separator between doctrine and mission, so `_split_doctrine_mission_ref` accepts exactly two segments and refuses an absolute path, any `..`, and any other shape. Confusing the two is how a stored reference climbs out of `.lore/doctrines/`.

- **Both resolvers read Windows separators.** `_reference_path` runs a reference through `PureWindowsPath(...).as_posix()`, so a reference a Windows-side author stored resolves identically here.

- **`_find_doctrine_dir` is subtree-wide, shallowest match first.** Sorted by `(depth, path)`. This is what makes a seeded doctrine under `default/` reachable by `read_doctrine`, `update_doctrine` and `delete_doctrine` alike.

- **A bare `None` from `read_doctrine` means the DOCTRINE missed, and only that.** When the doctrine resolves and the named mission does not, the returned dict carries `"mission": None`. A caller distinguishes the two misses from the return value alone — which is what lets the CLI print two different messages.

- **`_resolve_doctrine_mission` returns `None` rather than raising.** A read never raises on a reference that does not resolve (lore codex show decisions-033-unresolvable-reference-is-silent-on-read). `health.py` imports the same function so it asks the question this module answers rather than re-deriving it.

- **A mission's id is its filename stem, not its frontmatter `id`.** `_mission_record` keys on `path.stem`. The frontmatter `id` is validated to match at write time and by `lore health --scope doctrines`, but the stem is what a read addresses.

- **`_frontmatter_mapping` keeps every key; `parse_frontmatter_doc` keeps a subset.** Schema validation needs the mapping exactly as written, because `additionalProperties: false` can only report an unexpected key it can see. That is why this module carries its own frontmatter reader alongside the shared one.

- **Validation order is total, and rules 7–9 are breadth-first.** `create_doctrine` runs ten rules before any disk write: foreign-id → name → group → duplicate (subtree-wide) → design frontmatter id → design schema → at least one mission → mission ids → mission id-vs-stem → mission schemas. Each of the last three runs across every mission before the next starts, so the first failure a caller sees is the earliest *rule*, not the earliest file.

- **Shape validation lives in JSON Schema, not inline.** `_validate_design_frontmatter` and `_validate_mission_sources` are thin wrappers around `lore.schemas.validate_entity`. Required fields and `additionalProperties: false` live in the schema files. Adding inline shape checks here is a divergence risk.

- **Cross-field rules stay in code.** Three checks the schema cannot express: the design `id` must equal the `name` argument; a mission's frontmatter `id` must equal its filename stem; and the id-presence check runs *before* full validation so an id complaint surfaces ahead of any other schema issue.

- **`create_doctrine` stages; `update_doctrine` does not.** Create builds the whole tree in `.lore/doctrines/.<name>.lore-tmp/<name>/` and arrives by one `os.replace`. Edit validates everything first and then writes per file — its guarantee is scoped to validation failure, not to a crash mid-write (lore codex show decisions-031-staged-multi-file-entity-write).

- **`update_doctrine` merges by stem.** A mission nobody names is left byte-identical. The last-mission guard runs on `(live - removals) | replacements`, so a removal that would empty the doctrine is refused even when a replacement is supplied in the same call.

- **`load_mission_sources` owns the duplicate-stem rule, not `cli.py`.** A Python caller passing a `dict` physically cannot express two files sharing a stem; the mistake exists only on the path-list side, and so does its check. Putting it in `cli.py` would give the rule a home only the CLI can reach.

- **Every write calls `projects.reject_foreign` first.** Cross-project reads are read-only (`decisions-025`).

- **`delete_doctrine` renames the directory.** `<name>` → `<name>.deleted`. The skip rule then makes it invisible everywhere.

- **Discovery order is path order, not id order.** `list_doctrines` walks the tree and never sorts by id, so a merged cross-project listing concatenates each project's own order.

## Shape

| Function | Returns | Notes |
|----------|---------|-------|
| `list_doctrines` | `list[dict]` (per-entry: `id`, `group`, `title`, `summary`, `valid=True`, `filename`, `origin`) | No missions. `filename` is `<stem>.design.md`. |
| `read_doctrine` | `dict \| None` (`id`, `title`, `summary`, `design`, `missions`, `origin`) | Plus `mission`: `{id, title, summary, body}` or `None`, when `mission=` is passed. `design` is the whole file; a mission `body` is frontmatter-stripped. |
| `create_doctrine` | `dict` (`created`, `group`, `missions`, `path`) | `missions` sorted; `path` is the repo-relative directory with a trailing `/`. |
| `update_doctrine` | `dict` (`updated`, `design_replaced`, `missions_replaced`, `missions_removed`) | Both lists sorted. |
| `delete_doctrine` | `dict` (`id`, `deleted=True`, `deleted_at=None`) | |
| `load_mission_sources` | `dict[str, str]` | Internal. Raises on a missing file or a duplicate stem. |

## Schemas (pointer)

- `src/lore/schemas/doctrine-design-frontmatter.yaml` — required `id`, `title`, `summary`; `additionalProperties: false`.
- `src/lore/schemas/doctrine-mission-frontmatter.yaml` — required `id`, `title`, `summary`; `additionalProperties: false`; `id` must match the filename stem.

Both are loaded once per process. Audit-time validation in `lore health` runs the same schemas — adding a new constraint means editing the schema file, not the module.
