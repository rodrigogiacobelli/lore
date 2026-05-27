# Getting Started with Lore Agent Skills

Prereq: `pip install lore-agent-task-manager && lore init` in your project root. That created the `.lore/` directory you're reading from now.

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

The full skills table lives in `.lore/LORE-AGENT.md` — single source of truth so the list stays in sync with what your agent sees.

## Step 3 — Edit your project files

`lore init` seeded three user-tracked files you should review and edit:

- **`.lore/codex/codex.md`** — project-wide rules and conventions. Agents read this first.
- **`.lore/codex/glossary.yaml`** — controlled vocabulary. Run `lore artifact show glossary-design` before adding entries.
- **`.lore/config.toml`** — generic project config (e.g. glossary auto-surface toggle).

## Verify

Run `lore health` — should exit 0 on a fresh init.
