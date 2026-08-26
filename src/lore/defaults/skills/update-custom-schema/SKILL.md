---
name: update-custom-schema
description: Create or edit a custom-schema overlay that adds project-specific codex frontmatter fields
---

# Update Custom Schema

Author a custom frontmatter field for a codex doc kind without hand-writing JSON-Schema. This skill **creates an overlay or edits an existing one**, whichever the request calls for — "make `owner` required" and "add a `reviewed_at` field" both land here.

The codex ships a fixed packaged schema per kind; a **custom-schema overlay** at `.lore/custom-schemas/<kind>.yaml` adds extra project-specific fields on top. Overlays are **add-only**: you may add new keys (and mark them required), but you may never override, redefine, or drop a packaged field. The resolver merges the overlay onto the packaged base, pins `additionalProperties: false`, appends your `required` entries, and keeps the packaged `$id` — so a doc that carries a custom field validates the same way everywhere (`lore codex new/edit`, `lore health`, and Realm's `lore.api`). The one exception is `.lore/codex/transient/**`, which stays on the packaged schema; see step 1.

This skill interviews you for the kind, the fields, and which are required; runs the add-only guard **before** writing so a malformed overlay never lands; writes the overlay; then runs `lore health` so you get immediate confirmation.

## Steps

### 1. Pick the target kind

Overlays are discovered by filename — `<kind>.yaml` — with no config. For v1 exactly two kinds are eligible:

| Kind | Applies to | Overlay file |
|------|-----------|--------------|
| `codex-frontmatter` | canonical codex docs (`.lore/codex/...`) | `.lore/custom-schemas/codex-frontmatter.yaml` |
| `codex-source-frontmatter` | codex **sources** layer (`.lore/codex/sources/...`) | `.lore/custom-schemas/codex-source-frontmatter.yaml` |

Ask the author which kind they want to extend. If an overlay file for that kind already exists, read it and **edit** it — add to or adjust its `properties` / `required` rather than overwriting the file. Each kind gets at most one overlay file, so an overwrite silently drops every field the project already declared.

An overlay is a plain project file at a path you know, not a Lore entity with an id, so you read and write it the same way in every access mode. What differs is how you read the docs it will govern:

<!-- lore:access cli -->
```
lore codex list
lore codex show <doc-id>
```
<!-- lore:access end -->
<!-- lore:access native -->
List `.lore/codex/` and read the documents directly with your own file tool. Glossary terms are not attached to what you read — look up an unfamiliar one in `.lore/codex/glossary.yaml`.
<!-- lore:access end -->

**Transient docs are out of scope.** Neither overlay reaches `.lore/codex/transient/` — the in-flight working docs (PRDs, tech specs, context maps, and the reports `lore health` writes there itself when `health-report-retention` is `"latest"` or `"all"`). They validate against the packaged schema alone, so a `required` custom field never blocks the spec pipeline and never turns a past health report into an error. The flip side: a transient doc may not *carry* a custom field either — it fails `Unknown property`. Custom fields are governance for permanent codex knowledge. Fixed by ADR-019; the scope is not configurable.

### 2. Collect the fields

For each custom field the author wants, gather three things:

- **name** — the frontmatter key (e.g. `owner`, `reviewed_at`, `tags`).
- **type** — the JSON-Schema type: `string`, `integer`, `number`, `boolean`, `array`, or `object`. Optionally a small constraint the author asks for (`minLength: 1` for a non-empty string, `format: date`, `enum: [...]`, `items: {type: string}` for an array). Keep it minimal — the overlay is a JSON-Schema fragment.
- **required?** — must every doc of this kind now carry the field, or is it optional?

### 3. Run the add-only guard — BEFORE writing

The resolver rejects a bad overlay with `OverlayError`, but catch it here first so you never write a file that `lore health` will flag. Check, for the chosen kind:

**(a) Collision check.** No custom field name may collide with a **packaged** field of that kind. If a proposed name is in the protected set below, stop — the key cannot be added or overridden. Ask the author to rename it.

| Kind | Protected (packaged) keys — never add or override |
|------|---------------------------------------------------|
| `codex-frontmatter` | `id`, `title`, `summary`, `type`, `related`, `binds`, `rites` |
| `codex-source-frontmatter` | `id`, `title`, `summary`, `type`, `related` |

**(b) Undeclared-required check.** Every name in `required:` must be a field this overlay declares in `properties:`. You may not require a packaged field (it is already governed by the base) nor a name that does not appear in your `properties`. If a required name is not among the fields collected in step 2, stop and fix it.

Only when both checks pass do you write the file.

### 4. Write the overlay

Write `.lore/custom-schemas/<kind>.yaml` in the **add-only** shape — creating the file, or rewriting it with the existing fields plus your change: a header comment, a `properties:` mapping (required), and an optional `required:` list. Do **not** emit `additionalProperties`, `$id`, `$schema`, `title`, or `type: object` at the top level — the resolver synthesizes all of that from the packaged base and ignores any other top-level keys you add.

```yaml
# Add-only overlay for codex canonical-doc frontmatter.
# Merged onto the packaged codex-frontmatter schema. New keys only.
properties:
  owner:
    type: string
    minLength: 1
    description: Team or person accountable for this doc.
required:
  - owner
```

Omit the `required:` block entirely if every custom field is optional. The directory `.lore/custom-schemas/` is created on demand — it is never seeded by `lore init`, so `mkdir -p .lore/custom-schemas` first if it does not exist.

### 5. Run `lore health` and report

```
lore health --scope schemas
```

This builds the merged validator for the kind and validates every existing doc against it. Report the result to the author:

- **0 errors** — the overlay is well-formed and every existing doc satisfies it. Done.
- A `scan_failed` issue naming the overlay — the overlay itself is malformed (the guard in step 3 missed something, e.g. unparseable YAML or a collision). Fix the overlay.
- A per-doc validation error — the overlay is well-formed, but an existing doc now violates it (typically a newly `required` field that older docs lack). Either make the field optional or backfill the docs, then re-run.

Backfill one doc at a time.

<!-- lore:access cli -->
Field-edit mode resolves the same merged schema, so it is the safe way to add a newly required field:

```
lore codex edit <doc-id> --set owner=alice
lore codex edit <doc-id> --set tags=a,b          # array fields comma-split
```

To drop a custom field again, remove it from the overlay's `properties` and `required`, then `lore codex edit <doc-id> --unset <field>` on every doc that carries it — a doc holding a field no overlay declares fails with `Unknown property`.
<!-- lore:access end -->
<!-- lore:access native -->
Add the key to each document's frontmatter block yourself, in the type the overlay declares — a scalar as a plain value, an array as a YAML list. To drop a custom field again, remove it from the overlay's `properties` and `required`, then delete the key from every doc that carries it: a doc holding a field no overlay declares fails with `Unknown property`.

Nothing validates a hand-edit as you make it, so re-run `lore health --scope schemas` after the batch and read it as the verdict on the whole backfill.
<!-- lore:access end -->

Only canonical docs and sources will appear in the error list — transient docs are out of scope and never need backfilling.

## Notes

- **Add-only, always.** The overlay never reads a value out of the packaged schema — it only adds. You cannot loosen a packaged constraint, make a packaged field optional, or change its type. To change packaged behavior you would change the packaged schema, which is out of scope for this skill.
<!-- lore:access cli -->
- **Canonical-only, always.** The same merged schema governs `lore health`, `lore codex new`, and both `lore codex edit` modes (`-f` and `--set`) — but only for canonical docs and sources. `.lore/codex/transient/` is packaged-schema territory at every one of those seams (ADR-019).
<!-- lore:access end -->
<!-- lore:access native -->
- **Canonical-only, always.** The merged schema governs canonical docs and sources and nothing else; `.lore/codex/transient/` is packaged-schema territory (ADR-019). A document written with your own file tool is validated by nothing until `lore health` runs, so that run is the whole of the guarantee here.
<!-- lore:access end -->
- **No CLI command.** There is no `lore schema` command — discovery is convention (the filename) plus this skill plus the docs. The overlay is a plain project file, not Lore state.
- **Parity.** The same merged schema is reached from the CLI and from Realm via `lore.api` (`validate_entity(kind, data, project_root=...)`, `project_validator_for`). Authoring the overlay here changes validation for both consumers at once.
