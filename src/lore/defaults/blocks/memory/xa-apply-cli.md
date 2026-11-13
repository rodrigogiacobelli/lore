---
id: xa-apply-cli
feature: memory
route: cli
commands: [codex new, codex edit, codex delete]
---
## Applying the change

Drive every change through the CLI. It normalises frontmatter and runs schema validation, including any project
overlay; a hand-edit skips both.

**Create.** Draft the body, frontmatter block included, to a temp file, then:

```
lore codex new <name> --group <subdir> -f <draft>.md
```

`--group` is slash-delimited (`decisions`, `technical/database/ref`). Add `--type codex-source` for a source snapshot.

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
