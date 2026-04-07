# Getting Started with Lore Agent Skills

`lore init` placed these files in `.lore/`. They are not active until you move them to the right place for your agent framework.

## Step 1 — Add the agent prompt

Copy the contents of `.lore/LORE-AGENT.md` into whichever file your agent framework reads:

| Framework     | File          |
|---------------|---------------|
| Claude Code   | `CLAUDE.md`   |
| OpenAI Codex  | `AGENTS.md`   |
| Other         | Whatever your framework reads at project root |

If the file already exists, append the content — do not replace it.

## Step 2 — Install skills (optional but recommended)

Skills give your agent step-by-step workflows for common tasks. Without them, your agent will still work, but it will have to figure out the process each time.

**Claude Code** — copy to `.claude/skills/`:
```
cp -r .lore/skills/. .claude/skills/
```
Then invoke with the Skill tool (e.g. `/start-quest`, `/new-doctrine`).

**Other frameworks** — check your framework's documentation for custom command or skill directories.

## Available skills

| Skill            | What it does                                                    |
|------------------|-----------------------------------------------------------------|
| `start-quest`    | Read a doctrine, create a quest and its missions, ask before dispatching |
| `new-doctrine`   | Draft and create a new doctrine via `lore doctrine new`        |
| `new-knight`     | Draft and create a new knight persona via `lore knight new`    |
| `new-watcher`    | Draft and create a new watcher via `lore watcher new`          |
| `new-artifact`   | Draft and create a new artifact file in `.lore/artifacts/`     |
| `explore-codex`  | Search, map, and traverse the codex to answer a question       |
