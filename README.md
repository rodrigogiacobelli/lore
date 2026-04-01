# Lore — Agent Task Manager

```
  _      ___  ___ ___
 | |    / _ \| _ \ __|
 | |__ | (_) |   / _|
 |____| \___/|_|_\___|
 Agent Task Manager
```

Lore was built entirely by AI agents. No code was written by hand. Every feature, test, refactor, and commit was executed by an AI worker operating under missions tracked in Lore itself. The human role was operator: writing requirements, reviewing output, unblocking missions, shipping releases.

That is not a gimmick. It is proof of concept. If you are running AI agents to build software, Lore is what gives them memory.

---

## The Problem

Running AI agents on real software projects surfaces two problems quickly.

**Agents lose track of work.** Agents are stateless. They do not know what has been done, what is blocked, or what to do next unless you tell them. Without shared state, agents repeat themselves, contradict each other, and stall. You end up babysitting instead of operating.

**Agents do not know your project.** Every new conversation, the agent has no memory of your architecture decisions, your coding standards, the choices you made last sprint. You re-explain the same things session after session. New features drift from old ones. Consistency erodes.

Lore solves both.

---

## What Lore Does

Lore is two systems in one tool.

**Task engine** — Quests, Missions, Doctrines, and Knights give agents structured state. An agent always knows what to work on, what it is blocked by, and how to behave. The orchestrator always knows what is done, what is in progress, and what is waiting.

**Project memory (Codex)** — A queryable knowledge graph of typed markdown documents living in `.lore/codex/`. Architecture decisions, conceptual guides, workflow standards, design records — all linked and searchable. Any agent can orient itself before acting. New features stay consistent with old ones. You stop repeating yourself.

Lore is **dumb infrastructure**. It stores state and answers queries. It does not orchestrate, spawn agents, or make decisions. All intelligence stays in the consuming orchestrator — Claude, Codex, Gemini, your own pipeline. Lore is the notepad with structure.

---

## Install

```bash
pip install lore-agent-task-manager
```

Or with uv:

```bash
uv pip install lore-agent-task-manager
```

Then initialize a project:

```bash
lore init
```

---

## Task Engine — Commands to Know

```bash
lore ready               # what should I work on next?
lore show <id>           # what is this quest or mission?
lore claim <id>          # I am working on this
lore done <id>           # finished
lore block <id> "reason" # stuck — here is why
```

Quests group related work. Missions are individual tasks. An orchestrator creates them; agents claim and close them.

```bash
lore new quest "Build authentication"
lore new mission "Design auth schema" -q <quest-id>
lore list          # open quests
lore list missions # open missions
```

Missions can depend on each other. `lore ready` only surfaces unblocked work — agents never pick up a task before its dependencies are done.

---

## Project Memory — Codex Commands

```bash
lore codex search "auth"          # find relevant documents
lore codex show <id>              # read one document (or many at once)
lore codex map <id> --depth 1     # traverse the graph from a document
lore codex list                   # see everything
```

The Codex is a graph of typed markdown documents. Documents link to each other via a `related` field. An agent reading a decision document can follow links to the conceptual guide, the workflow spec, and the schema definition — all in one traversal.

New agents orient using the Codex before doing anything else. This is how consistency survives across sessions, across agents, and across months of development.

---

## Core Vocabulary

| Term | What it is |
|---|---|
| **Quest** | A body of work — a feature, bug fix, refactor, or spike |
| **Mission** | One task inside a Quest. The unit an agent picks up and closes. |
| **Knight** | An agent persona — a markdown file telling a worker *how* to behave |
| **Doctrine** | A workflow template — YAML describing the steps and ordering of a body of work |
| **Artifact** | A reusable document template agents scaffold new files from |
| **Codex** | The project knowledge graph — decisions, concepts, standards |

---

## How It Fits Together

Lore is the foundation layer of the Camelot system:

```
Citadel  →  Realm  →  Lore
(UI)         (AI orchestrator)   (task engine — you are here)
```

- **Lore** stores all state. Zero dependencies on Realm or Citadel.
- **Realm** is the AI orchestration layer. It consumes Lore to run agents automatically.
- **Citadel** is the human-facing UI for monitoring and control.

Any orchestrator can consume Lore. The Camelot stack is one way to use it — not the only way.

---

## Python API

Realm and other orchestrators consume Lore via Python import rather than CLI:

```python
from lore.models import Quest, Mission, MissionStatus, Doctrine, Knight
```

`lore.models.__all__` defines the stable public API surface. Every name in `__all__` is a typed, immutable dataclass with full semver stability guarantees. Anything not in `__all__` is an internal detail.

Every CLI command is backed by a Python function. The CLI is a thin wrapper — the real interface is the Python modules underneath.

---

## Philosophy

Three principles drive every design decision in Lore:

**Dumb infrastructure.** Lore stores data and answers queries — nothing more. No hidden state transitions, no autonomous decisions. Agents can rely on Lore doing exactly what they ask. All intelligence lives in the orchestrator.

**Short commands.** Most operations are `lore [verb]` or `lore [verb] [id]`. No flags required for common operations. Every CLI invocation costs context window — commands return everything needed in one call.

**State is authoritative.** If Lore says a Mission is `blocked`, it is `blocked`. No other system maintains a parallel copy. Agents trust the state they read.

---

## Built by AI. Operated by a Human.

Every line of code in Lore was written by an AI agent. The human role throughout was: write a requirement, dispatch a mission, review the result, mark it done.

The requirements were tracked in Lore. The agents oriented using the Codex. The workflow followed Doctrines. The personas were defined by Knights.

Lore built itself using itself. That is what it is designed to let you do.

---

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended)

## Development

```bash
uv sync
uv run pytest
```
