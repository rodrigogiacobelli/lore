---
id: conceptual-workflows-health
title: lore health Behaviour
summary: What the system does internally when lore health runs — full-scan or scoped audit of all five file-based entity types, error/warning reporting, markdown report write to codex/transient, --scope filtering, --json output, exit code contract, and Python API via health_check().
related: ["conceptual-entities-artifact", "conceptual-entities-doctrine", "conceptual-entities-knight", "conceptual-entities-watcher", "conceptual-workflows-codex", "conceptual-workflows-error-handling", "conceptual-workflows-json-output", "decisions-012-multi-value-cli-param-convention", "tech-api-surface", "tech-cli-commands"]
stability: stable
---

# `lore health` Behaviour

`lore health` audits all five file-based entity types in a Lore project and reports every detected inconsistency as an error or a warning. It is the only command whose sole job is to prove the project's knowledge base is internally consistent.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- The caller may optionally specify one or more entity types via `--scope`.

## Invocation

```
lore health
lore health --scope doctrines knights
lore health --scope watchers
lore health --json
lore health --scope codex --json
```

`--scope` accepts one or more space-separated tokens from the set: `codex`, `artifacts`, `doctrines`, `knights`, `watchers`. Omitting `--scope` audits all five types.

`--json` prints machine-readable JSON to stdout instead of the human-readable table. The report file is always written regardless of `--json`.

## Steps

### 1. Resolve scope

The system determines which entity types to audit:
- No `--scope`: all five types (`codex`, `artifacts`, `doctrines`, `knights`, `watchers`).
- `--scope TYPE [TYPE ...]`: only the listed types are checked; all others are skipped entirely.

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

#### Watcher checks

- **Invalid YAML** (error): any `.yaml` file under `.lore/watchers/` (excluding `.yaml.deleted` files) that fails YAML parsing. Reports the line number from the parse error.
- **Broken doctrine ref** (error): any watcher whose `action` field names a doctrine not found on disk.

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

Report body on issues found: a markdown table with columns Severity, Entity Type, ID, Check, Detail.

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

Clean run:
```
Health check passed. No issues found.
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
      "detail": "'senior-engineer' not found (step 2)"
    },
    {
      "severity": "warning",
      "entity_type": "codex",
      "id": "proposals-draft",
      "check": "island_node",
      "detail": "no documents link here"
    }
  ]
}
```

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
| Unknown `--scope` token | Exit 1 with usage error: `Invalid scope: 'xyz'. Valid scopes: codex, artifacts, doctrines, knights, watchers.` |
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
