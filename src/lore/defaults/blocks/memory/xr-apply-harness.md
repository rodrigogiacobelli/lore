---
id: xr-apply-harness
feature: memory
route: harness
---
## Applying the change

Group small steps by platform or system (`portal/`, `backoffice/`, `db/`) so the tree stays browsable. The group is
optional; omit it for the root.

Write the YAML yourself under `.lore/rites/main/<group>/<id>.yaml`, or `.lore/rites/shared/<group>/<id>.yaml` for a
shared step. Create the group directory if it does not exist; delete the file to retire the rite.

Two things the CLI would have done that you now own:

- **Schema selection.** A main rite and a shared step validate against different schemas, and the subfolder is what
  picks one. A shared step written under `main/` fails validation.
- **Id uniqueness across the whole tree.** Grep both trees for the id before you write, because the folder is not part
  of identity.

Read the rite back afterwards the way the next agent will: your file tool does not inline the `use:` steps, so follow
each bare id to its file under `.lore/rites/shared/` and read the procedure end to end. A step that resolves to nothing
is a `dangling_use`.
