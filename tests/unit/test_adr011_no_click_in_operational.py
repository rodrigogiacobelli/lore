"""ADR-011 invariant — operational modules MUST NOT import click.

Plan: transient-public-api-facade-plan §G2 (and later chunks G3+ extend the
covered module list).
Anchor: decisions-011-public-api-stability (ADR-011 — facade boundary; only
``cli.py`` may import click).

This file enforces the grep-equivalent invariant from G2 acceptance:

    grep -l "^import click\\|^from click" src/lore/<module>.py == empty

G2 lands the invariant for ``knight`` and ``artifact`` (the two
``_validate_frontmatter`` raise sites flipped to ``ValueError``). Later
chunks extend the parametrize list as each module is hoisted clean. The
end-state ADR-011 target is the full list:

    knight, artifact, doctrine, watcher, db, codex, glossary, impacts,
    health, validators, frontmatter, priority, schemas, init, oracle

Red phase — these tests MUST fail before G2 Green flips the raises.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


SRC_LORE = Path(__file__).resolve().parents[2] / "src" / "lore"


# G2-scope modules — flipped in this chunk.
G2_MODULES = ("knight", "artifact")

# G15.5-scope modules — `DoctrineError` removed, doctrine module raises
# `ValueError`. Adds `doctrine` to the no-click invariant.
G15_5_MODULES = ("doctrine",)

# G16-scope modules — watcher's ``_validate_yaml`` raise type flips from
# ``click.ClickException`` to ``ValueError`` (amendment Section E
# validation behaviour changes). Adds ``watcher`` to the no-click
# invariant. Red-phase: every test in this scope MUST fail until G16
# Green hoists the click import out of ``lore.watcher``.
G16_MODULES = ("watcher",)


def _module_path(name: str) -> Path:
    """Return the file path for a top-level ``lore.<name>`` module."""
    return SRC_LORE / f"{name}.py"


@pytest.mark.parametrize("module_name", G2_MODULES)
def test_g2_module_source_has_no_click_text_reference(module_name: str) -> None:
    """Grep-equivalent: module source contains no 'click' substring (G2 scope)."""
    path = _module_path(module_name)
    text = path.read_text()
    assert "click" not in text, (
        f"src/lore/{module_name}.py still references 'click' — "
        "ADR-011 forbids click in operational modules."
    )


@pytest.mark.parametrize("module_name", G2_MODULES)
def test_g2_module_ast_imports_no_click(module_name: str) -> None:
    """AST check: module imports no ``click`` name (G2 scope — knight + artifact)."""
    path = _module_path(module_name)
    tree = ast.parse(path.read_text(), filename=str(path))
    bad_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "click" or alias.name.startswith("click."):
                    bad_imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "click" or (node.module or "").startswith("click."):
                bad_imports.append(f"from {node.module} import ...")
    assert not bad_imports, (
        f"src/lore/{module_name}.py imports click: {bad_imports}. "
        "ADR-011 forbids click in operational modules."
    )


# ---------------------------------------------------------------------------
# G15.5 scope — doctrine module joins the no-click invariant.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module_name", G15_5_MODULES)
def test_g15_5_module_source_has_no_click_text_reference(module_name: str) -> None:
    """Grep-equivalent: module source contains no 'click' substring (G15.5 scope)."""
    path = _module_path(module_name)
    text = path.read_text()
    assert "click" not in text, (
        f"src/lore/{module_name}.py still references 'click' — "
        "ADR-011 forbids click in operational modules."
    )


@pytest.mark.parametrize("module_name", G15_5_MODULES)
def test_g15_5_module_ast_imports_no_click(module_name: str) -> None:
    """AST check: module imports no ``click`` name (G15.5 scope — doctrine)."""
    path = _module_path(module_name)
    tree = ast.parse(path.read_text(), filename=str(path))
    bad_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "click" or alias.name.startswith("click."):
                    bad_imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "click" or (node.module or "").startswith("click."):
                bad_imports.append(f"from {node.module} import ...")
    assert not bad_imports, (
        f"src/lore/{module_name}.py imports click: {bad_imports}. "
        "ADR-011 forbids click in operational modules."
    )


@pytest.mark.parametrize("module_name", G15_5_MODULES)
def test_g15_5_module_has_no_doctrine_error_class(module_name: str) -> None:
    """``DoctrineError`` class symbol absent post-flip (G15.5 scope — doctrine)."""
    path = _module_path(module_name)
    text = path.read_text()
    assert "DoctrineError" not in text, (
        f"src/lore/{module_name}.py still references DoctrineError — "
        "G15.5 mandates removal of the Click-subclass exception."
    )


# ---------------------------------------------------------------------------
# G16 scope — watcher module joins the no-click invariant.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module_name", G16_MODULES)
def test_g16_module_source_has_no_click_text_reference(module_name: str) -> None:
    """Grep-equivalent: module source contains no 'click' substring (G16 scope)."""
    path = _module_path(module_name)
    text = path.read_text()
    assert "click" not in text, (
        f"src/lore/{module_name}.py still references 'click' — "
        "ADR-011 + G16 amendment forbid click in operational modules."
    )


@pytest.mark.parametrize("module_name", G16_MODULES)
def test_g16_module_ast_imports_no_click(module_name: str) -> None:
    """AST check: module imports no ``click`` name (G16 scope — watcher)."""
    path = _module_path(module_name)
    tree = ast.parse(path.read_text(), filename=str(path))
    bad_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "click" or alias.name.startswith("click."):
                    bad_imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "click" or (node.module or "").startswith("click."):
                bad_imports.append(f"from {node.module} import ...")
    assert not bad_imports, (
        f"src/lore/{module_name}.py imports click: {bad_imports}. "
        "ADR-011 + G16 amendment forbid click in operational modules."
    )
