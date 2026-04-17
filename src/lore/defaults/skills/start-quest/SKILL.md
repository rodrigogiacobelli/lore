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

Read the full doctrine. Note:
- The phases and their order
- The step IDs, titles, types (`knight`, `constable`, `human`), knights, and `needs` dependencies
- If the user asked for a trimmed run, identify which steps to include and which to skip

### 2. Check existing quests (for naming context)

```
lore list
```

### 3. Create the quest

```
lore new quest "<feature title>" -d "<one paragraph description of the change>" --auto-close
```

Use the feature description as the title, not the doctrine name.

### 4. Create all missions

For each step in the doctrine (or the trimmed subset), create one mission:

```
lore new mission -q <quest-id> "<step title>" \
  -d "<description>" \
  -k <knight-file> \
  -T <type> \
  -p <phase-number>
```

The mission description must be **self-contained**. A worker agent will execute this mission using only its description. Include:
- What the agent must do (from the doctrine step notes)
- The feature context (what is being built and why)
- Acceptance criteria
- Relevant file paths or constraints from the user's input

Use the knight from the doctrine step if one is specified (`-k`).
Set `-T` to the step type: `knight`, `constable`, or `human`.
Set `-p` to the phase number from the doctrine.

Keep a local mapping of `doctrine-step-id → mission-id` as you create each mission. Mission IDs returned by `lore new mission` are fully qualified (`q-xxxx/m-yyyy`). Store the full ID in the mapping.

### 5. Declare dependencies

For each mission that has a `needs:` list in the doctrine, declare the dependency using the real fully-qualified mission IDs:

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
- Board messages defined in doctrine steps (agents posting to downstream missions) are wiring instructions — preserve them in the relevant mission descriptions so workers know to send them
