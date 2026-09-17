"""E2E parity tests for the codex index's public API surface.

Spec: codex-index-spec — Part 4 "E2E", the `tests/e2e/test_api_parity_index.py`
rows. ADR-011: every CLI capability is reachable from `lore.api` with the same
result, and a Python caller meets the same message a terminal user does — the
CLI adds no wording of its own.
"""

from __future__ import annotations

import json

import pytest

from lore.cli import main

W4_NOT_AUTHORED = (
    "no index authored for this project. Run the update-index skill to author it."
)


def test_build_index_equals_the_cli_envelope(w1_project, runner):
    """The `--json` envelope is `build_index`'s dict and nothing else."""
    from lore.api import build_index

    res = runner.invoke(main, ["--json", "index", "build"])

    assert res.exit_code == 0, res.output
    assert build_index(w1_project) == json.loads(res.stdout)


def test_search_index_equals_the_cli_envelope(w1_project, runner):
    """`search_index` returns the list the envelope wraps under `clusters`."""
    from lore.api import search_index

    res = runner.invoke(main, ["--json", "index", "search", "beta"])

    assert res.exit_code == 0, res.output
    assert search_index(w1_project, "beta") == json.loads(res.stdout)["clusters"]


def test_the_api_raises_where_the_cli_exits(index_project):
    """ADR-011 — the refusal is the core's, and it carries the W4 wording."""
    from lore.api import CodexIndexNotAuthoredError, search_index

    with pytest.raises(CodexIndexNotAuthoredError) as caught:
        search_index(index_project, "beta")

    assert str(caught.value) == W4_NOT_AUTHORED


def test_the_exception_types_are_exported():
    """ADR-010 — the four names are the facade's, and the hierarchy is stated."""
    from lore.api import (
        CodexIndexError,
        CodexIndexNotAuthoredError,
        build_index,
        search_index,
    )

    assert callable(build_index)
    assert callable(search_index)
    assert issubclass(CodexIndexNotAuthoredError, CodexIndexError)
    assert issubclass(CodexIndexError, ValueError)


def test_the_four_names_are_the_identity_of_the_objects_in_lore_index():
    """`standards-facade` — a re-export, never a copy or a wrapper."""
    from lore import api, index

    assert api.build_index is index.build_index
    assert api.search_index is index.search_index
    assert api.CodexIndexError is index.CodexIndexError
    assert api.CodexIndexNotAuthoredError is index.CodexIndexNotAuthoredError
