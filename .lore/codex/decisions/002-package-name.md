---
id: decisions-002-package-name
title: "PyPI package name: lore-agent-task-manager"
summary: "The canonical PyPI package name is lore-agent-task-manager. The earlier working name lore-taskman has been retired and all references updated."
related: ["decisions-010-public-api-stability", "ops-installation"]
stability: stable
---

# ADR 002 — PyPI Package Name

## Context

Two names appeared in the documentation for the Lore PyPI package:

- `lore-taskman` — used in older spec-layer documents (`docs/spec.md`, user stories US-1 and US-29). The spec carried a provisional comment indicating the name was subject to PyPI availability.
- `lore-agent-task-manager` — used in `docs/installation.md` and in `pyproject.toml`.

The migration audit identified this as a confirmed gap. Human confirmation was sought and received.

## Decision

The canonical PyPI package name is:

```
lore-agent-task-manager
```

`pyproject.toml` is the authoritative source for the published package name. All references to `lore-taskman` have been updated to `lore-agent-task-manager`.

## Rationale

- `pyproject.toml` is the build configuration used to publish the package. Whatever name is in that file is what gets uploaded to PyPI. It is the most operationally authoritative source.
- `installation.md` was already consistent with `pyproject.toml`, reinforcing that `lore-agent-task-manager` was the current intent.
- `lore-taskman` appeared only in older spec-layer documents and was a working name that was superseded.

## Alternatives Rejected

**`lore-taskman`** — a shorter name, but already superseded in the build configuration. Adopting it would have required updating `pyproject.toml` and `installation.md` against the direction of travel.
