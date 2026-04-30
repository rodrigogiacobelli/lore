---
id: conceptual-workflows-health
title: lore health Behaviour
summary: What the system does internally when lore health runs — full-scan or scoped audit of all six file-based entity types (codex, artifacts, doctrines, knights, watchers, glossary), error/warning reporting, markdown report write to codex/transient, --scope filtering, --json output, exit code contract, and Python API via health_check(). Includes the glossary scope's schema, intra-file collision, and cross-codex deprecated-term scan.
related: ["conceptual-entities-artifact", "conceptual-entities-doctrine", "conceptual-entities-knight", "conceptual-entities-watcher", "conceptual-entities-glossary", "conceptual-workflows-codex", "conceptual-workflows-glossary", "conceptual-workflows-error-handling", "conceptual-workflows-json-output", "decisions-012-multi-value-cli-param-convention", "decisions-013-toml-for-config-yaml-for-glossary", "tech-api-surface", "tech-cli-commands", "tech-arch-schemas"]
---

# `lore health` Behaviour

`lore health` audits all six file-based entity types in a Lore project — codex, artifacts, doctrines, knights, watchers, and the Glossary (lore codex show conceptual-entities-glossary) — and reports every detected inconsistency as an error or a warning. It is the only command whose sole job is to prove the project's knowledge base is internally consistent.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- The caller may optionally specify one or more entity types via `--scope`.

## Invocation

```
lore health
lore health --scope doctrines knights
lore health --scope watchers
lore health --scope glossary
lore health --scope codex glossary
lore health --json
lore health --scope codex --json
```

`--scope` accepts one or more space-separated tokens from the set: `codex`, `artifacts`, `doctrines`, `knights`, `watchers`, `schemas`, `glossary`. Omitting `--scope` runs every scope including `schemas` and `glossary`.

`--json` prints machine-readable JSON to stdout instead of the human-readable table. The report file is always written regardless of `--json`.

## Steps

### 1. Resolve scope

The system determines which entity types to audit:
- No `--scope`: all scopes run, including `schemas` and `glossary`.
- `--scope TYPE [TYPE ...]`: only the listed scopes are checked; all others are skipped entirely.
- Valid scope tokens: `codex`, `artifacts`, `doctrines`, `knights`, `watchers`, `schemas`, `glossary`.

### 2. Run per-entity checkers

Each in-scope entity type is checked independently. A failure in one checker (e.g., the watchers directory is missing) does not abort other checkers — the failure is recorded as a `scan_failed` error and scanning continues.

#### Codex checks

- **Missing `id` field** (error): any `.md` file under `.lore/codex/` whose frontmatter lacks an `id` field.
- **Broken `related` link** (error): any codex document whose `related` list names an ID that does not exist in the codex.
- **Island node** (warning): any codex document that no other document references in its `related` list.

#### Artifact checks

- **Missing required frontmatter** (error): any `.md` file under `.lore/artifacts/` missing `id`, `title`, or `summary`. Reports the first absent field. These files are currently silently skipped by `lore artifact list` — `lore health` makes the gap visible.

#### Doctrine checks

- **Orphaned file** (error): any `.yaml` with no matching `.design.md`, or any `.design.md` with no matching `.yaml`.
- **Broken knight ref in step** (error): any doctrine step whose `knight` field names a knight not present on disk (and not soft-deleted as `<name>.md.deleted`).
- **Broken artifact ref in step notes** (error): any doctrine step whose `notes` field contains a token matching the artifact ID pattern (`fi-[a-z0-9-]+`) that does not exist in the artifact index.

#### Knight checks

- **Missing file** (error): any active (non-closed, non-deleted) mission that names a knight whose `.md` file is absent from disk. A `.md.deleted` file means intentional soft-delete — not an error. A completely absent file is an error.

#### Glossary checks (scope: `glossary`)

The glossary scope runs three families of check over `.lore/codex/glossary.yaml` and the rest of the codex. See conceptual-entities-glossary (lore codex show conceptual-entities-glossary) for the entity model and conceptual-workflows-glossary (lore codex show conceptual-workflows-glossary) for the matcher used by the deprecated-term scan.

1. **Schema validation.** `lore.schemas.validate_entity_file(path, "glossary")` validates the file against `lore://schemas/glossary`. Schema errors are always errors (never warnings) and short-circuit the intra-glossary checks for that file (the unsafe-to-interpret rule). The `glossary` schema kind also runs as part of `--scope schemas`.
2. **Intra-glossary collisions:**
   - **`duplicate_keyword`** (error): two items share a casefolded `keyword`. `id=<glossary path>`, `detail="'<kw>' appears in items[i] and items[j]"`.
   - **`alias_keyword_collision`** (warning): an alias of item A casefold-equals the keyword of item B (B != A). `detail="alias '<a>' on '<kw>' collides with keyword '<other>'"`.
   - **`do_not_use_collision`** (error): a `do_not_use` term casefold-equals any other item's `keyword` or any `alias`. `detail="'<term>' in do_not_use of '<kw>' collides with keyword/alias '<other>'"`.
3. **Cross-codex deprecated-term scan.** Every codex `.md` body is loaded once. `lore.glossary.find_deprecated_terms` runs the shared tokeniser over each body and matches `do_not_use` token-tuples (canonical keywords and aliases are NOT scanned here — only deprecated forms). Each occurrence emits one `HealthIssue(severity="warning", entity_type="codex", id=<doc-id>, check="glossary_deprecated_term", detail='document uses deprecated term "<term>" — prefer "<canonical-keyword>"')`. Mirrors the existing `broken_related_link` warning shape.

`--scope glossary` runs only those three families (no codex `related` checks, no doctrine checks, etc.). `--scope codex glossary` runs codex reference-integrity checks AND the glossary checks (multi-scope per ADR-012). `--scope schemas` continues to validate every schema kind, including `glossary`, so a malformed glossary surfaces in `--scope schemas` even without `glossary` in the scope set.

A missing `.lore/codex/glossary.yaml` is NOT an error — empty glossary is a valid state. Schema validation of an absent file is a no-op for this kind. The intra-glossary and deprecated-term scans both no-op on an empty/absent file.

#### Watcher checks

- **Invalid YAML** (error): any `.yaml` file under `.lore/watchers/` (excluding `.yaml.deleted` files) that fails YAML parsing. Reports the line number from the parse error.
- **Broken doctrine ref** (error): any watcher whose `action` field names a doctrine not found on disk.

#### Schema checks (scope: `schemas`)

Schema checks validate the *shape* of every on-disk entity file against its JSON Schema. They are complementary to the reference-integrity checks above — schema checks answer "is this file a valid `X`?", reference checks answer "does this link resolve?". Schema definitions live in `src/lore/schemas/*.yaml` and are the single authoritative contract shared with create-time validators in `doctrine.py`, `knight.py`, `watcher.py`, and `artifact.py` (see tech-arch-schemas).

Every schema violation is an **error** (never a warning) and each emits a `HealthIssue` with `check="schema"` and three extra fields: `schema_id`, `rule`, `pointer`. Multiple violations per file are collected via `jsonschema.Draft202012Validator.iter_errors` — no short-circuit.

Per-kind coverage:

- **`doctrine-yaml`** — every `.lore/doctrines/**/*.yaml` validated against `lore://schemas/doctrine-yaml`.
- **`doctrine-design-frontmatter`** — frontmatter of every `.lore/doctrines/**/*.design.md` validated against `lore://schemas/doctrine-design-frontmatter`.
- **`knight`** — frontmatter of every `.lore/knights/**/*.md` validated against `lore://schemas/knight-frontmatter`.
- **`watcher`** — every `.lore/watchers/**/*.yaml` validated against `lore://schemas/watcher-yaml`.
- **`codex`** — frontmatter of every `.lore/codex/**/*.md` validated against `lore://schemas/codex-frontmatter` (optional `related` array accepted; mapping form rejected).
- **`artifact`** — frontmatter of every `.lore/artifacts/**/*.md` validated against `lore://schemas/artifact-frontmatter`.
- **`glossary`** — the single file `.lore/codex/glossary.yaml` (full-YAML, not frontmatter) validated against `lore://schemas/glossary`. Unique among schema kinds: a literal file glob, not a `**/*.yaml` walk.

Special error rules (beyond JSON Schema keywords):

- **`rule="yaml-parse"`** — file's YAML is unparseable. Single error emitted; validation of that file stops. `pointer="/"`, `message` is the YAML parser message.
- **`rule="missing-frontmatter"`** — frontmatter-validated file has no `---` block. Single error, `pointer="/"`, message `"File has no YAML frontmatter block"`.
- **`rule="read-failed"`** — I/O or Unicode failure on read. Single error, `pointer="/"`, `message=str(exc)`. Validation continues to the next file.

Files that the existing entity loaders today silently skip (unpaired doctrine designs, frontmatter-less knights, malformed artifacts) are surfaced here as schema errors instead of being silently dropped.

### 3. Collect results

All checkers return a list of `HealthIssue` objects. The system partitions them into errors and warnings and assembles a `HealthReport`.

### 4. Write markdown report

The system always writes a markdown report to `.lore/codex/transient/health-{timestamp}.md`, even on clean runs. The timestamp uses UTC ISO 8601 with colons replaced by hyphens for filesystem compatibility (e.g., `health-2026-04-09T14-32-00.md`).

Report frontmatter:
```yaml
id: health-2026-04-09T14-32-00
title: Health Report — 2026-04-09T14:32:00
summary: lore health report generated at 2026-04-09T14:32:00 UTC
```

Report body on issues found: a markdown table with columns Severity, Entity Type, ID, Check, Detail, followed by a `## Schema validation` section listing every schema error grouped by `kind` then file path. When there are zero schema errors, the section reads `No schema errors.`.

Report body on clean run: `No issues found.`

No retention policy is enforced — reports accumulate.

### 5. Render output

**Text mode (no `--json`):**

Issues present:
```
SEVERITY  ENTITY_TYPE  ID                CHECK
ERROR     doctrines    feat-auth         broken_knight_ref: 'senior-engineer' not found (step 2)
ERROR     watchers     on-quest-close    broken_doctrine_ref: 'feat-payments' not found
WARNING   codex        proposals-draft   island_node: no documents link here
```

Schema violations use a dedicated multi-line ERROR block followed by a summary line:

```
ERROR .lore/knights/default/feature-implementation/pm.md
  kind: knight
  schema: lore://schemas/knight-frontmatter
  rule: additionalProperties
  path: /stability
  message: Unknown property 'stability' — allowed keys are id, title, summary.
Schema validation: 1 error
```

Clean run:
```
Health check passed. No issues found.
Schema validation: 0 errors
```

**JSON mode (`--json`):**

Issues present:
```json
{
  "has_errors": true,
  "issues": [
    {
      "severity": "error",
      "entity_type": "doctrines",
      "id": "feat-auth",
      "check": "broken_knight_ref",
      "detail": "'senior-engineer' not found (step 2)",
      "schema_id": null,
      "rule": null,
      "pointer": null
    },
    {
      "severity": "error",
      "entity_type": "knight",
      "id": ".lore/knights/default/feature-implementation/pm.md",
      "check": "schema",
      "detail": "Unknown property 'stability' — allowed keys are id, title, summary.",
      "schema_id": "lore://schemas/knight-frontmatter",
      "rule": "additionalProperties",
      "pointer": "/stability"
    }
  ]
}
```

Schema errors are strictly additive: every `HealthIssue` record carries the three new fields `schema_id`, `rule`, `pointer`, which are `null` for non-schema checks and populated for `check="schema"` rows.

Clean run:
```json
{
  "has_errors": false,
  "issues": []
}
```

### 6. Exit

- Exit `1` if `report.has_errors` is `True` (any error found).
- Exit `0` if clean or warnings-only.

## Python API

```python
from lore.models import health_check, HealthReport, HealthIssue
from pathlib import Path

report = health_check(project_root=Path("."), scope=None)
report = health_check(project_root=Path("."), scope=["codex"])
report = health_check(project_root=Path("."), scope=["doctrines", "watchers"])

report.has_errors       # bool
report.errors           # tuple[HealthIssue, ...]
report.warnings         # tuple[HealthIssue, ...]
report.issues           # tuple[HealthIssue, ...] — errors then warnings
```

`health_check()` never prints to stdout or stderr. The report file is written by the CLI handler after calling `health_check()`, not inside `health_check()` itself. Python API callers that do not want the file side effect simply do not call `_write_report`.

`health_check` is in `lore.models.__all__`. `HealthIssue` and `HealthReport` are also in `__all__`.

## Error Paths

| Condition | Behaviour |
|-----------|-----------|
| Unknown `--scope` token | Exit 1 with usage error: `Invalid scope: 'xyz'. Valid scopes: codex, artifacts, doctrines, knights, watchers, schemas, glossary.` |
| Authoritative schema file missing at load time | Propagated as a `scan_failed` error naming the missing schema id. No partial false-green. |
| Entity directory missing | `scan_failed` error added for that entity type; other types continue |
| Report directory missing | Created if absent (`.lore/codex/transient/` is created on first run) |
| No entities of a type on disk | Clean result for that type (no issues) |

## Scope Isolation

When `--scope` is provided, only the named entity types are checked. No other entity types are scanned. Example: `lore health --scope watchers` never reads codex, artifact, doctrine, or knight files.

## Out of Scope

- Missions and quests (DB entities) are outside the health perimeter.
- Auto-repair (`--fix`) is a post-MVP feature.
- Scheduling or periodic execution is handled by watchers or CI.

## Related

- health-check-prd-final (lore codex show health-check-prd-final)
- health-check-tech-spec (lore codex show health-check-tech-spec)
- conceptual-workflows-error-handling (lore codex show conceptual-workflows-error-handling)
- conceptual-workflows-json-output (lore codex show conceptual-workflows-json-output)
- decisions-012-multi-value-cli-param-convention (lore codex show decisions-012-multi-value-cli-param-convention)
- tech-cli-commands (lore codex show tech-cli-commands)
- tech-api-surface (lore codex show tech-api-surface)
