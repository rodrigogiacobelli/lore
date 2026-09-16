---
id: conceptual-workflows-doctrine-show
title: lore doctrine show Behaviour
summary: What the system does internally when `lore doctrine show <name>` runs — subtree-wide resolution by directory name, the design document printed verbatim followed by a `--- Missions ---` index, and `--mission <id>` printing one mission body with its frontmatter stripped. Covers both JSON envelopes and the two distinct not-found messages.
binds:
- src/lore/doctrine.py
- src/lore/cli.py
- tests/e2e/test_doctrine_show.py
- tests/unit/test_doctrine.py
related: ["conceptual-entities-doctrine", "conceptual-workflows-doctrine-list", "conceptual-workflows-doctrine-edit", "ref-lore_cli-commands", "ref-lore_doctrine-module", "decisions-033-unresolvable-reference-is-silent-on-read"]
---

# `lore doctrine show` Behaviour

`lore doctrine show <name>` prints a doctrine's design document and an index of its missions in one call. `lore doctrine show <name> --mission <id>` prints that mission's body instead. One call gives an orchestrator everything it needs to plan a quest; a second call gives a worker the body of one mission.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- A doctrine directory named `<name>` exists somewhere under `.lore/doctrines/`, holding `<name>.design.md`.

## Steps

### 1. Resolve the doctrine

`read_doctrine(project_root, name, scope=..., mission=...)` selects the doctrine from the scoped listing by id, then locates its directory on disk by the stem the listing carries. Resolution is subtree-wide and the shallowest match wins, so a doctrine under `default/` resolves the same way as one at the root.

Any path segment beginning with `.` or ending `.deleted` hides everything at and below it, so a soft-deleted doctrine and a half-written staging directory are both invisible here.

A `--mission` value carrying a path separator raises `ValueError` before anything is read: `Invalid mission id: path separators not allowed`.

### 2. Distinguish the two misses

`read_doctrine` returns a bare `None` when **the doctrine** missed, and only then. When the doctrine resolves and the named mission does not, it returns the record with `"mission": None`. A caller tells the two apart from the return value alone.

| Situation | Message (stderr) | Exit code |
|---|---|---|
| Doctrine not found | `Doctrine '<name>' not found` | 1 |
| Doctrine found, mission not found | `Mission "<mission-id>" not found in doctrine "<name>"` | 1 |

The two messages quote differently — the doctrine miss uses single quotes and the mission miss uses double. Each follows its own nearest precedent, and both are strings a consumer may match on.

### 3. Build the record

- `design` is the whole design file read verbatim, frontmatter block included.
- `id`, `title` and `summary` come from the design frontmatter; `title` falls back to the stem and `summary` to `""`.
- `missions` is one record per live `.md` file under `missions/`, sorted by id. Each record is `{id, title, summary}`, where `id` is the filename stem and `title`/`summary` come from that file's frontmatter, falling back to the stem and `""`.
- A mission file whose name begins with `.` is skipped.
- With `--mission <id>`, `mission` is `{id, title, summary, body}` or `None`. The `body` is frontmatter-stripped.

Lore parses nothing else out of either file (lore codex show decisions-029-doctrine-is-prose-not-a-graph).

### 4. Render output

**Text mode, no `--mission`:**

The design document verbatim, then one blank line, then `--- Missions ---`, then one row per mission sorted by id, with the id left-padded to the widest id and two spaces before the title.

```
---
id: tdd-feature-lite
title: TDD Feature Lite
summary: A three-mission TDD cycle.
---

# TDD Feature Lite

## Missions

- **recon** — map the codex and the code surface
- **feature-spec** — write the one planning document
- **scribe** — reconcile the codex

--- Missions ---
feature-spec  Write the feature spec
recon         Map the codex and the binding decisions
scribe        Reconcile the codex against what shipped
```

A doctrine with no `missions/` directory still resolves, and the index reads `(none)`.

**Text mode, with `--mission`:**

The mission body alone, frontmatter stripped, with no trailing newline added.

**JSON mode (`--json`), no `--mission`:**

```json
{"doctrine": {"id": "tdd-feature-lite", "title": "TDD Feature Lite", "summary": "A three-mission TDD cycle.", "design": "---\nid: tdd-feature-lite\n...", "missions": [{"id": "feature-spec", "title": "Write the feature spec", "summary": "..."}], "origin": "self"}}
```

**JSON mode, with `--mission`:**

```json
{"mission": {"id": "recon", "title": "Map the codex and the binding decisions", "summary": "...", "body": "# Recon\n\nYou are Recon...\n"}}
```

Exit code 0 on success. On failure the error envelope `{"error": "<message>"}` goes to stderr with exit code 1.

## Python API

```python
from pathlib import Path
from lore.api import read_doctrine

record = read_doctrine(Path("."), "tdd-feature-lite")
if record is None:
    ...  # the doctrine does not exist

one = read_doctrine(Path("."), "tdd-feature-lite", mission="recon")
if one["mission"] is None:
    ...  # the doctrine exists; the mission does not
```

Return shape:

```python
{
    "id": str,
    "title": str,
    "summary": str,
    "design": str,            # whole design file, frontmatter included
    "missions": list[dict],   # [{"id", "title", "summary"}], sorted by id
    "origin": str,
    # present only when `mission` was passed:
    "mission": dict | None,   # {"id", "title", "summary", "body"}
}
```

## Failure Modes

| Failure point | Message (stderr) | Exit code |
|---|---|---|
| Doctrine directory not found | `Doctrine '<name>' not found` | 1 |
| Mission file not found in a resolved doctrine | `Mission "<id>" not found in doctrine "<name>"` | 1 |
| `--mission` value carries a path separator | `Invalid mission id: path separators not allowed` | 1 |
| `<name>` carries a path separator | `Invalid doctrine name: path separators not allowed` | 1 |

## Out of Scope

- Listing a doctrine's missions as a separate command — the index comes back with the design in one call.
- Editing doctrine content — use `lore doctrine edit`.
- Listing all doctrines — use `lore doctrine list`.

## Related

- conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list) — how doctrine listing works
- conceptual-workflows-doctrine-new (lore codex show conceptual-workflows-doctrine-new) — how doctrine creation works
- conceptual-workflows-doctrine-edit (lore codex show conceptual-workflows-doctrine-edit) — how doctrine editing works
- ref-lore_doctrine-module (lore codex show ref-lore_doctrine-module) — module-level implementation details
- ref-lore_cli-commands (lore codex show ref-lore_cli-commands) — full CLI reference
