---
id: conceptual-entities-watcher
title: Watcher
summary: What a Watcher is — a YAML-configured trigger definition stored in .lore/watchers/ that declares a condition and maps it to an action. Watchers are passive declarations; Lore stores and surfaces them but does not execute them.
related:
  - conceptual-entities-doctrine
  - conceptual-entities-knight
  - conceptual-workflows-watcher-list
  - conceptual-workflows-watcher-crud
  - conceptual-workflows-lore-init
  - tech-arch-initialized-project-structure
  - tech-arch-source-layout
---

# Watcher

A Watcher is a YAML file stored in the project's `.lore/watchers/` directory tree. Each watcher declares a condition — a file change, a git event, a schedule, or a manual invocation — and maps it to an action, typically a Lore doctrine by name. Lore stores and surfaces watcher definitions; it never executes them. Execution is the responsibility of the consuming layer (Realm, a CI pipeline, or a human).

Watchers are deliberately passive. They are declarations, not executors. This keeps Lore's architecture dumb by design (ADR-001) and gives the consuming tool full control over when and how triggers fire.

For CLI commands (`lore watcher new`, `lore watcher list`, etc.) see tech-cli-commands (lore codex show tech-cli-commands).

## YAML Schema

A watcher file is pure YAML (not markdown-with-frontmatter). Three fields are required:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Stable identifier — the filename stem (e.g., `change-log-updates`) |
| `title` | string | Yes | Human-readable name |
| `summary` | string | Yes | One-sentence description |
| `watch_target` | any | No | The trigger target — free-form, untyped. Examples: `main`, `src/**/*.py`, `CHANGELOG.md` |
| `interval` | any | No | The trigger cadence — free-form, untyped. Canonical examples: `on_merge`, `on_file_change`, `daily` |
| `action` | any | No | The action to perform when triggered — typically the name of a Lore doctrine |

The optional fields (`watch_target`, `interval`, `action`) are untyped. Lore stores and returns them as-is without schema enforcement. This is intentional: Lore is the record-keeper; the consuming tool interprets the values.

`lore watcher show <id>` in plain mode returns the raw YAML file content byte-for-byte, including comments. JSON mode returns a structured dict with all 8 keys always present (absent optional fields serialize as `null`).

## Python API

`Watcher` is exported from `lore.models` as a typed, immutable dataclass:

```python
from lore.models import Watcher
```

Fields: `id`, `group`, `title`, `summary`, `watch_target`, `interval`, `action`, `filename`. All fields are always present. Optional fields are `object` type and default to `None` when absent from the YAML file.

`Watcher.from_dict()` accepts both `list_watchers()` output and `load_watcher()` output.

```python
from lore.watcher import find_watcher, load_watcher
from lore.models import Watcher

path = find_watcher(watchers_dir, "change-log-updates")
watcher = Watcher.from_dict(load_watcher(path))
```

Watcher objects are immutable — attempting to assign to any field raises `FrozenInstanceError`.

## Discovery

`lore init` places the bundled default watcher inside `.lore/watchers/default/`. User-created watchers (added via `lore watcher new`) land directly in `.lore/watchers/`. Both `lore watcher list` and `lore watcher show` search the full `.lore/watchers/` directory tree recursively — they discover watchers regardless of which subdirectory the file lives in.

`lore watcher list` returns a single flat merged list of all watchers found anywhere in the tree, sorted alphabetically by `id`. No subdirectory annotation or `(default)` label is shown.

`lore watcher show <id>` resolves a watcher by its filename stem (e.g., `change-log-updates` for `change-log-updates.yaml`). The search is recursive across the full tree.

## Default Watcher

`lore init` seeds one default watcher: `change-log-updates`. It watches for merges to `main` and triggers the `update-changelog` doctrine. Both the watcher and its companion doctrine (`update-changelog`) are seeded together — every new project gets an immediately usable automation hook with zero configuration.

```yaml
id: change-log-updates
title: Update Changelog
summary: Watches for merges to main and triggers the update-changelog doctrine

watch_target: main
# Canonical interval examples: on_merge | on_file_change | daily
interval: on_merge
action: update-changelog
```

## Soft-Delete Semantics

Watchers are soft-deleted by renaming the YAML file with a `.deleted` suffix. The `rglob("*.yaml")` discovery pattern naturally excludes `.yaml.deleted` files. Creating a new watcher with the same name as a soft-deleted one succeeds; the old `.deleted` file is left as-is.

## Related

- Doctrine (lore codex show conceptual-entities-doctrine) — the `action` field in a watcher typically names a doctrine to run
- Knight (lore codex show conceptual-entities-knight) — doctrines triggered by watchers reference knight files
- conceptual-workflows-watcher-list (lore codex show conceptual-workflows-watcher-list) — `lore watcher list` and `lore watcher show` behaviour
- conceptual-workflows-watcher-crud (lore codex show conceptual-workflows-watcher-crud) — `lore watcher new/edit/delete` behaviour
- conceptual-workflows-lore-init (lore codex show conceptual-workflows-lore-init) — how the default watcher is seeded
- tech-cli-commands (lore codex show tech-cli-commands) — `lore watcher` command reference
- tech-arch-source-layout (lore codex show tech-arch-source-layout) — `watcher.py` module internals
