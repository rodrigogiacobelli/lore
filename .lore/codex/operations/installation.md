---
id: ops-installation
title: Installation
summary: How to install Lore as an end-user CLI tool (uv tool, pipx) and how to set up a development environment, build a distributable package, publish to PyPI, and verify the install.
related: ["ops-git-workflow", "decisions-002-package-name"]
stability: stable
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

When installing from a local clone after making changes, use `--force --reinstall` to ensure uv rebuilds the wheel from source instead of using a cached copy:

```bash
uv tool install . --force --reinstall
```

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

```bash
uv build
uv publish
```

You'll need a [PyPI account](https://pypi.org/account/register/) and API token. For test runs, use [TestPyPI](https://test.pypi.org/) first:

```bash
uv publish --publish-url https://test.pypi.org/legacy/
uv tool install --index-url https://test.pypi.org/simple/ lore-agent-task-manager
```

## Verifying the Install

```bash
lore --version
lore --help
```

## Requirements

- **Python 3.10+** (uses `match` statements and modern type hints)
- **SQLite 3.35+** (ships with Python 3.10+; uses `RETURNING` clause)
- No native dependencies — pure Python with Click and PyYAML
