---
id: ua-write-cli
feature: artifacts
route: cli
commands: [artifact new, artifact edit, artifact delete]
---
### 4. Create or edit the artifact

The CLI validates frontmatter and lands the file under `.lore/artifacts/`:

```
lore artifact new <slug> -f draft.md      # new artifact
lore artifact edit <slug> -f draft.md     # replace an existing one
lore artifact new audit-checklist --group security -f draft.md    # nest under .lore/artifacts/security/
```

To retire an artifact, `lore artifact delete <slug>` is a soft delete, so the file is renamed rather than destroyed.
