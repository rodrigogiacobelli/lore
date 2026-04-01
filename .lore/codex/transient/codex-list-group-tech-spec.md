---
feature: codex-list-group
status: draft
id: codex-list-group-tech-spec
title: codex-list-group — Tech Spec
summary: Tech Spec for replacing the manual f-string codex list table with _format_table and GROUP column derived from derive_group.
---

# codex-list-group — Tech Spec

**Author:** Architect
**Date:** 2026-03-27
**Input:** codex-list-group-prd

---

## Core Architectural Decisions

| Priority | Decision | Choice | Rationale |
|----------|----------|--------|-----------|
| Critical | Where to derive GROUP | CLI handler (`codex_list`) | Consistent with `knight_list` pattern; `scan_codex` stays a pure scanner, no API surface change |
| Critical | Renderer for tabular output | `_format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows)` | All other entity list commands already use this helper; aligns interface fully |
| Critical | JSON key for document array | `"codex"` (was `"documents"`) | Matches envelope pattern of `{"knights": [...]}`, `{"doctrines": [...]}`, etc. |
| Important | `--json` local flag | Add `@click.option("--json", "json_flag", ...)` to `codex_list` | Consistent with `knight_list`, `doctrine_list`, `watcher_list` which all have a local `--json` flag in addition to the global `ctx.obj["json"]` |
| Important | TYPE field in JSON output | Drop `"type"` from JSON output, expose only `id`, `group`, `title`, `summary` | Matches `knight_list` and `watcher_list` JSON; TYPE can still be obtained via `lore codex show` |
| Deferred | Update `conceptual-workflows-codex` codex doc | Post-MVP | Implementation change is trivial; doc update is cosmetic and can follow separately |

---

## Data Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | No change | Pure CLI rendering change; no DB involvement |
| ORM / query layer | No change | `scan_codex` walks filesystem; no query layer touched |
| Migration approach | None required | No schema or data changes |
| Data validation | No change | `derive_group` is a pure path operation; input is always a `Path` from `scan_codex` |

---

## API & Communication

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API style | CLI only | No HTTP API surface; `codex_list` is a Click handler |
| Error response format | No change | Existing empty-list message `"No codex documents found."` is retained |
| Versioning strategy | None | Internal CLI helper; no semver impact since `lore.models.__all__` is not changed |

---

## Implementation Patterns

### Naming Conventions

**Code:** snake_case throughout (`codex_list`, `json_flag`, `codex_dir`, `group`)
**CLI flags:** `--json` (local flag name `json_flag`, matching `knight_list` convention)
**JSON keys:** lowercase snake_case (`"id"`, `"group"`, `"title"`, `"summary"`, `"codex"`)

### Exact File Changes

#### `src/lore/cli.py` — `codex_list` handler (lines 2226–2269)

This is the **only file that changes**.

Replace the entire `codex_list` handler with:

```python
@codex.command("list")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def codex_list(ctx, json_flag):
    """List all codex documents."""
    from lore.codex import scan_codex

    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)
    codex_dir = paths.codex_dir(project_root)

    documents = scan_codex(codex_dir)

    if json_mode:
        filtered = [
            {
                "id": d["id"],
                "group": paths.derive_group(d["path"], codex_dir),
                "title": d["title"],
                "summary": d["summary"],
            }
            for d in documents
        ]
        click.echo(json.dumps({"codex": filtered}))
        return

    if not documents:
        click.echo("No codex documents found.")
        return

    rows = [
        [d["id"], paths.derive_group(d["path"], codex_dir), d["title"], d["summary"]]
        for d in documents
    ]
    for line in _format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows):
        click.echo(line)
```

**What changes:**
1. Add `@click.option("--json", "json_flag", ...)` decorator (new line before `@click.pass_context`)
2. Add `json_flag` parameter to function signature
3. Change `json_mode = ctx.obj.get("json", False)` to `json_mode = json_flag or ctx.obj.get("json", False)`
4. In JSON branch: replace `"documents"` key with `"codex"`, drop `"type"`, add `"group"` computed via `paths.derive_group(d["path"], codex_dir)`
5. Replace entire manual column-width + f-string table with `_format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows)` where each row is `[d["id"], paths.derive_group(d["path"], codex_dir), d["title"], d["summary"]]`

**No other files change.**

- `src/lore/codex.py` — `scan_codex` already returns `path` in every record; no change needed
- `src/lore/paths.py` — `derive_group` already implemented with correct signature; no change needed
- `_format_table` in `cli.py` — already implemented; no change needed

### Error Handling

`derive_group` raises `ValueError` if `filepath` is not under `base_dir`. This cannot happen in practice because every path returned by `scan_codex(codex_dir)` is obtained via `codex_dir.rglob("*.md")` — all paths are guaranteed to be under `codex_dir`. No additional error handling is required.

Documents at the root of `.lore/codex/` (no subdirectory) return `""` from `derive_group` — this is the correct fallback per the PRD and consistent with other entities.

### Output Formats

**Tabular success (lore codex list):**
```
  ID                         GROUP     TITLE                          SUMMARY
  001                                  Dumb infrastructure design...  ADR recording the core design...
  decisions-006-id-references          Agents reference entities...   ADR recording the decision that...
  tech-arch-source-layout    tech-arch Source Layout                  One-line descriptions of every...
```

**JSON success (lore codex list --json):**
```json
{
  "codex": [
    {
      "id": "001",
      "group": "",
      "title": "Dumb infrastructure design principles",
      "summary": "ADR recording the core design principles..."
    },
    {
      "id": "tech-arch-source-layout",
      "group": "tech-arch",
      "title": "Source Layout",
      "summary": "One-line descriptions of every module..."
    }
  ]
}
```

**Empty result:**
```
No codex documents found.
```

---

## Project Structure

```
src/lore/
  cli.py                            # codex_list handler updated (lines 2226–2269)
tests/
  e2e/
    test_codex_list_group_e2e.py    # New E2E test file
  unit/
    test_cli_codex_list.py          # Existing unit tests — must continue to pass; add group column cases
```

---

## Test Strategy

### E2E Coverage

| Workflow (from PRD) | Workflow codex ID | Test scenario | Priority |
|---------------------|-------------------|---------------|----------|
| Listing codex documents — Developer | `conceptual-workflows-codex` | Run `lore codex list`; assert output contains four columns: ID, GROUP, TITLE, SUMMARY header line; assert GROUP value matches subdirectory of document path | High |
| Listing codex documents — Developer | `conceptual-workflows-codex` | Run `lore codex list`; assert output does NOT contain TYPE column | High |
| Listing codex documents — Developer | `conceptual-workflows-codex` | Create a document directly under `.lore/codex/` (no subdirectory); run `lore codex list`; assert GROUP column is empty string (not an error) | High |
| Consuming codex list output — Automation | `conceptual-workflows-codex` | Run `lore codex list --json`; parse JSON; assert every record has a `"group"` key | High |
| Consuming codex list output — Automation | `conceptual-workflows-codex` | Run `lore codex list --json`; parse JSON; assert top-level key is `"codex"` (not `"documents"`) | High |
| Consuming codex list output — Automation | `conceptual-workflows-codex` | Run `lore codex list --json`; parse JSON; assert `group` value for a document in a subdirectory matches the expected subdirectory name | High |
| Consuming codex list output — Automation | `conceptual-workflows-codex` | Run `lore codex list --json`; assert no record contains a `"type"` key | Medium |

**Exact lore codex list commands for E2E tests:**

```bash
# Tabular output - verify GROUP column present, TYPE absent
lore codex list

# JSON output - verify group field and codex envelope
lore codex list --json

# JSON output via global flag (also supported)
lore codex list --json
```

### Unit Coverage

| Component | Workflow codex ID | Scenarios to cover |
|-----------|-------------------|--------------------|
| `codex_list` in `cli.py` | `conceptual-workflows-codex` | Tabular output includes GROUP column header; tabular output uses `_format_table`; GROUP derived correctly from subdirectory path; GROUP is empty string for root-level document; JSON output key is `"codex"`; JSON record includes `"group"` field; JSON record does not include `"type"` field; `--json` local flag works; global `ctx.obj["json"]` still works |

### Test Conventions

- E2E tests live in `tests/e2e/test_codex_list_group_e2e.py`
- E2E tests use a temporary project directory fixture with `lore init` and seed documents placed in subdirectories of `.lore/codex/`
- Unit tests for `codex_list` extend the existing unit test file at `tests/unit/test_cli_codex_list.py` (or the equivalent existing file covering `codex_list`)
- Assertions on tabular output: check header line string exactly, check at least one data row contains expected GROUP value
- Assertions on JSON output: `json.loads(result.output)`, access `result["codex"]`, iterate records

---

## Crazy Tech Spec Findings

No Crazy Tech Spec was produced for this feature. The implementation is a straightforward alignment with the established `knight_list` pattern.

| Idea | Decision | Rationale |
|------|----------|-----------|
| Push group derivation into `scan_codex` | Rejected | Would require adding `base_dir` parameter to `scan_codex`, changing its API surface; CLI-handler derivation is consistent with `knight_list` and avoids API change |
| Keep `"type"` in JSON output | Rejected | Breaks consistency with `knight_list` and `watcher_list` JSON; `type` still accessible via `lore codex show` |
| Keep `"documents"` JSON envelope key | Rejected | `"codex"` matches the entity-name envelope pattern used by all other list commands |

---

## Migration & Rollback

This change is purely additive/cosmetic at the CLI layer:

- **No database changes** — no migration required
- **JSON breaking change:** The JSON envelope key changes from `"documents"` to `"codex"`, and `"type"` is removed from records. Any script currently consuming `lore codex list --json` and accessing `result["documents"]` or `record["type"]` will need updating. This is an acceptable breaking change as the current output is non-standard.
- **Rollback:** Revert the `codex_list` handler in `cli.py` to its prior state. No data is affected.

---

## Change Log

| Version | Change | Reason |
|---------|--------|--------|
| 1.0 | Initial Tech Spec | Align `codex_list` with all other entity list commands using `_format_table` and GROUP column |
