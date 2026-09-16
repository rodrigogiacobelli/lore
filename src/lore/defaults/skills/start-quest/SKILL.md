---
name: start-quest
description: Read a doctrine, create a quest and its missions, ask before dispatching
---

# Start Quest

Start a new Lore quest from a doctrine. Use this when you have a feature, bugfix, or change to implement and a doctrine to drive it.

You need two things from the user before starting:
1. The doctrine ID (e.g. `feature-implementation`, `tdd-implementation`)
2. A description of the feature, bugfix, or change — as detailed as possible
3. Optionally: which phases to include if they want a trimmed run (e.g. "only phases 2 and 3")

If either of the first two is missing, ask before proceeding.

## Steps

### 1. Read the doctrine

```
lore doctrine show <doctrine-id>
```

One call returns the design document and a `--- Missions ---` index of every mission in the doctrine. Read the design in full. Note:
- The phases and their order
- The mission ids, titles, types (`agent`, `constable`, `human`), and depends-on edges from the design table
- If the user asked for a trimmed run, identify which missions to include and which to skip

Read a mission body only when you need to know what the worker will be told:

```
lore doctrine show <doctrine-id> --mission <mission-id>
```

You do not need to read every mission body to plan the quest. The design table carries the workflow; the mission body is the worker's brief, and the worker receives it automatically through `-D`.

### 2. Check existing quests (for naming context)

```
lore list
```

Before drafting missions, align on the project's vocabulary — use its canonical keywords in titles and descriptions instead of synonyms, so every downstream worker reads the same word for the same thing.

<!-- lore:access cli -->
```
lore glossary list
lore codex search <feature-keyword>
lore codex show <id1> <id2>
```

Batch ids into one `lore codex show` call — it deduplicates and appends the glossary terms it matched.
<!-- lore:access end -->
<!-- lore:access native -->
Read `.lore/codex/glossary.yaml` for the vocabulary, then grep `.lore/codex/**/*.md` for the feature and read the candidates directly with your own file tool. Glossary terms are not attached to what you read, so look up an unfamiliar one yourself.
<!-- lore:access end -->

`lore codex map <id>` and `lore impacts <path-or-id>` stay on the CLI in every mode — no file read reproduces a precomputed traversal or the bidirectional `binds:` index. Run `lore impacts` over the paths the feature touches and name the governing documents in the mission descriptions, so a worker inherits its obligations instead of discovering them.

Doctrines, quests and missions are reached through the Lore CLI in every mode: `lore doctrine show` assembles the mission index across the doctrine directory and hides a `default/` versus flat split and slash-derived groups, `lore show <mission-id>` splices in the doctrine mission body, and quests and missions are SQLite-backed.

### 3. Create the quest

```
lore new quest "<feature title>" -d "<one paragraph description of the change>" --auto-close
```

Use the feature description as the title, not the doctrine name.

### 4. Create all missions

For each mission in the doctrine (or the trimmed subset), create one Lore mission:

```
lore new mission -q <quest-id> "<mission title>" \
  -d "<description>" \
  -D <doctrine-id>/<mission-id> \
  -T <type> \
  -p <phase-number>
```

`-D` stores the reference `<doctrine-id>/<mission-id>`. Lore resolves it at read time, so `lore show <mission-id>` hands the worker the doctrine mission body under `--- Mission Instructions ---` alongside the description. That is what makes the description feature-specific rather than a copy of the doctrine.

The mission description carries **what is specific to this run** — the worker already receives the doctrine mission body through `-D`, so do not restate it. Include:
- The feature context (what is being built and why)
- Acceptance criteria for this run
- Relevant file paths or constraints from the user's input
- The board wiring: which mission ids this worker posts to

Set `-T` to the mission type from the design table: `agent`, `constable`, or `human`.
Set `-p` to the phase number from the design table.

Keep a local mapping of `doctrine-mission-id → mission-id` as you create each mission. Mission IDs returned by `lore new mission` are fully qualified (`q-xxxx/m-yyyy`). Store the full ID in the mapping.

### 5. Declare dependencies

For each mission with a depends-on entry in the design table, declare the dependency using the real fully-qualified mission IDs:

```
lore needs q-xxxx/m-yyyy:q-xxxx/m-zzzz q-xxxx/m-aaaa:q-xxxx/m-yyyy
```

Always use the `q-xxxx/m-yyyy` form — passing a bare `m-yyyy` will fail with "Mission not found". Repeat pairs until all dependencies are declared.

### 6. Show the result

```
lore show <quest-id>
lore ready
```

Present the quest and missions to the user. Show the first mission(s) that are ready to dispatch.

### 7. Ask before dispatching

Do **not** dispatch agents yet. Ask the user:

> "Quest created with N missions. The first agent(s) ready to dispatch are: [list]. Shall I proceed?"

Only dispatch after explicit confirmation.

## Notes

- `constable` missions are orchestrator chores — claim and handle them inline, do not dispatch a subagent
- `human` missions must not be claimed — leave them for the user
- If the user asked to trim phases, only create missions for the requested phases and adjust dependencies accordingly
- Board wiring the doctrine mission bodies describe (workers posting to downstream missions) needs the real mission ids — put them in the relevant mission descriptions so workers know where to send them
