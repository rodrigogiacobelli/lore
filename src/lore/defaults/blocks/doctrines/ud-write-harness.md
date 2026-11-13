---
id: ud-write-harness
feature: doctrines
route: harness
---
### 4. Write the doctrine

Create the directory `.lore/doctrines/<group>/<name>/` (the group is optional) holding `<name>.design.md` and
`missions/<mission-id>.md` for each mission. Write only the files the request names and leave the rest byte-identical.

Three things the CLI would have done that you now own:

- **Identity.** The design's `id` equals the directory name; each mission's `id` equals its filename stem.
- **At least one mission.** A doctrine with an empty `missions/` directory is not a doctrine.
- **Retirement.** To retire a doctrine, delete its directory, then search the project for the id and remove every
  mention of it.
