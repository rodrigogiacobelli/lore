---
id: sg-steps
feature: memory
commands: [--version, init]
---
## Steps

### 1. Confirm the precondition

```
lore --version
```

Confirm with the user that they upgraded `lore` before invoking this skill. If they did not, stop: there will be nothing
to merge.

### 2. Refresh the seed

```
lore init --yes
```

Idempotent and safe. `--yes` accepts the resolved answer for every question, so the run stays unattended even from a
terminal. It overwrites only Lore-owned files: the default trees under `.lore/` are replaced in place and
`.lore/LORE-AGENT.md` is re-rendered. Installed skills go through reconciliation instead: one you have edited is reported
and left alone unless you pass `--on-conflict overwrite`. It never touches `.lore/codex/codex.md` or
`.lore/codex/glossary.yaml`, it rewrites only the leading comment block of `.lore/config.toml`, and it replaces only the
marked block inside an agent instruction file.
