"""Red-phase tests for US-008 — Python API surface re-exported from ``lore.models``.

Workflow: conceptual-workflows-impacts.
Tech Spec: lore-impacts-tech-spec § "Python API (FR-15)".
Story: lore-impacts-us-008.
Standards: ref-lore_api-core (``lore.models.__all__`` is the public-API contract;
``project_root`` is the keyword parameter convention, NOT ``codex_dir``).

Every test here must FAIL until Green wires the five symbols
(``impacts``, ``ImpactsResult``, ``CodexBinding``, ``CodeBinding``,
``ImpactsError``) into ``lore.models`` and appends each to ``__all__``.

This file deliberately exercises ``lore.models`` only — NOT ``lore.impacts``
directly. The point of these tests is the façade re-export (standards-facade,
ADR-010), not the implementation already covered by ``test_impacts.py``.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from pathlib import Path

import pytest
import yaml

from click.testing import CliRunner


# ---------------------------------------------------------------------------
# Helpers — duplicate the minimal codex-entry writer so this file does not
# couple to fixtures defined in ``test_impacts.py``. Mirrors the on-disk
# layout used by ``lore.impacts._load_codex_binds_index``.
# ---------------------------------------------------------------------------


def _write_codex_entry(
    project_root: Path,
    *,
    entry_id: str,
    binds: list | None = None,
) -> Path:
    """Write a minimal codex markdown file with optional ``binds:`` list."""
    fm: dict = {
        "id": entry_id,
        "title": entry_id.replace("-", " ").title(),
        "summary": f"Codex entry {entry_id}.",
    }
    if binds is not None:
        fm["binds"] = binds
    front = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)
    codex_dir = project_root / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    path = codex_dir / f"{entry_id}.md"
    path.write_text(f"---\n{front}---\nBody for {entry_id}.\n", encoding="utf-8")
    return path


@pytest.fixture()
def tmp_project(tmp_path):
    """Bare project with ``.lore/codex/`` ready for codex entries."""
    (tmp_path / ".lore" / "codex").mkdir(parents=True)
    return tmp_path


@pytest.fixture(autouse=True)
def _clear_binds_index_cache():
    """Drop the lru_cache between tests so each tmp_path sees a clean codex.

    ``lore.impacts._load_codex_binds_index`` is wrapped in
    ``functools.lru_cache(maxsize=1)``. Without clearing, different tmp_path
    fixtures collide on the cache key.
    """
    try:
        from lore.impacts import _load_codex_binds_index

        _load_codex_binds_index.cache_clear()
    except (ImportError, AttributeError):
        pass
    yield
    try:
        from lore.impacts import _load_codex_binds_index

        _load_codex_binds_index.cache_clear()
    except (ImportError, AttributeError):
        pass


# ===========================================================================
# Public surface — __all__ membership and importability
# ===========================================================================


def test_lore_models_all_contains_impacts():
    """ref-lore_api-core — ``__all__`` is the public-API contract.

    Scenario 7 / unit-test bullet: ``"impacts"`` is a member of
    ``lore.models.__all__``.
    """
    import lore.models as models

    assert "impacts" in models.__all__


def test_lore_models_all_contains_impacts_result():
    """Scenario 7 — ``"ImpactsResult"`` in ``lore.models.__all__``."""
    import lore.models as models

    assert "ImpactsResult" in models.__all__


def test_lore_models_all_contains_codex_binding():
    """Scenario 7 — ``"CodexBinding"`` in ``lore.models.__all__``."""
    import lore.models as models

    assert "CodexBinding" in models.__all__


def test_lore_models_all_contains_code_binding():
    """Scenario 7 — ``"CodeBinding"`` in ``lore.models.__all__``."""
    import lore.models as models

    assert "CodeBinding" in models.__all__


def test_lore_models_all_contains_impacts_error():
    """Scenario 7 — ``"ImpactsError"`` in ``lore.models.__all__``."""
    import lore.models as models

    assert "ImpactsError" in models.__all__


def test_public_reexport_from_lore_models_imports_cleanly():
    """Scenario 7 — façade import statement works as a single line.

    This mirrors the exact line in the story acceptance criteria:
    ``from lore.models import impacts, ImpactsResult, CodexBinding,
    CodeBinding, ImpactsError``. Until Green wires them, this import
    raises ``ImportError`` and the test fails.
    """
    from lore.models import (  # noqa: F401
        CodeBinding,
        CodexBinding,
        ImpactsError,
        ImpactsResult,
        impacts,
    )


# ===========================================================================
# Façade — re-export by reference, not by copy (standards-facade)
# ===========================================================================


def test_models_impacts_is_same_object_as_lore_impacts_impacts():
    """ref-lore_api-core — façade re-export by reference.

    Story unit-test bullet: ``lore.models.impacts is lore.impacts.impacts``.
    Catches accidental ``def impacts(...)`` redefinition inside ``models.py``.
    """
    import lore.impacts as impacts_mod
    import lore.models as models

    assert models.impacts is impacts_mod.impacts


def test_models_impacts_result_is_same_class_as_lore_impacts_impacts_result():
    """Façade by-reference: ``ImpactsResult`` is the same class object."""
    import lore.impacts as impacts_mod
    import lore.models as models

    assert models.ImpactsResult is impacts_mod.ImpactsResult


def test_models_codex_binding_is_same_class_as_lore_impacts_codex_binding():
    """Façade by-reference: ``CodexBinding`` is the same class object."""
    import lore.impacts as impacts_mod
    import lore.models as models

    assert models.CodexBinding is impacts_mod.CodexBinding


def test_models_code_binding_is_same_class_as_lore_impacts_code_binding():
    """Façade by-reference: ``CodeBinding`` is the same class object."""
    import lore.impacts as impacts_mod
    import lore.models as models

    assert models.CodeBinding is impacts_mod.CodeBinding


def test_models_impacts_error_is_same_class_as_lore_impacts_impacts_error():
    """Façade by-reference: ``ImpactsError`` is the same class object."""
    import lore.impacts as impacts_mod
    import lore.models as models

    assert models.ImpactsError is impacts_mod.ImpactsError


# ===========================================================================
# Signature — keyword-only project_root, direct_links=False
# ===========================================================================


def test_impacts_signature_token_is_positional():
    """Tech Spec § Python API — first parameter ``token: str`` is positional."""
    from lore.models import impacts

    sig = inspect.signature(impacts)
    params = list(sig.parameters.values())
    assert params[0].name == "token"
    assert params[0].kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


def test_impacts_signature_project_root_is_keyword_only():
    """ref-lore_api-core — ``project_root`` (NOT ``codex_dir``) is the
    public keyword parameter convention; must be keyword-only.
    """
    from lore.models import impacts

    sig = inspect.signature(impacts)
    assert "project_root" in sig.parameters
    assert (
        sig.parameters["project_root"].kind == inspect.Parameter.KEYWORD_ONLY
    )


def test_impacts_signature_has_no_codex_dir_parameter():
    """ref-lore_api-core — ``codex_dir`` is the legacy convention; the
    public Python API must NOT expose it.
    """
    from lore.models import impacts

    sig = inspect.signature(impacts)
    assert "codex_dir" not in sig.parameters


def test_impacts_signature_direct_links_is_keyword_only_default_false():
    """Tech Spec — ``direct_links`` is keyword-only with default ``False``."""
    from lore.models import impacts

    sig = inspect.signature(impacts)
    assert "direct_links" in sig.parameters
    p = sig.parameters["direct_links"]
    assert p.kind == inspect.Parameter.KEYWORD_ONLY
    assert p.default is False


# ===========================================================================
# Behaviour — codex-seed call returns CodexBinding list
# ===========================================================================


def test_impacts_codex_seed_returns_codex_kind_result(tmp_project):
    """Scenario 1 — codex-seed lookup returns ``kind == "codex"``.

    Verified through the ``lore.models`` façade (not ``lore.impacts`` direct).
    """
    from lore.models import impacts

    _write_codex_entry(
        tmp_project,
        entry_id="entry-mix",
        binds=["src/lore/cli.py", "src/lore/**/*.py"],
    )
    result = impacts("entry-mix", project_root=tmp_project)
    assert result.kind == "codex"
    assert result.code_items == ()


def test_impacts_codex_seed_codex_items_is_tuple_of_codex_binding(tmp_project):
    """Scenario 1 — ``codex_items`` is a tuple of ``CodexBinding`` instances."""
    from lore.models import CodexBinding, impacts

    _write_codex_entry(
        tmp_project,
        entry_id="entry-mix",
        binds=["src/lore/cli.py", "src/lore/**/*.py"],
    )
    result = impacts("entry-mix", project_root=tmp_project)
    assert isinstance(result.codex_items, tuple)
    assert len(result.codex_items) == 2
    for item in result.codex_items:
        assert isinstance(item, CodexBinding)


def test_impacts_codex_seed_returns_declaration_order(tmp_project):
    """Scenario 1 — exact value equality matches the story acceptance criteria."""
    from lore.models import CodexBinding, ImpactsResult, impacts

    _write_codex_entry(
        tmp_project,
        entry_id="entry-mix",
        binds=["src/lore/cli.py", "src/lore/**/*.py"],
    )
    result = impacts("entry-mix", project_root=tmp_project)
    assert result == ImpactsResult(
        kind="codex",
        codex_items=(
            CodexBinding(path="src/lore/cli.py", kind="exact"),
            CodexBinding(path="src/lore/**/*.py", kind="glob"),
        ),
        code_items=(),
    )


# ===========================================================================
# Behaviour — code-seed call returns CodeBinding list
# ===========================================================================


def test_impacts_code_seed_returns_code_kind_result(tmp_project):
    """Scenario 2 — code-seed lookup returns ``kind == "code"``."""
    from lore.models import impacts

    _write_codex_entry(
        tmp_project, entry_id="dec-006-id-references", binds=["src/lore/cli.py"]
    )
    result = impacts("src/lore/cli.py", project_root=tmp_project)
    assert result.kind == "code"
    assert result.codex_items == ()


def test_impacts_code_seed_code_items_is_tuple_of_code_binding(tmp_project):
    """Scenario 2 — ``code_items`` is a tuple of ``CodeBinding`` instances."""
    from lore.models import CodeBinding, impacts

    _write_codex_entry(
        tmp_project,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py"],
    )
    _write_codex_entry(
        tmp_project,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )
    result = impacts("src/lore/cli.py", project_root=tmp_project)
    assert isinstance(result.code_items, tuple)
    assert len(result.code_items) == 2
    for item in result.code_items:
        assert isinstance(item, CodeBinding)


def test_impacts_code_seed_returns_sorted_codebindings(tmp_project):
    """Scenario 2 — exact value equality matches story acceptance criteria."""
    from lore.models import CodeBinding, ImpactsResult, impacts

    _write_codex_entry(
        tmp_project,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py"],
    )
    _write_codex_entry(
        tmp_project,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )
    result = impacts("src/lore/cli.py", project_root=tmp_project)
    assert result == ImpactsResult(
        kind="code",
        code_items=(
            CodeBinding(id="dec-006-id-references", match="exact", pattern=None),
            CodeBinding(
                id="tech-arch-source-layout",
                match="glob",
                pattern="src/lore/**/*.py",
            ),
        ),
        codex_items=(),
    )


# ===========================================================================
# Error model — ImpactsError surfaces via lore.models
# ===========================================================================


def test_impacts_unknown_codex_id_raises_impacts_error(tmp_project):
    """Scenario 3 — unknown codex id raises ``ImpactsError`` via façade."""
    from lore.models import ImpactsError, impacts

    with pytest.raises(ImpactsError) as exc:
        impacts("no-such-id", project_root=tmp_project)
    assert exc.value.args[0] == 'Unknown codex id: "no-such-id"'


def test_impacts_error_is_subclass_of_value_error():
    """Tech Spec § Error Model — ``ImpactsError`` extends ``ValueError``.

    Catchable as ``ValueError`` per Scenario 3 story note.
    """
    from lore.models import ImpactsError

    assert issubclass(ImpactsError, ValueError)
    assert isinstance(ImpactsError("m"), ValueError)


def test_impacts_outside_repo_path_raises_impacts_error(tmp_project):
    """Scenario 4 — outside-repo path raises ``ImpactsError`` with exact msg."""
    from lore.models import ImpactsError, impacts

    with pytest.raises(ImpactsError) as exc:
        impacts("/etc/passwd", project_root=tmp_project)
    assert exc.value.args[0] == 'Path is outside the project root: "/etc/passwd"'


def test_impacts_traversal_token_raises_impacts_error(tmp_project):
    """Scenario 5 — ``..`` traversal raises ``ImpactsError`` with exact msg."""
    from lore.models import ImpactsError, impacts

    with pytest.raises(ImpactsError) as exc:
        impacts("../foo", project_root=tmp_project)
    assert exc.value.args[0] == 'Path traversal not allowed: "../foo"'


# ===========================================================================
# Filter — direct_links=True drops glob matches on code seed
# ===========================================================================


def test_impacts_direct_links_drops_glob_matches_on_code_seed(tmp_project):
    """Scenario 6 — ``direct_links=True`` keeps only exact matches."""
    from lore.models import CodeBinding, impacts

    _write_codex_entry(
        tmp_project,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py"],
    )
    _write_codex_entry(
        tmp_project,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )
    result = impacts(
        "src/lore/cli.py", project_root=tmp_project, direct_links=True
    )
    assert result.code_items == (
        CodeBinding(id="dec-006-id-references", match="exact", pattern=None),
    )


def test_impacts_direct_links_default_false_keeps_glob_matches(tmp_project):
    """Tech Spec — ``direct_links`` defaults to ``False``; glob rows kept."""
    from lore.models import impacts

    _write_codex_entry(
        tmp_project,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py"],
    )
    _write_codex_entry(
        tmp_project,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )
    result = impacts("src/lore/cli.py", project_root=tmp_project)
    glob_ids = {b.id for b in result.code_items if b.match == "glob"}
    assert "tech-arch-source-layout" in glob_ids


# ===========================================================================
# CLI parity — Python return contract == CLI `--json` envelope item shape
# ===========================================================================


def test_python_codex_items_match_cli_json_envelope(tmp_project, monkeypatch):
    """Scenario 8 — codex-seed item dict shape == CLI ``--json`` envelope items.

    Per-item dict keys ``{path, kind}`` round-trip via
    ``dataclasses.asdict`` against the CLI envelope's ``impacts`` list.
    """
    from lore.cli import main as cli
    from lore.models import impacts

    _write_codex_entry(
        tmp_project,
        entry_id="entry-mix",
        binds=["src/lore/cli.py", "src/lore/**/*.py"],
    )

    py_result = impacts("entry-mix", project_root=tmp_project)
    py_items = [dataclasses.asdict(b) for b in py_result.codex_items]

    runner = CliRunner()
    monkeypatch.chdir(tmp_project)
    cli_result = runner.invoke(cli, ["impacts", "entry-mix", "--json"])
    assert cli_result.exit_code == 0, cli_result.output
    cli_envelope = json.loads(cli_result.stdout)

    assert cli_envelope["impacts"] == py_items


def test_python_code_items_match_cli_json_envelope(tmp_project, monkeypatch):
    """Scenario 8 — code-seed item dict shape == CLI ``--json`` envelope items.

    Exact items emit ``{id, match}``; glob items emit ``{id, match, pattern}``.
    Python ``dataclasses.asdict`` produces ``{id, match, pattern}`` for both,
    so the parity assertion drops ``pattern`` when ``match == "exact"`` to
    match the CLI's pruning rule (Tech Spec § Output Formats).
    """
    from lore.cli import main as cli
    from lore.models import impacts

    _write_codex_entry(
        tmp_project,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py"],
    )
    _write_codex_entry(
        tmp_project,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )

    py_result = impacts("src/lore/cli.py", project_root=tmp_project)
    py_items: list[dict] = []
    for b in py_result.code_items:
        row = dataclasses.asdict(b)
        if row["match"] == "exact":
            row.pop("pattern", None)
        py_items.append(row)

    runner = CliRunner()
    monkeypatch.chdir(tmp_project)
    cli_result = runner.invoke(cli, ["impacts", "src/lore/cli.py", "--json"])
    assert cli_result.exit_code == 0, cli_result.output
    cli_envelope = json.loads(cli_result.stdout)

    assert cli_envelope["impacts"] == py_items


def test_python_direct_links_matches_cli_direct_links_flag(
    tmp_project, monkeypatch
):
    """Scenario 6 + parity — ``direct_links=True`` Python output mirrors
    ``--direct-links`` CLI output (same items, same order).
    """
    from lore.cli import main as cli
    from lore.models import impacts

    _write_codex_entry(
        tmp_project,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py"],
    )
    _write_codex_entry(
        tmp_project,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )

    py_result = impacts(
        "src/lore/cli.py", project_root=tmp_project, direct_links=True
    )
    py_items: list[dict] = []
    for b in py_result.code_items:
        row = dataclasses.asdict(b)
        if row["match"] == "exact":
            row.pop("pattern", None)
        py_items.append(row)

    runner = CliRunner()
    monkeypatch.chdir(tmp_project)
    cli_result = runner.invoke(
        cli, ["impacts", "src/lore/cli.py", "--direct-links", "--json"]
    )
    assert cli_result.exit_code == 0, cli_result.output
    cli_envelope = json.loads(cli_result.stdout)

    assert cli_envelope["impacts"] == py_items
