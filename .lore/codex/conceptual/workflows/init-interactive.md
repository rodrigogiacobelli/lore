---
id: conceptual-workflows-init-interactive
title: Interactive lore init
summary: The user-facing flow when a person runs `lore init` at a terminal — the TTY
  gate, the seven prompts and the order they fire in, which prompts are conditional,
  the command-line flag that answers each one, the plan summary and its confirmation,
  and what `--yes`, `--dry-run` and `--reconfigure` do.
binds:
- src/lore/prompts.py
- src/lore/cli.py
- tests/e2e/test_init_interactive.py
- tests/unit/test_prompts.py
related:
- conceptual-workflows-lore-init
- conceptual-workflows-init-reconcile
- conceptual-workflows-error-handling
- conceptual-entities-skill
- tech-arch-agents-md
- tech-arch-skill-catalogue
- decisions-001-dumb-infrastructure
- decisions-011-api-parity-with-cli
- decisions-012-multi-value-cli-param-convention
- decisions-017-constrained-flags-use-click-choice
---

# Interactive `lore init`

**Role: the person setting up a project.** A developer adopting Lore on a repository runs `lore init` and is asked how their project works, rather than receiving a fixed set of files and a manual copy step.

## The TTY Gate

`lore init` prompts only when standard output is a terminal. When it is not — a pipe, a CI job, Realm calling `run_init()` — no prompt fires, and `lore init` proceeds on flags, recorded answers and defaults alone. Absence of a terminal selects defaults silently; it is never an error and never a hang.

This has one consequence worth knowing: `lore init | tee upgrade.log` is not a terminal, so the whole plan applies without being shown. `--dry-run` is how a person reads the plan first in that situation.

## The Prompts

Seven prompts, in this order. Five fire on every interactive run; two are conditional.

| # | Prompt | Fires when | Answer |
|---|---|---|---|
| 1 | Which coding agents does this project use? | Always | A multi-select over the agent registry. More than one may be selected. |
| 2 | How should agents read and write Lore's local files? | Always | `Their own tools` or `The Lore CLI`. |
| 3 | Which skill families should be installed? | Always | A multi-select over memory, machinery and workflow. |
| 4 | `<instruction file>` already exists and carries no Lore markers. What should Lore do? | A selected agent's instruction file exists without Lore's markers | `Append a Lore section` or `Leave it alone`. |
| 5 | How should the installed skills be tracked in git? | Every run — every project has an install root | `Ignore Lore's skills, track my own`, `Track everything`, or `Ignore the whole directory`. |
| 6 | *n* file(s) Lore did not install sit where Lore would write. What should Lore do? | Reconciliation found a path Lore wants holding a file it never installed | `Leave mine alone` or `Overwrite`. |
| 7 | Apply this plan? | Always, unless `--yes` | Yes or no. |

Prompt 1 shows each agent's label beside the file it writes, so the choice is legible without knowing the registry. Prompt 2 states its own scope: the access mode governs codex documents, rites and the glossary, while quests, missions, artifacts, knights, doctrines and watchers always go through the CLI. Prompt 3 preselects memory and workflow, and leaves machinery unselected.

A conditional prompt fires only in the case named. An instruction file that does not exist is created with markers, and one that already carries markers has its block replaced — neither asks.

Prompt 6 is narrower than its flag name suggests. Lore owns the files it installs (`conceptual-workflows-init-reconcile`), so an edited skill, knight or doctrine of Lore's is replaced — or removed, if the release retired it — without a question. The prompt fires only for a path Lore wants that holds a file **the project** put there, which is the one conflict where both answers do something. A conflict Lore cannot act on either way — a symlink, a path resolving out of the project — is reported and opens no prompt.

Ctrl-C at any prompt aborts: Lore prints `Aborted!` to stderr, writes nothing, and exits 1.

## The Summary

Before anything is written, `lore init` prints the plan — every file it would create, overwrite, remove or leave alone, with the reason beside each removal and each conflict — followed by a count line and prompt 7.

```
Plan for /home/dev/acme (agents: claude · access: native · families: memory, workflow)

  Create   .claude/skills/store-memory/SKILL.md
  Overwrite .claude/skills/start-quest/SKILL.md
  Remove   .claude/skills/new-rite/SKILL.md               merged into store-memory; your edit is discarded
  Conflict .claude/skills/house-style/SKILL.md            not installed by Lore
  Section  CLAUDE.md                                      replaces <!-- lore:begin --> block

  1 create · 1 section · 1 overwrite · 1 remove · 1 conflict

? Apply this plan? (Y/n)
```

Answering no prints `No changes applied.` and exits 0. Nothing is written.

## The Flags

Every prompt has a flag equivalent, so the whole flow is reachable from a script. Multi-value flags take space-separated tokens (`decisions-012-multi-value-cli-param-convention`); constrained flags reject an out-of-set token as a usage error at exit 2 (`decisions-017-constrained-flags-use-click-choice`).

| Flag | Answers | Notes |
|---|---|---|
| `--agent ID [ID ...]` | 1 | Registry ids. `--agent none` cannot be combined with another id. |
| `--access {cli,native}` | 2 | |
| `--skills FAMILY [FAMILY ...]` | 3 | Also accepts the aggregate tokens `all` and `none`. |
| `--on-existing-agent-file {append,skip}` | 4 | Defaults to `append`. |
| `--skills-gitignore {lore-only,none,all}` | 5 | |
| `--on-conflict {skip,overwrite}` | 6 | Defaults to `skip`. Governs a file Lore did not install; no say over Lore's own. |
| `-y, --yes` | 7, and every other prompt | Accepts the resolved answer for each prompt without asking. |
| `--reconfigure` | — | Asks again for the four recorded answers instead of reusing them. Needs a terminal to ask in, or all four supplied as flags. |
| `--dry-run` | — | Prints the plan and writes nothing. Exit 0. |

`--dry-run` and `--yes` compose, and `--dry-run` wins: nothing is written.

There is no `--force`. `--yes --on-conflict overwrite` says the same thing explicitly and composes with the rest — though it is the narrower flag it once was: Lore replaces its own files whichever way it is set.

Passing a flag suppresses only its own prompt. A run with `--access native` and nothing else still asks the other seven.

### Errors

An out-of-set token on any constrained flag is Click's standard usage error:

```
$ lore init --access agentic
Usage: lore init [OPTIONS]
Try 'lore init --help' for help.

Error: Invalid value for '--access': 'agentic' is not one of 'cli', 'native'.
```

Exit 2. Combining `--agent none` with another id is the same exit code with Lore's own message, `--agent none cannot be combined with other agents.`, raised before any file is read or written. The rule lives in `validators.validate_agent_selection`, so a Python caller passing `agents=["none", "claude"]` is rejected identically (`decisions-011-api-parity-with-cli`).

## Answers Are Recorded

Four answers — agents, access mode, skill families, skills gitignore — are written to `.lore/config.toml` and reused on every later run, so a project is asked once. The two that are not recorded — how to treat an existing instruction file, how to resolve a conflict — are decisions about a particular run, not about the project.

A third question used to sit here: whether to add Lore's entries to the project's root `.gitignore`. Both answers left the tree identically ignored, because every path the block named was already covered by the `*` opening `.lore/.gitignore` — so the prompt, the flag and the block are gone, and a project still carrying the block has it removed. `conceptual-workflows-lore-init` holds the removal.

On a later interactive run, each recorded answer is preselected at its prompt, so a person sees what the project is set to and confirms or changes it. `--reconfigure` drops the suppression, so all four are asked again.

Asking needs somewhere to ask. A run with no prompt — a pipe, CI, `--yes` — has no new answer to collect, and the recorded four are the only record of what this project installed: dropping them would resolve the agent selection to the built-in default of none, and a run with no agent selected removes every skill and every marked block Lore has written. So `lore init --reconfigure` without a terminal stops with a usage error naming the flags that would answer the questions it cannot ask, and writes nothing:

```
$ lore init --reconfigure --yes
Error: --reconfigure asks the four recorded questions again, and this run has no
terminal to ask in. Pass --agent, --access, --skills, --skills-gitignore to answer
without a prompt, or drop --reconfigure to reuse what .lore/config.toml records.
```

Exit 2. A caller that passes all four itself has supplied the new answers and is not asking for a prompt, so that run proceeds. On the Python surface `plan_init(reconfigure=True)` keeps its plain meaning — skip the config layer — because a caller passing keywords is stating the answers directly; the gate belongs to the flag, which promises a question.

### A recorded answer that no longer resolves

`.lore/config.toml` is a file people edit, and a value that loads can still be one `plan_init` refuses — `init-agents = ["none", "claude"]` is two valid registry ids and an illegal selection. That answer is taken again on every later run, so the message names the key holding it and the flag that replaces it rather than leaving the project to a text editor:

```
$ lore init --yes
Error: --agent none cannot be combined with other agents. init-agents in
.lore/config.toml records ["none", "claude"], and this run took it from there.
Re-run with --agent to record a new answer.
```

Exit 1, nothing written. `lore init --agent claude` then records the corrected answer. The same wording reaches a Python caller, because `plan_init` raises it.

Changing the access mode changes the content of every installed skill, so those files reconcile as ordinary overwrites of unmodified files rather than as conflicts. `conceptual-workflows-init-reconcile` holds why.

## The Same Flow Without a Terminal

Every prompt's effect is a keyword parameter on `plan_init`, and `plan_init` reports which conditional prompts a given plan justifies. The CLI asks; the planning function does not. A Python caller reaches the identical behaviour by passing the parameters, which is what keeps the interactive path from being a second implementation (`decisions-011-api-parity-with-cli`).
