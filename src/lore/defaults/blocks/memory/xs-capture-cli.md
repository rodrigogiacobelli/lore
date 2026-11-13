---
id: xs-capture-cli
feature: memory
route: cli
commands: [codex new]
---
   Draft the snapshot to a temp file, then:

   ```
   lore codex new <id> --type codex-source --group sources/<system> -f <draft>.md
   ```

   `--type codex-source` selects the stricter four-field schema. `--group sources/<system>` creates the directory when
   it does not exist.
