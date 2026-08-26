# Reference — recording a fact as a codex document

Read this when the knowledge is semantic: something that is true about the
system as it exists today.

## Classify the layer

Pick the layer from the *The codex* section of `.lore/codex/codex.md` — that is
the canonical subdirectory map for this project, and it varies.

For a `ref-*` document, default to one cluster document per logical group rather
than one per entity, and make sure the `**Covers:**` line names every covered
entity verbatim, followed by a `**Source of truth:**` pointer at the schema's
home in code.

## Frontmatter

Exactly these fields, plus any project-local keys declared in a
`.lore/custom-schemas/` overlay:

```yaml
---
id: <unique-id>
title: <human title>
summary: <1-3 sentences for scanning>
related:        # optional; omit or use [] if none
  - <other-id>
binds:          # optional; repo-root-relative paths or globs this doc governs
  - <path-or-glob>
rites:          # optional; the rites this doc governs
  - <rite-id>
---
```

`lore health --scope codex` rejects anything else.

## Body rules

- No "Related Documentation" section — cross-references live in `related` alone.
- No duplicated facts — link instead.
- Workflow documents lead with the subject (system or user) and stay consistent.
- Decision records include the rejected alternatives; they tell a future agent
  what not to suggest again.
- Write the state, never the delta. "`binds:` maps a document to the code files
  it governs", not "this release added `binds:`".

## The `binds:` workflow

`binds:` is the codex↔code edge, and it points one way: the codex names the code,
never the reverse. A document with `binds: [src/lore/cli.py]` is surfaced by
`lore impacts src/lore/cli.py`. Populate it whenever a document governs specific
files — typically technical documents, standards, decision records and `ref-*`
clusters.

Globs use `**` for recursive descent (`src/lore/**/*.py`). Literal paths and
globs mix freely in one list. Absolute paths, `..` segments and empty strings
are rejected by the schema.

## Applying the change

<!-- lore:access cli -->
Drive every change through the CLI. It normalises frontmatter and runs schema
validation, including any project overlay; a hand-edit skips both.

**Create.** Draft the body — frontmatter block included — to a temp file, then:

```
lore codex new <name> --group <subdir> -f <draft>.md
```

`--group` is slash-delimited (`decisions`, `technical/database/ref`). Add
`--type codex-source` for a source snapshot.

**Replace the body:**

```
lore codex edit <name> -f <new-body>.md
```

**Field-edit the frontmatter without touching the body:**

```
lore codex edit <name> --set summary="..."        # scalar field
lore codex edit <name> --add related=<other-id>   # list field, append
lore codex edit <name> --remove related=<other-id>
lore codex edit <name> --add rites=<rite-id>
lore codex edit <name> --unset binds              # drop a field entirely
```

`--set` / `--unset` work on scalar fields; `--add` / `--remove` on list fields.

**Delete:**

```
lore codex delete <name>
```
<!-- lore:access end -->
<!-- lore:access native -->
Write the file yourself under `.lore/codex/<layer>/<id>.md`, frontmatter block
first. Create the layer directory if it does not exist. To retire a document,
delete the file — then grep the tree for its id and remove every `related` entry
that named it, because nothing does that for you.

Three things the CLI would have done that you now own:

- **Frontmatter normalisation.** Key order, list formatting and the trailing
  newline are yours to get right.
- **Schema validation, including any `.lore/custom-schemas/` overlay.** A
  project-local required field is not visible in the shape above.
- **Group derivation.** The subdirectory under `.lore/codex/` is the document's
  group; put the file in the right one.

`lore health --scope codex schemas` is what catches all three. Run it.
<!-- lore:access end -->

Verify the document's reach after editing `binds:`:

```
lore impacts <codex-id>          # the paths the doc claims
lore impacts <path-or-glob>      # the docs claiming this path
```

## Templates

```
lore artifact list
lore artifact show <template-id>
```

Use the matching template — a decision-record skeleton for `decisions/`, an
entity skeleton for `conceptual/entities/` — so frontmatter and body conventions
are right from the first draft. Artifacts are reached through the CLI in every
mode.
