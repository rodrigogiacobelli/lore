---
id: remove-type-field-codex-proposal
title: Remove type Field — Codex Change Proposal
summary: Codex Change Proposal for the remove-type-field feature. Lists every codex document to update after the source-code change, with specific section-level changes. No new documents need to be created and no documents need to be retired. Eight existing documents require targeted updates to remove type field references.
---

# Remove `type:` Field — Codex Change Proposal

**Author:** Tech Writer
**Date:** 2026-03-27
**PRD:** `lore codex show remove-type-field-prd`
**Tech Spec:** `lore codex show remove-type-field-tech-spec`

---

## Orientation

The remove-type-field feature strips the `type:` frontmatter field from the Lore Python source layer (`frontmatter.py`, `codex.py`, `artifact.py`, `models.py`, `cli.py`) and from all ~39 default artifact templates. The parallel quest q-bbbf has already migrated body content in several live codex documents (frontmatter.md, codex-map.md, CODEX.md, commands.md, etc.). This proposal targets the eight codex documents that still describe the `type` field in their body text, function signatures, JSON schemas, or table column definitions — and therefore remain out of sync with the completed code change. No new documents are needed; no documents need to be retired.

---

## Documents to Create

None. The feature removes a field; it does not introduce a new concept, command, or subsystem that requires fresh documentation.

---

## Documents to Update

| Existing ID | Section(s) | Proposed Change | Rationale |
|-------------|------------|-----------------|-----------|
| `conceptual-entities-artifact` | Properties; Python API | Remove `type` from the four required fields list; remove `type` from the Python API field list and the `Artifact.from_dict` note | The `type` field is removed from the `Artifact` dataclass and from artifact frontmatter requirements |
| `conceptual-workflows-artifact-list` | Preconditions; Step 3 (Parse and validate); Step 6 (Render) | Drop `type` from required fields; update step-3 condition count from four to three; update table from five columns to four; update JSON example | Reflects the removed TYPE column and dropped `type` required field |
| `conceptual-workflows-codex` | Preconditions; Steps — Show JSON mode | Remove `type` from preconditions required fields; remove `type` from codex show JSON example | Codex documents no longer require or expose a `type` key |
| `conceptual-workflows-codex-chaos` | Frontmatter summary; Step 5 (Render) — text mode; Step 5 — JSON mode | Remove "ID, TYPE, TITLE, SUMMARY table" from summary and body; update JSON example to omit `type` key | chaos output no longer includes a `type` key |
| `tech-arch-frontmatter` | Public Interface (both function signatures); Required Fields section; `exclude_type` Parameter section; Callers table | Remove `exclude_type` parameter from both function signatures and their descriptions; remove `required_fields` artifact-caller note; remove the `exclude_type` Parameter section entirely | `exclude_type` is removed; artifact callers no longer pass `required_fields=("id","title","type","summary")` |
| `tech-api-surface` | chaos_documents Notes | Update `chaos_documents` return shape from `id, type, title, summary, body` to `id, title, summary` | The `type` key is removed from all function return dicts |
| `tech-arch-source-layout` | Module table — `frontmatter.py` row; Module table — `artifact.py` row | Remove `exclude_type=None` from both function signatures; remove the sentence about artifact callers using `("id","title","type","summary")`; update `artifact.py` dict-contract note | Reflects the new function signatures and dropped required field |
| `tech-cli-commands` | `lore artifact list` command description; `lore codex show` JSON schema; `lore artifact list --json` schema; `lore artifact show --json` schema | Remove TYPE column from artifact list table description; remove `type` key from codex show JSON; remove `type` key from artifact list and artifact show JSON examples | CLI output no longer includes `type` in any codex or artifact command |

---

## Update Details

### `conceptual-entities-artifact`

**Current state:** The Properties section lists four required fields: `id`, `title`, `type`, `summary`. The `type` field description reads: "A classification label (e.g. `template`). Used as a display column in `lore artifact list`. Not interpreted by Lore — it is metadata for human and agent readers." The Python API section lists fields as `id`, `title`, `type`, `summary`, `content`.

**Proposed change:**

In the **Properties** section:
- Replace the opening sentence "Every artifact file contains a YAML frontmatter block with four required fields:" with "Every artifact file contains a YAML frontmatter block with three required fields:"
- Remove the `type` bullet point entirely.

In the **Python API** section:
- Replace "Fields: `id`, `title`, `type`, `summary`, `content`." with "Fields: `id`, `title`, `summary`, `content`."

---

### `conceptual-workflows-artifact-list`

**Current state:**
- Step 3 condition 4 reads: "All four required fields are present and non-null: `id`, `title`, `type`, `summary`."
- Step 6 table mode description reads: "A fixed-width table is printed with five columns: `ID`, `TYPE`, `GROUP`, `TITLE`, `SUMMARY`."
- Step 6 JSON mode example includes `"type": "..."` in each artifact record.
- Out of Scope section mentions "Filtering by type or group — no filter flags exist."

**Proposed change:**

In **Step 3**, condition 4:
- Replace "All four required fields are present and non-null: `id`, `title`, `type`, `summary`." with "All three required fields are present and non-null: `id`, `title`, `summary`."

In **Step 6**, table mode:
- Replace "A fixed-width table is printed with five columns: `ID`, `TYPE`, `GROUP`, `TITLE`, `SUMMARY`." with "A fixed-width table is printed with four columns: `ID`, `GROUP`, `TITLE`, `SUMMARY`."

In **Step 6**, JSON mode — replace the JSON example:

```json
{
  "artifacts": [
    {"id": "...", "group": "...", "title": "...", "summary": "..."},
    ...
  ]
}
```

In **Out of Scope**:
- Replace "Filtering by type or group — no filter flags exist." with "Filtering by group — no filter flags exist."

---

### `conceptual-workflows-codex`

**Current state:**
- Preconditions reads: "Codex documents must have `id`, `type`, `title`, and `summary` frontmatter fields for full display."
- Steps — Show, JSON mode example includes `"type": "..."` in each document record.

**Proposed change:**

In **Preconditions**:
- Replace "Codex documents must have `id`, `type`, `title`, and `summary` frontmatter fields for full display." with "Codex documents must have `id`, `title`, and `summary` frontmatter fields for full display."

In **Steps — Show**, JSON mode — replace the JSON example:

```json
{
  "documents": [
    {"id": "...", "title": "...", "summary": "...", "body": "..."}
  ]
}
```

---

### `conceptual-workflows-codex-chaos`

**Current state:**
- Frontmatter `summary` field includes: "Output format is identical to lore codex map (ID, TYPE, TITLE, SUMMARY table)."
- Step 5 text mode reads: "a table with columns ID, TYPE, TITLE, SUMMARY — identical column layout to `lore codex list` and `lore codex search`."
- Opening paragraph reads: "Output format is identical to `lore codex map`: a table with columns ID, TYPE, TITLE, SUMMARY."
- Step 5 JSON example includes `"type": "..."`.

**Proposed change:**

In the **frontmatter summary**:
- Replace "Output format is identical to lore codex map (ID, TYPE, TITLE, SUMMARY table)." with "Output format is identical to lore codex map (ID, TITLE, SUMMARY table)."

In the **opening paragraph**:
- Replace "Output format is identical to `lore codex map`: a table with columns ID, TYPE, TITLE, SUMMARY." with "Output format is identical to `lore codex map`: a table with columns ID, TITLE, SUMMARY."

In **Step 5**, text mode:
- Replace "a table with columns ID, TYPE, TITLE, SUMMARY — identical column layout to `lore codex list` and `lore codex search`." with "a table with columns ID, TITLE, SUMMARY — identical column layout to `lore codex list` and `lore codex search`."

In **Step 5**, JSON mode — replace the JSON example:

```json
{
  "documents": [
    {"id": "...", "title": "...", "summary": "..."},
    ...
  ]
}
```

---

### `tech-arch-frontmatter`

**Current state:**
- Both function signatures include `exclude_type=None` parameter.
- `parse_frontmatter_doc` description states: "artifact callers use `required_fields=("id", "title", "type", "summary")` because artifact frontmatter retains a `type` field."
- Required Fields section states: "Artifact callers pass `required_fields=("id", "title", "type", "summary")` because artifact frontmatter retains a `type` field."
- The `exclude_type` Parameter section (lines 79–89) documents the parameter with a caller table.

**Proposed change:**

In **Public Interface**, `parse_frontmatter_doc` signature and description:
- Replace `parse_frontmatter_doc(filepath, required_fields=("id","title","summary"), exclude_type=None, extra_fields=()) -> dict | None` with `parse_frontmatter_doc(filepath, required_fields=("id","title","summary"), extra_fields=()) -> dict | None`
- Remove `exclude_type` from the Input parameter list.
- Remove the sentence about artifact callers using `("id","title","type","summary")`.

In **Public Interface**, `parse_frontmatter_doc_full` signature and description:
- Same: remove `exclude_type=None` from signature and description.
- Remove the artifact-caller note.

In **Required Fields** section:
- Remove the sentence: "Artifact callers pass `required_fields=("id", "title", "type", "summary")` because artifact frontmatter retains a `type` field."
- Replace with: "Artifact callers use the default `required_fields=("id", "title", "summary")`."

Remove the **`exclude_type` Parameter** section entirely (the heading and all content including the caller table).

---

### `tech-api-surface`

**Current state:**
- The `chaos_documents` Notes section states: "On success, each dict has keys `id`, `type`, `title`, `summary`, `body`."

**Proposed change:**

In the **`chaos_documents` Notes** section:
- Replace "On success, each dict has keys `id`, `type`, `title`, `summary`, `body`." with "On success, each dict has keys `id`, `title`, `summary`."

Note: The JSON schemas in the main API table rows do not enumerate dict keys inline — they reference function signatures. No other changes are needed in this document.

---

### `tech-arch-source-layout`

**Current state:**
- `frontmatter.py` module table row includes `exclude_type=None` in both function signatures and the sentence "The `required_fields` parameter allows callers to specify which frontmatter fields must be present; artifact callers use `("id","title","type","summary")` as artifacts retain a `type` field."
- `artifact.py` row states "Dict contracts unchanged" (acceptable as-is after the change, but no specific `type` mention).

**Proposed change:**

In the **module table**, `frontmatter.py` row:
- Replace the description of both function signatures to remove `exclude_type=None`:
  - `parse_frontmatter_doc(filepath, required_fields=("id","title","summary"), extra_fields=())`
  - `parse_frontmatter_doc_full(filepath, required_fields=("id","title","summary"), extra_fields=())`
- Remove the sentence "The `required_fields` parameter allows callers to specify which frontmatter fields must be present; artifact callers use `("id","title","type","summary")` as artifacts retain a `type` field."
- Replace with: "The `required_fields` parameter specifies which frontmatter fields must be present; the default `("id","title","summary")` applies to all callers."

---

### `tech-cli-commands`

**Current state:**
- `lore artifact list` command description reads: "Return a table of available artifact templates: every artifact's ID, type, group, title, and summary. No body content. Human-readable output is a table with columns `ID`, `TYPE`, `GROUP`, `TITLE`, `SUMMARY`."
- `lore codex show` JSON schema includes `"type": "technical"`.
- `lore artifact list --json` schema includes `"type": "template"` in each record.
- `lore artifact show --json` schema includes `"type": "template"` in each record.

**Proposed change:**

In **`lore artifact list`** command description:
- Replace "Return a table of available artifact templates: every artifact's ID, type, group, title, and summary. No body content. Human-readable output is a table with columns `ID`, `TYPE`, `GROUP`, `TITLE`, `SUMMARY`." with "Return a table of available artifact templates: every artifact's ID, group, title, and summary. No body content. Human-readable output is a table with columns `ID`, `GROUP`, `TITLE`, `SUMMARY`."

In **`lore codex show <id> [id ...] --json`** schema — replace example:

```json
{
  "documents": [
    {
      "id": "tech-cli-commands",
      "title": "CLI Command Reference",
      "summary": "Complete CLI reference for Lore — every command, flag, argument, output format, JSON schema, exit codes, and error behaviours.",
      "body": "# CLI Command Reference\n\n## Init\n\n..."
    }
  ]
}
```

In **`lore artifact list --json`** schema — replace example:

```json
{
  "artifacts": [
    {
      "id": "transient-business-spec",
      "group": "transient",
      "title": "Business Specification Template",
      "summary": "Blank scaffold for writing a new business specification."
    }
  ]
}
```

In **`lore artifact show <id> [id ...] --json`** schema — replace example:

```json
{
  "artifacts": [
    {
      "id": "transient-business-spec",
      "title": "Business Specification Template",
      "summary": "Blank scaffold for writing a new business specification.",
      "body": "# {Title}\n\n## Problem\n\n..."
    },
    {
      "id": "transient-full-spec",
      "title": "Full Specification Template",
      "summary": "Blank scaffold for writing a full technical specification.",
      "body": "# {Title}\n\n..."
    }
  ]
}
```

---

## Documents to Retire

None. No existing codex document has been superseded or made redundant by this feature.

---

## Consistency Check

- `conceptual-entities-artifact` → updated to match new three-field contract; consistent with `conceptual-workflows-artifact-list` update.
- `conceptual-workflows-artifact-list` → updated columns and required fields; consistent with `conceptual-entities-artifact` and `tech-cli-commands` updates.
- `conceptual-workflows-codex` → preconditions and JSON schema updated; consistent with `tech-cli-commands` update.
- `conceptual-workflows-codex-chaos` → output format description updated; consistent with `tech-api-surface` and `tech-cli-commands`.
- `tech-arch-frontmatter` → `exclude_type` section removed; required fields note corrected; consistent with `tech-arch-source-layout` update.
- `tech-api-surface` → chaos return shape corrected to `{id, title, summary}`; consistent with tech spec FR-7 and `conceptual-workflows-codex-chaos`.
- `tech-arch-source-layout` → function signatures corrected; consistent with `tech-arch-frontmatter`.
- `tech-cli-commands` → JSON schemas updated across artifact list, artifact show, codex show; consistent with all other updates above.

No contradictions are introduced. Documents not listed here (`decisions/`, `standards/`, `tech-db-schema`, `conceptual-entities-*` other than artifact, operations docs) do not reference the `type` frontmatter field and require no changes.

---

## Workflow Coverage

This feature does not introduce any new CLI commands and does not remove any CLI commands. It modifies the output of five existing commands (`lore codex list`, `lore codex search`, `lore codex map`, `lore codex chaos`, `lore artifact list`) by dropping the `type` field from their output. All five commands already have workflow documents. No new workflow documents are needed.

| Command / Flow | Workflow ID | Action |
|----------------|-------------|--------|
| `lore artifact list` | `conceptual-workflows-artifact-list` | Update (columns and required fields) |
| `lore codex list` | `conceptual-workflows-codex` | Update (preconditions) |
| `lore codex search` | `conceptual-workflows-codex` | No change needed (search already omits type in current doc) |
| `lore codex show` | `conceptual-workflows-codex` | Update (JSON schema) |
| `lore codex map` | `conceptual-workflows-codex-map` | No change needed (map doc has no type references) |
| `lore codex chaos` | `conceptual-workflows-codex-chaos` | Update (output format description and JSON schema) |

---

## Coverage Gaps

None identified. All eight documents with stale `type` field references are listed above with specific changes. The `tech-arch-codex-map` and `tech-arch-codex-chaos` technical architecture docs were inspected and contain no `type` field references in their body. The `conceptual-workflows-codex-map` doc was inspected and contains no `type` field references. Database schema docs (`tech-db-schema`) document `Dependency.type` which is an unrelated DB column — not touched.
