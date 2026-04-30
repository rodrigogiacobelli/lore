# Codex

The codex is your project's documentation system. It lives at `.lore/codex/` as a graph of typed markdown documents — concepts, decisions, standards, workflows, and entity descriptions.

## Structure

Documents are organised by kind under subdirectories:

- `conceptual/` — entities, workflows, and other conceptual material
- `decisions/` — architectural decision records (ADRs)
- `standards/` — coding and process standards
- `ops/` — operational runbooks
- `glossary.yaml` — project vocabulary (see Glossary below)

Each markdown document carries frontmatter (`id`, `title`, `summary`, optional `related`) and a body. Use `lore codex show <id>` to read, `lore codex search <keyword>` to find, `lore codex map <id>` to traverse the related-link graph.

## Glossary

The glossary at `.lore/codex/glossary.yaml` holds short, canonical definitions for project-specific terms. Each item has a `keyword`, a `definition`, and optional `aliases` and `do_not_use` lists.

Read it with `lore glossary list`, `lore glossary search <q>`, or `lore glossary show <kw>`. On every `lore codex show`, Lore auto-attaches a `## Glossary` block listing each glossary item whose keyword or alias appears in the document body.

### When something goes in the glossary

The glossary is restrictive. Most candidate terms do NOT belong here. Before adding an entry, run:

```
lore artifact show glossary-design
```

The gate is three questions, all must be YES:

1. **Project-specific.** Generic IT vocabulary (ADR, soft-delete, E2E, mock, fixture, idempotent, …) does NOT qualify — assume the reader knows IT.
2. **Not an entity.** Entities (Quest, Mission, Knight, Doctrine, Codex, Artifact, Watcher, Glossary, plus system-level Camelot/Lore/Realm/Citadel) live in their own `conceptual-entities-<name>` doc. Link to it instead.
3. **Not a named workflow, command, or feature.** Anything with a `conceptual-workflows-<name>` doc, a CLI command, or a feature surface is documented there. Link to it instead.

If any answer is NO, write the entity doc / workflow doc / ADR / standards doc instead. The `glossary-design` artifact has worked examples and a "where to put it instead" table.
