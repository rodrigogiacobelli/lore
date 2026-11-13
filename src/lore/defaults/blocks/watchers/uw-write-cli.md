---
id: uw-write-cli
feature: watchers
route: cli
commands: [watcher new, watcher edit, watcher delete]
---
### 4. Create or edit

**Create:** write the draft to a temporary file, then

```
lore watcher new <name> --from <temp-file>
```

`-f` is the short form of `--from`. To nest watchers under a subdirectory, pass `--group <subdir>` (for example
`lore watcher new nightly-check --group team-a/nightly -f <temp-file>` lands the file under
`.lore/watchers/team-a/nightly/`).

**Edit an existing watcher:**

- Whole-file replace: `lore watcher edit <name> -f <file>`
- Single-field tweak (cheaper, and the default choice for an edit): `lore watcher edit <name> --set KEY=VALUE` (or
  `--unset KEY`, `--add KEY=VALUE`, `--remove KEY=VALUE` for list fields)

**Retire a watcher:** `lore watcher delete <name>` is a soft delete, so the file is renamed rather than destroyed.
