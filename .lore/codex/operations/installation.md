---
id: ops-installation
title: Installation
summary: How to install Lore as an end-user CLI tool (uv tool, pipx) and how to set
  up a development environment, build a distributable package, and verify the install.
  See ops-publish-pypi for the release runbook.
binds:
- pyproject.toml
related:
- ops-git-workflow
- ops-publish-pypi
- decisions-002-package-name
- decisions-013-toml-for-config-yaml-for-glossary
- conceptual-workflows-lore-init
- conceptual-workflows-init-interactive
- conceptual-workflows-init-reconcile
- tech-overview
---

# Installation

## Install as a CLI Tool

The recommended way to install Lore is as an isolated CLI tool using `uv tool` or `pipx`. This puts the `lore` command on your PATH without polluting any project environment.

### From source (local clone)

```bash
git clone https://github.com/rodrigogiacobelli/lore.git
uv tool install ./lore
```

### From a git URL

```bash
uv tool install git+https://github.com/rodrigogiacobelli/lore.git
```

### From PyPI (once published)

The authoritative PyPI package name is `lore-agent-task-manager` (as declared in `pyproject.toml`).

```bash
uv tool install lore-agent-task-manager
```

### Using pipx instead of uv

If you prefer [pipx](https://pipx.pypa.io/):

```bash
pipx install ./lore                    # from local clone
pipx install lore-agent-task-manager   # from PyPI
```

### Upgrading

```bash
uv tool upgrade lore-agent-task-manager
```

When installing from a local clone after making changes, use `--force --reinstall` so uv rebuilds the wheel from source instead of using a cached copy:

```bash
uv tool install . --force --reinstall
```

**Re-run `lore init` in each project after upgrading.** The package upgrade changes what Lore ships; `lore init` is what brings a project into line with it — installing skills the release added, removing the ones it retired, and refreshing each agent's instruction block. It prompts only for what it cannot answer from `.lore/config.toml`, shows the full change set before writing anything, and never replaces a file the project edited without asking.

```bash
cd your-project
lore init --dry-run     # read the plan first
lore init
```

`conceptual-workflows-init-reconcile` holds what happens to a skill the project edited, and `conceptual-workflows-init-interactive` holds the prompts and their flag equivalents.

### Uninstalling

```bash
uv tool uninstall lore-agent-task-manager
```

## Development Setup

For working on Lore itself, use an editable install inside the project venv:

```bash
git clone https://github.com/rodrigogiacobelli/lore.git
cd lore
uv sync
```

This installs the package in editable mode with dev dependencies (pytest, ruff, mypy). Commands must be run through the venv:

```bash
uv run lore --version
uv run pytest
```

### Type Checking

`mypy` is available as a dev dependency. Run it to type-check `lore.models` and the rest
of the package:

```bash
uv run mypy src/lore/
```

The `[tool.mypy]` configuration in `pyproject.toml` enables strict settings
(`disallow_untyped_defs`, `no_implicit_optional`, etc.). The `py.typed` PEP 561 marker
at `src/lore/py.typed` signals to mypy and pyright that `lore` ships inline type
annotations — downstream consumers (like Realm) get type-checker coverage automatically.

## Building a Distributable Package

To build a wheel and sdist:

```bash
uv build
```

This creates a `.whl` and `.tar.gz` in the `dist/` directory.

Install the built wheel on any machine:

```bash
uv tool install dist/lore_agent_task_manager-*.whl
```

## Publishing to PyPI

See `ops-publish-pypi` for the full release runbook (version bump, changelog, tag, build, upload, verify).

## Verifying the Install

```bash
lore --version
lore --help
```

## Requirements

- **Python 3.11+** — stdlib `tomllib` reads `.lore/config.toml` (decisions-013-toml-for-config-yaml-for-glossary)
- **SQLite 3.35+** (ships with Python 3.11+; uses `RETURNING` clause)
- No native dependencies — pure Python. Four required runtime dependencies, no extras and nothing optional: `click>=8.3,<9.0`, `PyYAML`, `jsonschema>=4.18`, `questionary>=2.0,<3.0`.
