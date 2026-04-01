# Lore

Lore is your project task manager. Run `lore --help` for the full command reference.

## Orchestrator

Use `lore ready` to get the next available mission. Dispatch based on mission type:

- **`knight`** — claim it (`lore claim <id>`), then spawn a worker agent passing the mission ID
- **`constable`**(or orchestrator) — claim it and handle inline (orchestrator chore — commit, housekeeping, etc.)
- **`human`** — do NOT claim; leave it for the human to complete

To start a new quest from a doctrine, use `/start-quest`. For creating doctrines, knights, watchers, artifacts, or exploring the codex, use the relevant skill.

## Worker

You have been assigned a mission ID by the orchestrator.

Run `lore show <id>` — this returns the mission description, acceptance criteria, and knight persona in a single call. Execute the mission. When done, run `lore done <id>`. If you are blocked, run `lore block <id> "<reason>"` with a clear explanation.

Do not create quests or missions. Do not claim work that has not been assigned to you.

## Available skills

| Skill            | What it does                                                    |
|------------------|-----------------------------------------------------------------|
| `start-quest`    | Read a doctrine, create a quest and its missions, ask before dispatching |
| `new-doctrine`   | Draft and create a new doctrine via `lore doctrine new`        |
| `new-knight`     | Draft and create a new knight persona via `lore knight new`    |
| `new-watcher`    | Draft and create a new watcher via `lore watcher new`          |
| `new-artifact`   | Draft and create a new artifact file in `.lore/artifacts/`     |
| `explore-codex`  | Search, map, and traverse the codex to answer a question       |