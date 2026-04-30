---
id: conceptual-workflows-glossary
title: Glossary Commands — lore glossary and auto-surface
summary: >
  What the system does internally when `lore glossary list/search/show` runs,
  when `lore codex show` auto-surfaces matched glossary entries, and when
  `--skip-glossary` overrides per call. Covers the shared tokeniser, the
  fail-soft policy on `lore codex show`, the fail-loud policy on `lore glossary`
  and `lore health`, the JSON envelope shape, and the `.lore/config.toml` toggle.
related:
  - conceptual-entities-glossary
  - conceptual-workflows-codex
  - conceptual-workflows-health
  - conceptual-workflows-lore-init
  - conceptual-workflows-error-handling
  - conceptual-workflows-json-output
  - conceptual-workflows-help
  - decisions-013-toml-for-config-yaml-for-glossary
  - decisions-012-multi-value-cli-param-convention
  - tech-cli-commands
  - tech-arch-schemas
---

# Glossary Commands — `lore glossary` and auto-surface

The Glossary entity (lore codex show conceptual-entities-glossary) has three operating surfaces: the read-only `lore glossary` CLI group, the auto-surface block appended by `lore codex show`, and the schema/collision/deprecated-term audit run by `lore health` (lore codex show conceptual-workflows-health). This document covers the first two; the health surface is documented inside `conceptual-workflows-health`.

All three surfaces share a single normaliser implemented in `lore.glossary` — `_normalise_tokens(text)` and `_build_lookup(items)`. Auto-surface and the deprecated-term scan are two presentation policies over one matcher.

## Preconditions

- The Lore project has been initialised (`.lore/` exists).
- `.lore/codex/glossary.yaml` exists (created by `lore init` as a skeleton; user-edited thereafter).
- Optional: `.lore/config.toml` exists. If absent or missing the relevant key, defaults apply (`show-glossary-on-codex-commands = true`).

## Invocation

```
lore glossary
lore glossary list
lore glossary list --json
lore glossary search <query>
lore glossary search "constable mission"
lore glossary show <keyword> [<keyword>...]
lore glossary show Constable Quest
lore --json glossary show Constable
```

`lore glossary` (no subcommand) is an alias for `lore glossary list`. The group is registered between `codex` and `artifact` in the CLI listing — adjacency reflects the conceptual proximity to the codex.

## Steps — List (`lore glossary` / `lore glossary list`)

### 1. Load the glossary

`lore.glossary.scan_glossary(project_root)` reads `.lore/codex/glossary.yaml`, validates against `lore://schemas/glossary`, and returns a list of frozen `GlossaryItem` dataclasses (`keyword`, `definition`, `aliases: tuple[str,...]`, `do_not_use: tuple[str,...]`).

If the file is absent, `scan_glossary` returns `[]` and the CLI prints `No glossary defined.` to stdout, exit 0.

### 2. Sort

Items are sorted alphabetically by `casefold(keyword)`. Original casing is preserved on display.

### 3. Render

Text mode emits a table with three columns: `KEYWORD`, `ALIASES` (joined by `, ` or em-dash `—` when empty), `DEFINITION` (truncated to 80 characters with trailing `…` when longer):

```
KEYWORD     ALIASES                          DEFINITION
Codex       —                                The documentation system at .lore/codex/. Markdown files...
Constable   constable mission, chore mission Mission type for orchestrator-handled chores (commits, ho...
Quest       —                                A live grouping of Missions representing one body of work.
```

JSON mode emits `{"glossary": [<items>]}` with all four item fields always present (empty arrays for absent `aliases` / `do_not_use` per the field-presence rule in conceptual-workflows-json-output).

## Steps — Search (`lore glossary search <query>`)

### 1. Load and filter

`search_glossary(root, query)` calls `scan_glossary(root)` and returns every item whose `casefold(query)` appears as a substring in any of: `keyword`, any `alias`, any `do_not_use` term, or `definition`. Substring match — NOT the tokenised contiguous-run match used by auto-surface. Substring match makes `search` a discovery tool for partial fragments; the matcher is reserved for auto-surface and the deprecated-term scan.

### 2. Sort and render

Same alphabetical sort and table layout as `list`. No-match output: `No glossary entries matching "<query>".` exit 0.

JSON envelope identical to `list` — `{"glossary": [...]}`.

## Steps — Show (`lore glossary show <keyword> [<keyword>...]`)

### 1. Accept multiple keywords

Positional arguments are zero-or-more keywords. ADR-012 multi-value space-separated semantics apply (lore codex show decisions-012-multi-value-cli-param-convention).

### 2. Look up each keyword

`read_glossary_item(root, keyword)` is case-insensitive (`casefold` on both sides) and returns the matching `GlossaryItem` or `None`. **Aliases are NOT accepted as lookup keys** — only canonical keywords. This keeps `show` a deterministic retrieval surface (one keyword → at most one item).

### 3. Fail-fast on missing keyword

If any keyword is missing, the command emits `Error: glossary keyword "<kw>" not found.` to stderr and exits 1 immediately. No partial output is printed. JSON mode emits `{"error": "glossary keyword \"<kw>\" not found."}` to stderr, exit 1. Mirrors the `lore codex show` precedent.

### 4. Render

Text mode prints each item under a `=== <keyword> ===` separator with `Keyword`, `Aliases`, `Do not use`, and a multi-line `Definition` block:

```
=== Constable ===
Keyword: Constable
Aliases: constable mission, chore mission
Do not use: bot mission
Definition:
  Mission type for orchestrator-handled chores (commits, housekeeping).
  Not dispatched to a worker.
```

JSON mode emits `{"glossary": [<items>]}` in the order keywords were requested (deduplicated).

## Steps — Auto-Surface (`lore codex show <id> [<id>...]`)

### 1. Read documents

The existing `lore codex show` pipeline runs unchanged (lore codex show conceptual-workflows-codex). Each requested document is read; bodies are collected.

### 2. Resolve config and flags

`lore.config.load_config(project_root)` returns a `Config` dataclass. `show-glossary-on-codex-commands` (default `true`) controls auto-surface globally. The `--skip-glossary` flag on `lore codex show` overrides per call. Effective rule: `show_glossary = config.show_glossary_on_codex_commands and not skip_glossary`.

If `show_glossary` is `False`, auto-surface is skipped entirely — no glossary block in text mode, `"glossary": []` in JSON mode.

### 3. Match

`match_glossary(bodies, root=project_root)` runs once:

- Calls `scan_glossary(root)` to load items.
- Builds a canonical-only lookup: `_build_lookup(items)` maps token-tuples (from `keyword` and each `alias`) to their `GlossaryItem`. `do_not_use` terms are excluded — auto-surface is canonical-vocabulary only.
- For each body, calls `_normalise_tokens(body)` (split on `[^\w]+` with `re.UNICODE`, casefold, drop empty strings).
- For each token position, attempts the longest-prefix match against the lookup. On a hit, the matched item is recorded once (set semantics) and the scan advances past the matched run.
- Returns the matched items alphabetised by casefolded keyword.

**Multi-word keyword + apostrophe regression:** body `the codex source's structure` tokenises to `["the", "codex", "source", "s", "structure"]`. A glossary item `keyword: Codex Source` becomes the token-tuple `("codex", "source")` and matches at index 1. This case is locked into the unit-test fixture.

`missionary` does NOT match `mission` because the matcher requires complete-token matches, not substring matches.

### 4. Render

Text mode appends a trailing `## Glossary` block after the last document body (separated by a blank line). Each matched item renders as `**<keyword>** — <definition>` on a single line. Multi-line definitions collapse to one line via `" ".join(definition.split())`. No ANSI; matches the existing CLI plain-text style.

```
=== conceptual-entities-mission ===
# Mission
... (body) ...

## Glossary

**Mission** — The unit of work an agent executes and closes.

**Quest** — A live grouping of Missions representing one body of work.
```

When zero items match, no `## Glossary` heading is emitted.

JSON mode adds an always-present `"glossary": [...]` field alongside `"documents"`:

```json
{
  "documents": [{"id": "...", "title": "...", "summary": "...", "body": "..."}],
  "glossary": [{"keyword": "Mission", "definition": "...", "aliases": [], "do_not_use": []}]
}
```

`"glossary"` is `[]` (always present, never omitted) when no items match, when `--skip-glossary` was passed, or when the config disables auto-surface. The always-present rule satisfies the field-presence contract in conceptual-workflows-json-output.

### 5. Fail-soft policy

If `scan_glossary` raises `GlossaryError` (parse failure or schema violation) or `OSError`, the auto-surface step:

- Emits a single line to stderr: `glossary unavailable: <reason>`.
- Treats the glossary as empty for this call.
- Does NOT propagate the error to the user.
- Exits 0 (or whatever exit the rest of `lore codex show` would have used).

This is the reliability bar from PRD NFR-Reliability: a malformed glossary MUST NOT break `lore codex show`. The same `GlossaryError` is treated fail-loud in `lore glossary list/search/show` and in `lore health`.

## Failure Modes

| Failure point | Surface | Behaviour | Exit code |
|---|---|---|---|
| Missing `.lore/codex/glossary.yaml` | `lore glossary list` | Stdout `No glossary defined.` | 0 |
| Missing `.lore/codex/glossary.yaml` | `lore glossary search` | Stdout `No glossary entries matching "<query>".` | 0 |
| Missing `.lore/codex/glossary.yaml` | `lore glossary show <kw>` | Stderr `Error: glossary keyword "<kw>" not found.` | 1 |
| Missing `.lore/codex/glossary.yaml` | `lore codex show` (auto-surface) | Skipped silently; no stderr; no glossary block | 0 |
| Malformed YAML or schema fail | `lore glossary list/search/show` | Stderr `Error: glossary unavailable: <reason>` | 1 |
| Malformed YAML or schema fail | `lore codex show` (auto-surface) | Stderr (single line) `glossary unavailable: <reason>`; no glossary block | 0 |
| Malformed YAML or schema fail | `lore health --scope glossary` (or `--scope schemas`) | `HealthIssue(severity="error", check="schema", schema_id="lore://schemas/glossary", ...)`; markdown report rows | 1 |
| Missing keyword on `show` | `lore glossary show` | Fail-fast: first missing aborts; stderr `Error: glossary keyword "<kw>" not found.` | 1 |
| Missing `.lore/config.toml` | any | `load_config` returns `DEFAULT_CONFIG` silently | 0 |
| Malformed `.lore/config.toml` | any | One-time stderr warning `lore: invalid config at .lore/config.toml: <reason> (using defaults)`; defaults applied | 0 |
| Wrong-type known config key | any | One-time stderr warning naming the key; default substituted | 0 |

## Out of Scope

- **Glossary writes via CLI.** No `lore glossary new/edit/delete`. Maintainers edit `.lore/codex/glossary.yaml` directly. This mirrors the artifact CLI read-only pattern (lore codex show conceptual-entities-artifact).
- **Auto-surface on `lore codex map` / `lore codex chaos`.** MVP scopes auto-surface to `lore codex show` only. `--skip-glossary` is not accepted on `map` or `chaos`.
- **Per-document glossary opt-out via frontmatter.** The only toggle is the project-wide `show-glossary-on-codex-commands` setting in `.lore/config.toml` and the per-call `--skip-glossary` flag.
- **Cross-project glossary import.** Each project owns its own `glossary.yaml`. No `lore glossary import <path>`.
- **Hash-based incremental indexing.** Linear scan satisfies the <200 ms NFR budget on the projected scale. Indexing is deferred post-MVP.
- **Auto-learning glossary terms from prose.** Out of scope.

## Python API

```python
from lore.models import GlossaryItem
from lore.glossary import (
    scan_glossary,
    read_glossary_item,
    search_glossary,
    match_glossary,
    find_deprecated_terms,
    GlossaryError,
)

items = scan_glossary(project_root)                      # list[GlossaryItem]; [] if file missing
item  = read_glossary_item(project_root, "Constable")    # GlossaryItem | None
hits  = search_glossary(project_root, "mission")          # list[GlossaryItem]
matched = match_glossary([doc1_body, doc2_body], root=project_root)  # list[GlossaryItem] (canonical-only)
deprecated = find_deprecated_terms({"doc-id-1": body1}, root=project_root)
                                                          # list[tuple[GlossaryItem, doc_id, matched_term]]
```

`GlossaryItem` is in `lore.models.__all__` (FR-30, ADR-010). `Config` is internal — not exported (FR-14, deferred until Realm asks). `scan_glossary` returns `[]` on missing file; raises `GlossaryError` on parse failure or schema violation.

## Related

- conceptual-entities-glossary (lore codex show conceptual-entities-glossary) — what the entity is.
- conceptual-workflows-codex (lore codex show conceptual-workflows-codex) — the `lore codex show` host pipeline.
- conceptual-workflows-health (lore codex show conceptual-workflows-health) — schema, collision, and deprecated-term audit.
- conceptual-workflows-lore-init (lore codex show conceptual-workflows-lore-init) — how the skeleton is seeded.
- conceptual-workflows-error-handling (lore codex show conceptual-workflows-error-handling) — exit codes and stderr routing.
- conceptual-workflows-json-output (lore codex show conceptual-workflows-json-output) — JSON envelope contract.
- decisions-013-toml-for-config-yaml-for-glossary (lore codex show decisions-013-toml-for-config-yaml-for-glossary) — file-format split.
- decisions-012-multi-value-cli-param-convention (lore codex show decisions-012-multi-value-cli-param-convention) — `lore glossary show <kw> [...]` and `--scope glossary` semantics.
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference.
