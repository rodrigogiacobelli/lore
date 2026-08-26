---
id: tech-arch-api-facade
title: API Facade Module
summary: The src/lore/api.py module — a pure re-export facade with zero def or class
  statements. Sole supported import surface for Lore consumers per ADR-010. Three-section
  __all__ layout (types/enums, operational callables, no module-level definitions),
  plus a separate block of leading-underscore namespace aliases used only by cli.py
  and unit-test monkeypatches. The underscore prefix keeps CLI re-exports out of
  dir(lore.api) so they are not part of the public surface.
binds:
- src/lore/api.py
related:
- decisions-010-public-api-stability
- decisions-011-api-parity-with-cli
- standards-facade
- standards-public-api-stability
- ref-lore_api-core
- tech-arch-source-layout
- conceptual-workflows-lore-init
---

# API Facade Module

`src/lore/api.py` is the public API facade for `lore-agent-task-manager`. It is the **only** import path consumers (Realm, Citadel, third parties, the future Lore Server) are permitted to use. Any other import — `from lore.db import ...`, `from lore.knight import ...`, `from lore.codex import ...` — is a consumer bug and may break without notice between any two releases.

## Pure Re-Export Pattern

`api.py` contains **zero** `def` or `class` statements. Every name in `__all__` is imported from an internal module and re-exported verbatim. There is no business logic in the facade — it is a flat name-routing layer.

Consequences:

- **Identity preserved.** `lore.api.create_quest is lore.db.create_quest` (and likewise for every other re-export). Tests, monkeypatches, and `inspect`-based tooling all see the same function object.
- **No behavioural drift.** The facade cannot diverge from the operational modules behind it because it adds no behaviour. ADR-011's CLI/Python parity is enforced at the operational layer; the facade exposes that surface.
- **Refactor freedom below the line.** Splitting `db.py`, renaming `codex.py`, or merging modules requires only that `api.py` keeps re-exporting the same names. No public API change. No semver bump.

## Three-Section `__all__` Layout

The `__all__` list in `api.py` is laid out in three named sections in a fixed order:

1. **Types & enums** — frozen dataclasses and `StrEnum` subclasses sourced from `lore.models`, plus exception classes (`DoctrineError`, `GlossaryError`, `ProjectNotFoundError`, `ConflictingDepthFlags`, `ImpactsError`) and the read-only `Config` dataclass.

   A sub-block marked `# --- Operational dataclasses (sourced from their owning modules) ---` sits inside this section for result types that mirror no stored record and therefore live in the module that produces them rather than in `lore.models`: `HealthIssue` and `HealthReport` from `lore.health`, `SchemaIssue` from `lore.schemas`, `CodeBinding` and `ImpactsResult` from `lore.impacts`, and `AccessMode`, `FileAction`, `AgentTarget`, `PlannedFile`, `InitAnswers`, `InitPlan` and `InitResult` from `lore.initplan`. `lore.models` stays the entity-record index — every member there mirrors a DB row or an on-disk file and carries a `from_row` / `from_dict` hydrator.

2. **Project root** — `find_project_root` (from `lore.root`).

3. **Operational callables** — every CRUD, lifecycle, traversal, validator, schema, health, and reporting function consumers may call. Grouped by domain (validators → db quest CRUD → db mission CRUD → db status transitions → db dependencies → db board → db dashboard/stats → db envelopes → priority → knight → doctrine → artifact → watcher → codex → glossary → impacts → health → schemas → init/reports/config, where the init block holds `plan_init`, `apply_init` and `run_init`) for diff legibility, not import order.

Each section is bounded by a comment marker. New exports go at the end of their domain block, never sprinkled across sections — this keeps `git diff` against `__all__` reviewable in one screen and ensures consumers reading the source can find names by category.

The canonical contents of `__all__` are pinned in `standards-public-api-stability`. `ref-lore_api-core` covers the cross-cutting contracts that callers must honour when using those names.

## Underscore-Aliased Namespace Re-Exports

Below the `__all__` list, `api.py` re-exports a set of internal submodules under leading-underscore aliases:

```python
from lore import paths as _paths
from lore import graph as _graph
from lore import knight as _knight
from lore import validators as _validators
from lore import watcher as _watcher
from lore import glossary as _glossary
from lore import impacts as _impacts
from lore import doctrine as _doctrine
from lore import health as _health
from lore import prompts as _prompts
from lore import agents as _agents
from lore import skills as _skills
from lore import __version__ as _lore_version
from lore.knight import _validate_frontmatter as _validate_frontmatter
```

Each line carries a `# noqa: F401` because ruff cannot infer re-export intent for renamed imports (only same-name `as` aliases count as PEP 484 explicit re-exports).

`_agents` and `_skills` are needed at `cli.py` **import** time, because `click.Choice` evaluates its set when the decorator runs. `_prompts` must not pull `questionary` into that import: `prompts.py` imports `questionary` lazily inside each function, so `import lore.api` stays cheap for every other command — pulling `prompt_toolkit` into every `lore ready` would cost per-invocation time for no benefit (`decisions-001-dumb-infrastructure`).

**Why they exist:** `cli.py` is a facade consumer too. It needs `paths.knights_dir(root)` style access for filesystem paths and `_validate_frontmatter` for create-time validation, but ADR-010 forbids it from reaching into `lore.<module>` directly — that would normalise the same breach external consumers are banned from. The underscore-aliased re-exports give the CLI (and only the CLI) a stable internal handle.

**Why the underscore prefix:** Names beginning with `_` are excluded from `dir(lore.api)` and from `from lore.api import *` semantics. Per Spec §1's "no public name outside `__all__`" rule, the underscore prefix is the mechanical guarantee that these aliases are not part of the public surface. Consumers that read `dir(lore.api)` to enumerate the API will not see them.

**Secondary use — monkeypatch anchors:** Unit tests patch `lore.api._paths.knights_dir` or `lore.api._knight._validate_frontmatter` rather than reaching into `lore.paths` or `lore.knight` directly. The facade boundary the ADR-010 contract enforces is honoured in tests as well as in production code.

## Verifying the Surface

- `lore.api.__all__` is the boundary. Names outside it (even importable ones like `_paths`) are internal.
- `from lore.api import *` imports only the names in `__all__`. Underscore aliases are excluded by definition.
- `dir(lore.api)` lists `__all__` plus the dunder names; underscore aliases are absent.
- `lore health` does not validate the facade's structure. The pure-re-export and underscore-prefix invariants are enforced by code review and the test suite (parity tests against `__all__`).
