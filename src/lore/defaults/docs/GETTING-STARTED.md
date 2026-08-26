# Getting Started with Lore

Prereq: `pip install lore-agent-task-manager && lore init` in your project root. That created the `.lore/` directory you're reading from now.

## Step 1 — What `lore init` already did

`lore init` wires your agents up itself; there is nothing to copy by hand.

Run in a terminal, it asked which coding agents this project uses, how they should reach Lore's files, and which skill families to install — then printed every file it would create, replace or remove and waited for your confirmation. Run from a pipe, a CI job, or the Python API, it prompted for nothing and took its answers from the flags you passed, from `.lore/config.toml`, and from its built-in defaults.

For each agent you selected, it wrote an instruction file and installed the skills:

| Agent                                       | Instruction file         | Skills install to |
|---------------------------------------------|--------------------------|-------------------|
| Claude Code                                  | `CLAUDE.md`              | `.claude/skills/` |
| Codex, Cursor, Windsurf, Zed, Amp, OpenCode  | `AGENTS.md`              | `.lore/skills/`   |
| Gemini CLI                                   | `GEMINI.md`              | `.lore/skills/`   |
| Qwen Code                                    | `QWEN.md`                | `.lore/skills/`   |
| Cursor — native rules                        | `.cursor/rules/lore.mdc` | `.lore/skills/`   |
| None                                         | —                        | `.lore/skills/`   |

Lore's guidance sits inside `<!-- lore:begin -->` … `<!-- lore:end -->` markers in the instruction file. Everything outside the markers is yours, and re-running `lore init` replaces only what is between them.

The same text is written in full to `.lore/LORE-AGENT.md` on every run, whether or not you selected an agent. If your framework is not in the table above, copy that file into whatever it reads at project root — and check its documentation for a skills or custom-command directory to point at `.lore/skills/`.

`.lore/LORE-AGENT.md` also carries the table of installed skills and where each one landed — the single source of truth, so the list always matches what your agent sees.

## Step 2 — Re-run it whenever the answers change

`lore init` is idempotent, and re-running it reconciles: it installs what is newly selected, removes what Lore installed and you have since deselected, and reports any skill a release retired along with its successor.

```
lore init --reconfigure      # ask the four recorded questions again (needs a terminal)
lore init --dry-run          # print the plan and write nothing
lore init --help             # every prompt also has a flag
```

Four answers are recorded in `.lore/config.toml` and reused on later runs — the agents, the access mode, the skill families, and how installed skills are tracked in git.

### Lore owns the files it installs

A skill, knight, doctrine, artifact or watcher that Lore shipped is Lore's. Re-running `lore init` replaces it with this release's version however you have edited it, and removes it — naming its successor — if the release has retired it. Nothing asks first; `lore init --dry-run` shows you every one of them before anything is written.

So put your own work where Lore does not write:

| Yours | Lore's |
|---|---|
| `.lore/knights/<your-own-id>.md` | `.lore/knights/default/` |
| `.lore/doctrines/<your-own-id>/` | `.lore/doctrines/default/` |
| `.lore/artifacts/<your-own-id>.md` | `.lore/artifacts/default/` |
| `.lore/watchers/<your-own-id>.yaml` | `.lore/watchers/default/` |
| `.claude/skills/<your-own-id>/` — any id Lore does not ship | every skill in the table `.lore/LORE-AGENT.md` lists |

Knights, doctrines, artifacts and watchers say it with a `default/` subdirectory. Skills have no such directory — they install straight into `.claude/skills/` or `.lore/skills/` — so the id **is** the boundary: a directory named after a skill Lore ships belongs to Lore, and one named anything else is never changed or removed by any run. What Lore replaces and removes is what its own install record says it put there, so a name Lore happens to have used in the past is not a name it will take. To customise a skill Lore ships, copy its directory to an id of your own and edit the copy.

A file Lore did **not** install, sitting at a path Lore wants to write, is the one conflict left. Lore leaves it alone and reports it — every run, not just the first — unless you pass `--on-conflict overwrite` to hand the path over.

## Step 3 — Edit your project files

`lore init` seeded three user-tracked files you should review and edit. What you write in them survives every later run:

- **`.lore/codex/codex.md`** — project-wide rules and conventions. Agents read this first. Never touched once it exists.
- **`.lore/codex/glossary.yaml`** — controlled vocabulary. Run `lore artifact show glossary-design` before adding entries. Never touched once it exists.
- **`.lore/config.toml`** — generic project config. Every known key is described in the comment block at the top; `lore init` regenerates that block on each run, so a project learns about keys added after it was created. Every settings line below it is yours and is left exactly as you set it.

## Verify

Run `lore health` — should exit 0 on a fresh init.
