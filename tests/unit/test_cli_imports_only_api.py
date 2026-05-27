"""Invariant: `src/lore/cli.py` imports ONLY from `lore.api`.

ADR-010 + ADR-011 + Tech Spec §1 lock the public surface as
``lore.api.__all__``. Every ``lore.<X>`` submodule below the facade is
INTERNAL. The CLI is a consumer like Realm — it MUST go through the
facade.

This Red test enforces the rule via AST inspection of ``src/lore/cli.py``:

- Allowed forms:
    * ``from lore import api``
    * ``from lore.api import <names>``
    * ``import lore.api``
    * Any non-``lore`` import (stdlib, third-party).
- Forbidden forms (Red today — to be flipped Green in m-778e):
    * ``from lore.<other_module> import …`` (knight, artifact, root, db, etc.)
    * ``from lore import <other_module>`` (paths, validators, graph, etc.)
    * ``import lore.<other_module>``

NOTE: ``from lore import __version__`` is also disallowed — ``__version__``
is exported through ``lore.api`` or stays out of CLI altogether (CLI prints
it from ``lore.api.__version__`` if exposed there, otherwise via
``importlib.metadata``). Spec §1 lists no exception; this test enforces the
strict rule.

Source spec docs:
  lore codex show transient-public-api-facade-tech-spec
  lore codex show decisions-010-public-api-stability
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


CLI_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "lore" / "cli.py"
)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _collect_lore_imports(tree: ast.AST) -> list[tuple[str, ast.stmt]]:
    """Return every (dotted-name, node) for imports that touch the ``lore`` pkg.

    Captures three syntactic shapes:
      * ``import lore`` / ``import lore.foo`` / ``import lore.foo as bar``
        → emits ``"lore"`` / ``"lore.foo"`` per alias.
      * ``from lore import x`` / ``from lore import x as y``
        → emits ``"lore.x"`` per imported name.
      * ``from lore.foo import x`` → emits ``"lore.foo"`` (one entry, since
        the constraint is on the SOURCE module, not the names imported).
    """
    out: list[tuple[str, ast.stmt]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "lore" or alias.name.startswith("lore."):
                    out.append((alias.name, node))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "lore":
                # `from lore import X[, Y]` — record one entry per name
                # so messages can pinpoint the offender.
                for alias in node.names:
                    out.append((f"lore.{alias.name}", node))
            elif mod == "lore.api":
                out.append(("lore.api", node))
            elif mod.startswith("lore."):
                out.append((mod, node))
    return out


def _is_allowed_lore_import(dotted: str) -> bool:
    """Allow only ``lore.api`` family. Reject every other ``lore.<X>``.

    Concretely:
      * ``lore.api``               — allowed
      * ``lore.api.<sub>``         — allowed (defensive; api has no submodules
                                     today but a future split shouldn't break
                                     this test)
      * ``lore``                   — disallowed (bare-package access leaks
                                     submodules)
      * ``lore.<anything-else>``   — disallowed
    """
    if dotted == "lore.api":
        return True
    if dotted.startswith("lore.api."):
        return True
    return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCliModuleFileExists:
    """Sanity — the file we're inspecting is on disk."""

    def test_cli_source_file_exists(self):
        assert CLI_MODULE_PATH.is_file(), (
            f"Expected CLI module at {CLI_MODULE_PATH}; not found"
        )


class TestCliImportsOnlyFromApi:
    """Every ``lore.*`` import in ``cli.py`` must resolve to ``lore.api``."""

    @pytest.fixture(scope="class")
    def cli_lore_imports(self) -> list[tuple[str, ast.stmt]]:
        tree = ast.parse(CLI_MODULE_PATH.read_text())
        return _collect_lore_imports(tree)

    def test_cli_has_at_least_one_lore_api_import(self, cli_lore_imports):
        """CLI must consume the facade — bare CLI with no api import is wrong."""
        api_imports = [d for d, _ in cli_lore_imports if _is_allowed_lore_import(d)]
        assert api_imports, (
            "src/lore/cli.py imports nothing from lore.api — facade unused"
        )

    def test_cli_imports_only_from_lore_api(self, cli_lore_imports):
        """No ``from lore.<X> import …`` outside ``lore.api``."""
        offenders = [
            (dotted, getattr(node, "lineno", "?"))
            for dotted, node in cli_lore_imports
            if not _is_allowed_lore_import(dotted)
        ]
        assert offenders == [], (
            "src/lore/cli.py imports from non-facade lore modules. "
            "Per Tech Spec §1 the CLI is a facade consumer — replace each "
            "import with `from lore.api import …`.\n"
            f"Offenders (dotted name, lineno): {offenders}"
        )


@pytest.mark.parametrize(
    "forbidden_module",
    [
        "lore.knight",
        "lore.artifact",
        "lore.doctrine",
        "lore.watcher",
        "lore.codex",
        "lore.glossary",
        "lore.impacts",
        "lore.health",
        "lore.priority",
        "lore.db",
        "lore.models",
        "lore.root",
        "lore.config",
        "lore.schemas",
        "lore.validators",
        "lore.frontmatter",
        "lore.graph",
        "lore.paths",
        "lore.init",
        "lore.oracle",
    ],
)
def test_cli_does_not_import_internal_module(forbidden_module: str):
    """No internal ``lore.<X>`` may be imported by ``cli.py`` — pinpointed.

    Parametrised so failures pinpoint the exact internal module still leaking.
    """
    tree = ast.parse(CLI_MODULE_PATH.read_text())
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == forbidden_module:
                    hits.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.module == forbidden_module:
                hits.append(node.lineno)
            elif node.module == "lore":
                tail = forbidden_module.rsplit(".", 1)[-1]
                for alias in node.names:
                    if alias.name == tail:
                        hits.append(node.lineno)
    assert hits == [], (
        f"src/lore/cli.py imports internal module {forbidden_module} "
        f"at line(s) {hits}. Replace with `from lore.api import …`."
    )
