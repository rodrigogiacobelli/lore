---
id: conceptual-workflows-rite-list
title: lore rite list Behaviour
summary: What the system does internally when `lore rite list` runs — recursive main-only listing by default, --shared to list reusable steps, the ID/GROUP/TRIGGER/SUMMARY (main) vs ID/GROUP/TITLE/SUMMARY (shared) columns, the --filter group flag, the JSON envelopes that carry the group key (root → null) and the shared summary field, empty-state messages, and Python API parity via scan_rites.
binds:
- src/lore/rite.py
- src/lore/cli.py
- tests/e2e/test_rite_list.py
- tests/unit/test_rite.py
related:
  - conceptual-entities-rite
  - conceptual-workflows-rite-show
  - conceptual-workflows-rite-search
  - conceptual-workflows-rite-crud
  - conceptual-workflows-json-output
  - decisions-016-rite-json-envelope-omits-group
  - ref-lore_cli-commands
---

# `lore rite list` Behaviour

`lore rite list` lists the project's rites (lore codex show
conceptual-entities-rite). By default it lists **main** rites only. `--shared`
switches to listing **shared steps** only. The two subfolders are never mixed in
one listing — agents reach shared steps through a main rite's `use:` and rarely
browse them directly.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).

## Steps

### 1. Scan the relevant subfolder (recursively)

`scan_rites(rites_dir, *, shared=False)` walks `.lore/rites/main/**/*.yaml` by
default, or `.lore/rites/shared/**/*.yaml` when `shared=True` — both
**recursive**. `.yaml.deleted` files are skipped (soft-delete, watcher
precedent). Each record carries a `group` derived from its path relative to
`main/`/`shared/` (root → `""`). Output is sorted by `(group, id)`.

### 2. Apply `--filter` (optional)

`--filter GROUP…` (space-separated, ADR-012) narrows the listing to the named
group(s) by segment-prefix match, like every other `list` command
(conceptual-workflows-filter-list). An empty token (`""`/`/`) is a usage error.

### 3. Render output

Uses the shared `_format_table` helper.

**Main rites** — columns `ID`, `GROUP`, `TRIGGER`, `SUMMARY`:
```
ID            GROUP               TRIGGER                                      SUMMARY
issue-refund  diagnostics/refund  Customer requests a refund on a returned...  Confirm the customer is reachable, then refund.
```

**Shared steps (`--shared`)** — columns `ID`, `GROUP`, `TITLE`, `SUMMARY` (shared
steps carry a `summary` but no `trigger` — `trigger` is MAIN-rite-only):
```
ID                 GROUP  TITLE                                 SUMMARY
read-contact-info  io     Read the user's contact information   Look up the customer's email and phone on file.
```

**Empty state (text):**
- main → `No rites found.` (exit 0)
- `--shared` → `No shared steps found.` (exit 0)

### 4. JSON mode

`lore rite list` accepts the global `--json` (`lore --json rite list`) and a
local `--json` (`lore rite list --json`), mirroring `artifact list`/`knight
list`/`doctrine list`. Double-declaration is harmless.

Main:
```json
{"rites": [{"id": "issue-refund", "group": null, "trigger": "Customer requests a refund on a returned order.", "summary": "Confirm the customer is reachable, then refund."}]}
```
`--shared`:
```json
{"shared_steps": [{"id": "read-contact-info", "group": null, "title": "Read the user's contact information", "summary": "Look up the customer's email and phone on file."}]}
```
Each `shared_steps[]` entry carries `id`, `group`, `title`, and `summary`
(`summary` always present, never absent).

The `group` key **IS** included (root → `null`), like every other entity
(decisions-016-rite-json-envelope-omits-group) — there is no rite carve-out in
conceptual-workflows-json-output. The field-presence-always rule holds: an empty
result is `{"rites": []}` / `{"shared_steps": []}`, never an absent key.

## Python API

```python
from lore.api import scan_rites
from pathlib import Path

rites_dir = Path(".lore/rites")
main_rites = scan_rites(rites_dir)                 # list[dict] of main rites
shared_steps = scan_rites(rites_dir, shared=True)  # list[dict] of shared steps
```

`scan_rites` returns listing dicts (id + group + trigger/summary for main; id +
group + title + summary for shared), recursively discovered. CLI and Python
behaviour are byte-identical (ADR-011).

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Not a Lore project | `{"error": "Not a Lore project: no .lore/ directory found."}` (shared CLI guard) | 1 |

No list-specific errors. An empty store is success, not an error.

## Out of Scope

- Listing main and shared in a single call — use two invocations.
- Reading a rite's full node-graph — use `lore rite show` (conceptual-workflows-rite-show).

## Related

- conceptual-entities-rite (lore codex show conceptual-entities-rite) — what a Rite is
- conceptual-workflows-rite-show (lore codex show conceptual-workflows-rite-show) — reading one rite with shared-step inlining
- conceptual-workflows-rite-search (lore codex show conceptual-workflows-rite-search) — keyword browse
- decisions-016-rite-json-envelope-omits-group (lore codex show decisions-016-rite-json-envelope-omits-group) — why rites carry `group`
- conceptual-workflows-filter-list (lore codex show conceptual-workflows-filter-list) — the shared `--filter` semantics
- ref-lore_cli-commands (lore codex show ref-lore_cli-commands) — full CLI reference
