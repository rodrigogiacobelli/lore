"""Holistic CRUD sweep for ``lore.codex`` — G16 Red.

Plan: ``transient-public-api-facade-plan`` §G16.
Amendment: ``transient-public-api-facade-create-stdz`` Sections A1, A6 +
Section B (Codex row) + Section F G16 step-list + Open Item 14 /
F-CODEX-FLIP-SCOPE.

Codex stays READ-ONLY (no create/update/delete CRUD per ADR gap;
amendment Section B explicit out-of-scope). This sweep is the first-arg
flip + ``scan_codex`` → ``list_codex`` rename across every callable.

Pins:

* ``scan_codex`` renamed to ``list_codex`` per audit Pattern 1; dropped
  from facade ``__all__``; ``list_codex`` added.
* First-arg flip on EVERY callable: ``read_document``, ``list_codex``,
  ``search_documents``, ``map_documents``, ``chaos_documents`` take
  ``project_root: Path`` first.
* ``chaos_documents`` first arg name was ``project_root`` already
  (verified codex.py:314); the test still asserts the contract so a
  regression that renames it would surface.

Red phase — every test below MUST fail until G16 Green lands.
"""

from __future__ import annotations

import inspect
import textwrap

import pytest

import lore.codex as _c_mod
from lore import api


# ---------------------------------------------------------------------------
# Fixture — project root with .lore/codex/ + one minimal doc.
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path):
    codex = tmp_path / ".lore" / "codex"
    codex.mkdir(parents=True)
    (codex / "alpha.md").write_text(
        textwrap.dedent(
            """\
            ---
            id: alpha
            title: Alpha
            summary: First doc.
            ---
            # body
            """
        )
    )
    (codex / "beta.md").write_text(
        textwrap.dedent(
            """\
            ---
            id: beta
            title: Beta
            summary: Second doc.
            related:
              - alpha
            ---
            # body
            """
        )
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Facade __all__ — scan_codex dropped; list_codex present.
# ---------------------------------------------------------------------------


class TestFacadeAllShape:
    def test_scan_codex_not_in_api_all(self):
        assert "scan_codex" not in api.__all__, (
            "G16: scan_codex renamed to list_codex."
        )

    def test_scan_codex_import_raises(self):
        with pytest.raises(ImportError):
            from lore.api import scan_codex  # noqa: F401

    def test_list_codex_in_api_all(self):
        assert "list_codex" in api.__all__

    def test_list_codex_identity_reexport(self):
        assert api.list_codex is _c_mod.list_codex


# ---------------------------------------------------------------------------
# Signatures — project_root first; codex_dir gone.
# ---------------------------------------------------------------------------


class TestCodexSignaturesUseProjectRoot:
    @pytest.mark.parametrize(
        "fn_name",
        (
            "read_document",
            "list_codex",
            "search_documents",
            "map_documents",
            "chaos_documents",
        ),
    )
    def test_first_positional_named_project_root(self, fn_name):
        fn = getattr(_c_mod, fn_name)
        params = list(inspect.signature(fn).parameters.values())
        assert params and params[0].name == "project_root", (
            f"{fn_name} first positional must be 'project_root' "
            f"(got {params[0].name if params else 'none'!r}); "
            "amendment Section B Codex row."
        )

    @pytest.mark.parametrize(
        "fn_name",
        (
            "read_document",
            "list_codex",
            "search_documents",
            "map_documents",
            "chaos_documents",
        ),
    )
    def test_no_codex_dir_parameter(self, fn_name):
        fn = getattr(_c_mod, fn_name)
        assert "codex_dir" not in inspect.signature(fn).parameters

    def test_module_has_no_scan_codex_symbol(self):
        assert not hasattr(_c_mod, "scan_codex"), (
            "scan_codex must be removed in favour of list_codex."
        )


# ---------------------------------------------------------------------------
# Behaviour — each callable accepts project_root and returns expected shape.
# ---------------------------------------------------------------------------


class TestCodexCallablesAcceptProjectRoot:
    def test_list_codex_takes_project_root(self, project_root):
        records = _c_mod.list_codex(project_root)
        assert isinstance(records, list)
        ids = {r["id"] for r in records}
        assert {"alpha", "beta"} <= ids

    def test_list_codex_empty_when_dir_absent(self, tmp_path):
        # no .lore/codex
        assert _c_mod.list_codex(tmp_path) == []

    def test_read_document_takes_project_root(self, project_root):
        result = _c_mod.read_document(project_root, "alpha")
        assert isinstance(result, dict)
        assert result["id"] == "alpha"

    def test_read_document_missing_returns_none(self, project_root):
        assert _c_mod.read_document(project_root, "nope") is None

    def test_search_documents_takes_project_root(self, project_root):
        results = _c_mod.search_documents(project_root, "alpha")
        assert isinstance(results, list)
        assert any(r["id"] == "alpha" for r in results)

    def test_map_documents_takes_project_root(self, project_root):
        results = _c_mod.map_documents(project_root, "alpha")
        assert isinstance(results, list)

    def test_map_documents_missing_seed_returns_none(self, project_root):
        assert _c_mod.map_documents(project_root, "nope") is None

    def test_chaos_documents_takes_project_root(self, project_root):
        results = _c_mod.chaos_documents(project_root, "alpha", 50)
        # alpha is reachable from itself only with related=[]; expect a list
        # (None only if start_id missing).
        assert results is not None
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# F-CODEX-FLIP-SCOPE — grep helper: zero `codex_dir(` call sites remain
# inside lore.codex internals (caller-facing surface should derive
# codex_dir from project_root itself).
#
# The sanity test reads the module source: no parameter named ``codex_dir``
# should appear in any public callable's signature.
# ---------------------------------------------------------------------------


class TestCodexFlipScopeGuard:
    def test_no_public_callable_uses_codex_dir_param(self):
        public = [
            name
            for name in dir(_c_mod)
            if not name.startswith("_")
            and callable(getattr(_c_mod, name))
            and getattr(getattr(_c_mod, name), "__module__", "")
            == "lore.codex"
        ]
        offenders = []
        for name in public:
            try:
                params = inspect.signature(getattr(_c_mod, name)).parameters
            except (TypeError, ValueError):
                continue
            if "codex_dir" in params:
                offenders.append(name)
        assert not offenders, (
            f"Public codex callables still accept codex_dir: {offenders}. "
            "Amendment Section B Codex row + F-CODEX-FLIP-SCOPE require flip "
            "to project_root."
        )
