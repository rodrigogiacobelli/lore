---
name: update-watcher
description: Create or edit a watcher — the project-state condition it fires on and what it runs
---

# Update Watcher

Author a Lore watcher. This skill **creates a watcher or edits an existing one**, whichever the request calls for — "make the changelog watcher fire on merge too" and "watch for blocked missions" both land here.

Watchers are YAML definitions for agents that monitor and react to project state — they describe what to watch for and what to do when it triggers.

## Creating or editing

- **Editing** — the watcher exists. Read it in full first (`lore watcher show <name>`), then change the one field the request names. A single-field edit is cheaper and safer than a whole-file replace.
- **Creating** — nothing watches for this condition yet. Run the whole flow below.

Watchers are reached through the Lore CLI in every access mode: the watcher tree hides a `default/` versus flat split, slash-derived groups and `.deleted` soft-delete naming.

## Steps

### 1. Understand the watcher

Ask the user (or read from context):
- What should this watcher monitor? (e.g. "when a quest closes", "when a mission is blocked", "when a file changes")
- What should it do when it triggers?
- How often or under what conditions should it fire?

### 2. Check existing watchers

```
lore watcher list
lore watcher show <existing-or-target-watcher>
```

A watcher reacts to project state, so check what the project already records about that state — a condition already governed by a documented rule should reference it rather than restate it:

<!-- lore:access cli -->
```
lore codex search <state-keyword>
lore codex show <id1> <id2>
```
<!-- lore:access end -->
<!-- lore:access native -->
Grep `.lore/codex/**/*.md` for the state the watcher reacts to and read the candidates directly. Glossary terms are not attached to what you read — look up an unfamiliar one in `.lore/codex/glossary.yaml`.
<!-- lore:access end -->

`lore codex map <id>` and `lore impacts <path-or-id>` stay on the CLI in every mode.

### 3. Draft the YAML

Write the watcher definition to a temporary file. Use the existing watcher format as your template — `lore watcher show` of an existing one gives you the schema to follow.

### 4. Create or edit

**Create:**

```
lore watcher new <name> --from <temp-file>
```

`-f` is the short form of `--from`. To nest watchers under a subdirectory, pass `--group <subdir>` (example: `lore watcher new nightly-check --group team-a/nightly -f <temp-file>` lands the file under `.lore/watchers/team-a/nightly/`).

**Edit an existing watcher:**

- Whole-file replace: `lore watcher edit <name> -f <file>`
- Single-field tweak (cheaper, and the default choice for an edit): `lore watcher edit <name> --set KEY=VALUE` (or `--unset KEY`, `--add KEY=VALUE`, `--remove KEY=VALUE` for list fields)

**Retire a watcher:** `lore watcher delete <name>` — a soft delete, so the file is renamed rather than destroyed.

### 5. Verify

```
lore watcher show <name>
```
