---
id: conceptual-workflows-impacts
title: lore impacts Behaviour
summary: What the system does internally when lore impacts <token> runs — the
  bidirectional surfacing primitive over the optional binds frontmatter field
  that links codex entries to the code paths they govern. Covers token
  classification (codex id vs path), exact-vs-glob matching, --direct-links and
  --json modes, error envelope, and Python API parity.
binds:
- src/lore/impacts.py
- src/lore/cli.py
- tests/e2e/test_impacts.py
- tests/unit/test_impacts.py
- tests/unit/test_models_impacts.py
related:
- conceptual-workflows-codex
- conceptual-workflows-codex-map
- conceptual-workflows-codex-chaos
- conceptual-workflows-error-handling
- conceptual-workflows-json-output
- conceptual-workflows-validators
- conceptual-workflows-health
- tech-arch-schemas
- tech-arch-frontmatter
- tech-arch-validators
- tech-arch-project-root-detection
- tech-cli-entity-crud-matrix
- ref-lore_cli-commands
- ref-lore_api-core
- decisions-006-id-references
- decisions-010-public-api-stability
- decisions-011-api-parity-with-cli
- standards-separation-of-concerns
- standards-single-responsibility
- vision-benchmarks
- codex
---

# `lore impacts` Behaviour

`lore impacts <token>` is a read-only surfacing primitive over a new optional
`binds:` field on codex frontmatter. The field declares which code paths or
globs a codex entry governs; `lore impacts` walks the edge in either direction.

- Pass a **codex id** → print the code paths/globs that entry binds.
- Pass a **file path** → print every codex entry whose `binds:` matches that
  path, exact-or-glob.

The command never writes anything. It is the codex↔code analogue of
`lore codex map` (which walks `related:` within the codex). Per
`vision-benchmarks`, this is the Layer-3 citation-accuracy retrieval primitive:
the gold-set generator for "which codex entries claim to govern this file?".
Determinism and zero false positives are therefore non-negotiable.

## Preconditions

- The Lore project has been initialised.
- For codex-seed lookups, the supplied id must resolve to an existing codex
  document.
- For path-seed lookups, the supplied path must resolve to a location inside
  the project root (absolute paths inside the repo are accepted and
  normalised).

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `<token>` | positional argument | required | A codex id (no `/`, no `.`) or a repo-relative / absolute file path. |
| `--direct-links` | flag | off | Path-seed only: drop glob matches; keep `exact` only. Silent no-op on codex-seed lookups. |
| `--json` (global) | flag | off | Emit the `{"impacts": [...]}` envelope instead of the flat text list. |

## Token Classification

The token is classified by string inspection only — no filesystem touch:

| Token contains | Treated as | Rationale |
|---|---|---|
| `/` | path | Codex ids never contain `/`. |
| `.` | path | Codex ids never contain `.`. |
| Neither `/` nor `.` | codex id | Matches the codex id pattern `[a-z0-9-]+`. |

This rule is the invariant; nothing else differs about how the two seed modes
are dispatched. Classification is part of business logic (not CLI parsing) —
it lives in the core module and is identical for the Python API.

## Steps — Codex-seed lookup

### 1. Validate the seed

`impacts.impacts` loads the codex index once via `scan_codex` (parsing
frontmatter with `extra_fields=("binds",)`). If the supplied id is not in the
index, the function raises `ImpactsError("Unknown codex id: \"<token>\"")` and
the CLI handler emits the message to stderr with exit code 1. Under `--json`
the same wording lands inside `{"error": "..."}` to stderr; exit code 1.

### 2. Read `binds:` from the entry

The entry's `binds:` list is returned verbatim in **declaration order from the
source file**. A missing `binds:` field is treated identically to `binds: []`
(FR-4) — both produce an empty result.

### 3. Render

**Text mode (default):** one binding per line, no headers, no annotation. The
output is exactly the `binds:` strings the author wrote.

```
$ lore impacts dec-006-id-references
src/lore/cli.py
src/lore/**/*.py
```

**JSON mode:** envelope keyed `"impacts"`. Each item is
`{"path": <string>, "kind": "exact" | "glob"}` where `kind` reflects whether
the binding string contains any glob character (`*`, `?`, `[`).

```json
{
  "impacts": [
    {"path": "src/lore/cli.py", "kind": "exact"},
    {"path": "src/lore/**/*.py", "kind": "glob"}
  ]
}
```

`--direct-links` is a silent no-op here; the output is identical with or
without the flag.

## Steps — Path-seed lookup

### 1. Normalise the path

`impacts._normalize_path_input` anchors the path against
`find_project_root()`:

- Relative paths stay relative (cleaned of `.`/`..` segments).
- Absolute paths inside the repo are converted to repo-relative.
- Absolute paths outside the repo raise `ImpactsError("Path is outside the
  project root: \"<token>\"")` (exit 1).
- Any path containing a `..` segment raises `ImpactsError("Path traversal not
  allowed: \"<token>\"")` (exit 1).
- Symlinks resolving outside the repo are rejected after `resolve()` (NFR
  Security — no filesystem walks happen during matching itself).

Normalised paths are `/`-joined POSIX strings regardless of platform.

### 2. Scan codex `binds:` index

`impacts._load_codex_binds_index` walks the codex once per process (cached via
`functools.lru_cache(maxsize=1)` keyed on the codex directory), reading
`binds:` from every entry's frontmatter. Entries with a malformed `binds:`
field on disk are silently skipped — schema-level rejection is
`lore health --scope schemas`' job, not this command's. `lore impacts` is a
read tool; it must never refuse to run because some other entry has a bad
field.

### 3. Match every binding against the normalised path

For each codex entry, every string in its `binds:` list is classified and
matched against the seed path:

- **Literal** (no `*`, `?`, `[`): exact equality.
- **Glob with `**`**: regex translation (via `fnmatch.translate` with `**` →
  any-chars-including-`/`) and a `re.fullmatch`.
- **Plain glob**: `fnmatch.fnmatchcase` on the slash-joined string.

A codex entry that matches both exactly **and** via glob is reported once,
classified as `exact` (FR-9). Dedup key is the codex id; exact wins.

### 4. Sort and render

Results are sorted **alphabetically by codex id** for determinism (NFR
Reliability).

**Text mode (default):** one matching codex id per line. Glob matches are
annotated `<id>  (glob: <pattern>)`; exact matches are unannotated.

```
$ lore impacts src/lore/cli.py
dec-006-id-references
tech-arch-source-layout  (glob: src/lore/**/*.py)
```

**JSON mode:** envelope keyed `"impacts"`. Items are `{"id": ..., "match":
"exact"}` for exact matches; `{"id": ..., "match": "glob", "pattern": ...}`
for glob matches (the matching binding string is echoed back).

```json
{
  "impacts": [
    {"id": "dec-006-id-references", "match": "exact"},
    {"id": "tech-arch-source-layout", "match": "glob", "pattern": "src/lore/**/*.py"}
  ]
}
```

### 5. Apply `--direct-links`

When set, every row where `match == "glob"` is dropped. JSON shape and sort
order are unchanged; the result may become empty.

## Empty Result Behaviour

| Seed type | Text mode | JSON mode | Exit |
|-----------|-----------|-----------|------|
| Codex seed, entry has no bindings | Nothing on stdout | `{"impacts": []}` | 0 |
| Path seed, no codex entry matches | Nothing on stdout | `{"impacts": []}` | 0 |
| Path seed, `--direct-links` drops every match | Nothing on stdout | `{"impacts": []}` | 0 |

Consistent with `lore codex map` / `lore codex chaos` and other listing
commands per `conceptual-workflows-error-handling`.

## Determinism

Two invocations on identical repo state must produce byte-identical stdout in
both default and `--json` modes. Codex-seed output preserves the author's
declaration order from the source file; path-seed output is sorted
alphabetically by codex id.

## Python API parity

Per `decisions-011-api-parity-with-cli`, `lore.impacts.impacts` exposes the
same behaviour as a keyword-only function. `lore.models` re-exports the typed
result surface:

```python
from lore.models import impacts, ImpactsResult, CodexBinding, CodeBinding, ImpactsError

result = impacts(token, project_root=root, direct_links=False)
# result.kind == "codex" or "code"
# result.codex_items: tuple[CodexBinding, ...]   when kind == "codex"
# result.code_items:  tuple[CodeBinding,  ...]   when kind == "code"
```

`CodexBinding` carries `path` and `kind`. `CodeBinding` carries `id`,
`match`, and an optional `pattern` (None when `match == "exact"`). Errors
surface as `ImpactsError` (subclass of `ValueError`); the CLI is a thin
translator over these.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| Unknown codex id | `Unknown codex id: "<token>"` to stderr (or JSON `{"error": "..."}`) | 1 |
| Path outside project root | `Path is outside the project root: "<token>"` to stderr (or JSON `{"error": "..."}`) | 1 |
| Path contains `..` segment | `Path traversal not allowed: "<token>"` to stderr (or JSON `{"error": "..."}`) | 1 |
| Empty token | Click `UsageError` | 2 |
| Malformed `binds:` entry on disk (some other codex entry) | Silently skipped from the index; matching continues. Surfaced separately by `lore health --scope schemas`. | 0 |
| Empty result (either seed) | Nothing on stdout; `{"impacts": []}` under `--json` | 0 |

## Out of Scope

- **Glob expansion.** `lore impacts` never converts a glob to a concrete file
  list. Globs surface as annotated rows; callers decide whether to walk them.
- **Authoring CLI.** No `lore codex bind` / `lore codex unbind` in v1 (PRD
  post-MVP). Bindings are authored on disk by editing the codex entry's
  frontmatter.
- **Health integration.** Dead-binding detection lives in
  `lore health --scope bindings` (lore codex show conceptual-workflows-health) —
  literal `binds:` paths missing on disk emit a `dead_binding` error; glob
  patterns matching zero files emit an `empty_glob_binding` warning. Schema-level
  rejection of malformed entries is automatic via `lore health --scope schemas`.
  Orphan-code detection (a code file no codex entry binds to) remains deferred.
- **Multi-hop traversal.** v1 is direct lookup only — one seed in, one set
  of direct neighbours out. No crossing of `related:` edges during a path
  lookup, no chained `binds:` traversal.
- **Injection policy.** When and how an orchestrator invokes `lore impacts`
  before dispatching a knight is the orchestrator's concern. This command
  exposes the data; it does not surface or inject it.
- **Glossary `binds:`.** PRD post-MVP. The schema and command shape generalise
  cleanly but v1 implements neither.
- **Edit-time triggers.** No watcher, no hook auto-runs `lore impacts` on
  file change.
