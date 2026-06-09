---
id: conceptual-workflows-rite-search
title: lore rite search Behaviour
summary: What the system does internally when `lore rite search <keyword>` runs — a case-insensitive substring keyword browse over id/title/summary/trigger of main rites (NOT the deferred situational matcher), the same table shape and JSON envelope as rite list, and the no-match message.
binds:
- src/lore/rite.py
- src/lore/cli.py
- tests/e2e/test_rite_search.py
- tests/unit/test_rite.py
related:
  - conceptual-entities-rite
  - conceptual-workflows-rite-list
  - conceptual-workflows-codex
  - conceptual-workflows-json-output
  - decisions-016-rite-json-envelope-omits-group
  - ref-lore_cli-commands
---

# `lore rite search` Behaviour

`lore rite search <keyword>` is a **keyword browse** over main rites — a
case-insensitive substring match. It is **not** the deferred situational matcher:
Lore never matches a "situation"; retrieval is AI-as-matcher (the agent reads
`lore rite list`/`search` output and picks). Situational scoring is out of scope
for this version and must not be documented as shipping (see
conceptual-entities-rite).

## Preconditions

- The Lore project has been initialised.

## Steps

### 1. Match

`search_rites(rites_dir, query)` scans `.lore/rites/main/**/*.yaml`
**recursively** (skipping `.yaml.deleted`) and returns every main rite whose
`id`, `title`, `summary`, or `trigger` contains `query` as a case-insensitive
substring. This mirrors `lore codex search` over id/title/summary and **adds
`trigger`** because the trigger is the retrieval cue agents browse. Shared steps
are not searched.

### 2. Render output

Same columns as `lore rite list` (main): `ID`, `TRIGGER`, `SUMMARY`.

**No match (text):** `No rites matching "<keyword>".` (exit 0; mirrors codex
search — a miss is success, not an error).

### 3. JSON mode

```json
{"rites": [{"id": "issue-refund", "trigger": "...", "summary": "..."}]}
```

Only matching rites appear. The search envelope reports the match cues
(`id`/`trigger`/`summary`); `group` is the organisational axis surfaced by `rite
list` (decisions-016-rite-json-envelope-omits-group). Empty match →
`{"rites": []}`.

## Python API

```python
from lore.api import search_rites
from pathlib import Path

hits = search_rites(Path(".lore/rites"), "refund")   # list[dict] of matching main rites
```

CLI and Python behaviour are identical (ADR-011).

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Not a Lore project | shared CLI guard error | 1 |

A no-match result is exit 0, not an error.

## Out of Scope

- Situational / semantic matching — deferred, not built. `search` is substring browse only.
- Searching shared steps — `search` targets main rites.
- Ordering by relevance/score — no scoring signal exists in this version.

## Related

- conceptual-entities-rite (lore codex show conceptual-entities-rite) — AI-as-matcher retrieval, deferred scoring
- conceptual-workflows-rite-list (lore codex show conceptual-workflows-rite-list) — the listing this shares its shape with
- conceptual-workflows-codex (lore codex show conceptual-workflows-codex) — the codex search precedent
- ref-lore_cli-commands (lore codex show ref-lore_cli-commands) — full CLI reference
