---
id: conceptual-workflows-doctrine-edit
title: lore doctrine edit Behaviour
summary: What the system does internally when `lore doctrine edit <name>` runs — whole-file mode merges by stem so an unnamed mission is left byte-identical, `--remove-mission` soft-deletes to `<id>.md.deleted` under a last-mission guard, and field-edit mode edits the design document's frontmatter in place. A run with no flags is a usage error at exit 2.
binds:
- src/lore/doctrine.py
- src/lore/cli.py
- src/lore/frontmatter_edit.py
- tests/e2e/test_doctrine_edit.py
- tests/unit/test_doctrine_crud.py
related: ["conceptual-entities-doctrine", "conceptual-workflows-doctrine-new", "conceptual-workflows-doctrine-show", "conceptual-workflows-error-handling", "ref-lore_cli-commands", "ref-lore_doctrine-module", "decisions-003-soft-delete-semantics", "decisions-034-missing-required-combination-is-a-usage-error"]
---

# `lore doctrine edit` Behaviour

`lore doctrine edit <name>` changes one doctrine in place. It has two mutually exclusive modes.

**Whole-file mode** replaces documents:

| Flag | Effect |
|------|--------|
| `-d`, `--design FILE` | replace the design document |
| `-m`, `--mission FILE [FILE ...]` | replace or add missions; the filename stem is the mission id |
| `--remove-mission ID [ID ...]` | soft-delete missions |

**Field-edit mode** edits the design document's frontmatter in place:

| Flag | Effect |
|------|--------|
| `--set KEY=VALUE` | set a frontmatter field |
| `--unset KEY` | remove a frontmatter field |
| `--add KEY=VALUE` | append to a list-typed field |
| `--remove KEY=VALUE` | remove a value from a list-typed field |

The two modes cannot be combined. The design document is the `doctrine` kind in `frontmatter_edit`, validated against `lore://schemas/doctrine-design-frontmatter`.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- A doctrine directory named `<name>` exists somewhere under `.lore/doctrines/`.
- The name is not origin-qualified — a foreign doctrine is never writable.
- At least one flag from one of the two modes is supplied.

## Steps

### 1. Reject a run with nothing to do

A run with no flags at all raises `click.UsageError("Nothing to update: pass -d, -m, or --remove-mission")` — exit 2, stderr, Click's `Error: ` prefix (lore codex show decisions-034-missing-required-combination-is-a-usage-error).

Combining the two modes fails at exit 1 with `Cannot combine -d/--design, -m/--mission or --remove-mission with --set/--unset/--add/--remove.`

### 2. Resolve the doctrine

`update_doctrine` locates the directory through the same subtree-wide resolver `read_doctrine` and `delete_doctrine` use — shallowest match wins — so a seeded doctrine under `default/` is editable. A miss raises `Doctrine "<name>" not found.`

### 3. Validate everything before writing anything

- The design content, when `-d` is passed, is validated exactly as on create: frontmatter present, `id` equal to `<name>`, schema clean.
- Every `-m` mission is validated exactly as on create: valid id, frontmatter `id` equal to the filename stem, schema clean.
- Every `--remove-mission` id must name a live mission: `Mission "<id>" not found in doctrine "<name>"`.
- The **last-mission guard**: the set of live missions, minus the removals, plus the replacements, must not be empty. Otherwise: `Cannot remove every mission: a doctrine keeps at least one mission.`

A validation failure leaves the tree exactly as it was.

### 4. Write

- The design document, when supplied, is replaced through `safewrite.atomic_write_text`.
- Each `-m` mission is written to `missions/<stem>.md` through the same call, creating it when it did not exist.
- Each `--remove-mission` id is renamed `missions/<id>.md` → `missions/<id>.md.deleted` (lore codex show decisions-003-soft-delete-semantics).

**Merge by stem.** A mission nobody names is left byte-identical. Editing one mission never requires re-supplying the rest.

Unlike `lore doctrine new`, the edit path writes per file rather than staging the whole directory: the guarantee is scoped to validation failure, not to a crash mid-write (lore codex show decisions-031-staged-multi-file-entity-write).

## Output

Clause order is fixed — design, replaced, removed — joined with `; `. Each list is sorted by id and joined with `, `.

```
$ lore doctrine edit tdd-feature-lite -m recon.md
Updated doctrine tdd-feature-lite (missions replaced: recon)

$ lore doctrine edit tdd-feature-lite -d design.md
Updated doctrine tdd-feature-lite (design replaced)

$ lore doctrine edit tdd-feature-lite --remove-mission refactor lint
Updated doctrine tdd-feature-lite (missions removed: lint, refactor)

$ lore doctrine edit tdd-feature-lite -d d.md -m recon.md --remove-mission lint
Updated doctrine tdd-feature-lite (design replaced; missions replaced: recon; missions removed: lint)
```

Field-edit mode prints `Updated doctrine <name>`.

**JSON mode (`--json`):**

```json
{"updated": "tdd-feature-lite", "design_replaced": false, "missions_replaced": ["recon"], "missions_removed": []}
```

Exit code 0.

## Python API

```python
from pathlib import Path
from lore.api import update_doctrine

update_doctrine(
    Path("."),
    "tdd-feature-lite",
    design_content,            # str | None
    {"recon": recon_body},     # {mission id: content} | None
    ["lint"],                  # removals | None
)
```

Return shape:

```python
{
    "updated": str,
    "design_replaced": bool,
    "missions_replaced": list[str],   # sorted
    "missions_removed": list[str],    # sorted
}
```

## Failure Modes

| Failure point | Message (stderr) | Exit code |
|---|---|---|
| No flags supplied | `Error: Nothing to update: pass -d, -m, or --remove-mission` | 2 |
| Both modes combined | `Cannot combine -d/--design, -m/--mission or --remove-mission with --set/--unset/--add/--remove.` | 1 |
| Doctrine not found | `Doctrine "<name>" not found.` | 1 |
| Source file missing | `File not found: <path>` | 1 |
| Two `-m` files share a stem | `Duplicate mission id "<stem>": two -m files share a filename stem` | 1 |
| Design id disagrees with the argument | `Design file id "<id>" does not match command argument "<name>"` | 1 |
| Mission id disagrees with its stem | `Mission file id "<declared>" does not match filename stem "<stem>"` | 1 |
| Removal names no live mission | `Mission "<id>" not found in doctrine "<name>"` | 1 |
| Removal would empty the doctrine | `Cannot remove every mission: a doctrine keeps at least one mission.` | 1 |
| Origin-qualified name | `ForeignEntityError` | 1 |

## Out of Scope

- A `lore doctrine mission` subcommand group — per-mission create, replace and remove are flags on this command and nothing else.
- Editing a mission file's frontmatter field by field — a mission's frontmatter is edited by supplying a replacement file.
- Restoring a soft-deleted mission — the `.md.deleted` file is renamed back by hand.

## Related

- conceptual-workflows-doctrine-new (lore codex show conceptual-workflows-doctrine-new) — how doctrine creation works
- conceptual-workflows-doctrine-show (lore codex show conceptual-workflows-doctrine-show) — how doctrine show works
- conceptual-entities-doctrine (lore codex show conceptual-entities-doctrine) — what a doctrine is
- ref-lore_cli-commands (lore codex show ref-lore_cli-commands) — full CLI reference
