---
id: xa-apply-harness
feature: memory
route: harness
---
## Applying the change

Write the file yourself under `.lore/codex/<layer>/<id>.md`, frontmatter block first. Create the layer directory if it
does not exist. To retire a document, delete the file, then grep the tree for its id and remove every `related` entry
that named it, because nothing does that for you.

Three things the CLI would have done that you now own:

- **Frontmatter normalisation.** Key order, list formatting and the trailing newline are yours to get right.
- **Schema validation, including any `.lore/custom-schemas/` overlay.** A project-local required field is not visible in
  the shape above.
- **Group derivation.** The subdirectory under `.lore/codex/` is the document's group; put the file in the right one.
