---
id: example-ops-deployment-dev
title: Development Environment
summary: Step-by-step guide to running the task app locally from a fresh clone. Prerequisites,
  install, database initialisation, run, and verify.
---

# Development Environment

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | ≥ 3.11 | [python.org](https://www.python.org/downloads/) or `pyenv install 3.11` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Git | any | pre-installed on most systems |
| _additional tool_ | _version_ | _install command or link_ |

_Remove or add rows as needed. If the project uses Docker for local dev, add it here._

## Clone and Install

```bash
git clone _repository URL_
cd taskapp
uv sync
```

This installs all dependencies (including dev dependencies) into a project-local virtual environment and creates `uv.lock` if it does not exist.

## Environment Variables

The task app reads configuration from environment variables. Copy the example file and fill in values:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|----------|-------------|---------|
| `TASKAPP_DB_PATH` | Path to the SQLite database file | `~/.taskapp/taskapp.db` |
| _additional variable_ | _description_ | _default or "(required)"_ |

_If there are no required environment variables beyond the default, note that explicitly._

## Database Initialisation

The database and migrations run automatically on first use. There is no manual migration step for development. To verify:

```bash
uv run taskapp task list
```

If the database file does not exist, it is created at `TASKAPP_DB_PATH` and all migrations are applied.

## Running the Application

```bash
uv run taskapp --help
```

Or install the tool into the local environment so `taskapp` is on PATH:

```bash
uv tool install --editable .
taskapp --help
```

_Choose the approach that matches this project's workflow._

## Common Commands

| Command | Description |
|---------|-------------|
| `uv run taskapp task list` | List all open tasks |
| `uv run pytest` | Run the test suite |
| `uv run pytest -x` | Run tests and stop on first failure |
| `uv run pytest --tb=short` | Run tests with short tracebacks |
| `rm ~/.taskapp/taskapp.db` | Reset the local database |
| `uv sync` | Sync dependencies after `pyproject.toml` changes |

## Troubleshooting

### `command not found: taskapp`

**Symptom:** Running `taskapp` after `uv tool install` returns "command not found".

**Cause:** The uv tools directory (`~/.local/bin`) is not on your PATH.

**Fix:** Add `export PATH="$HOME/.local/bin:$PATH"` to your shell profile and reload it.

### Database is not created

**Symptom:** `uv run taskapp task list` errors with "unable to open database file".

**Cause:** The directory containing the database file does not exist.

**Fix:** Create the directory: `mkdir -p ~/.taskapp` or set `TASKAPP_DB_PATH` to a writable location.

### _Additional common problem_

_Symptom, cause, and fix._
