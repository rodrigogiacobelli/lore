"""Unit tests for G15.5 — doctrine module raises ``ValueError`` (not ``DoctrineError``).

Plan: ``transient-public-api-facade-plan §G15.5`` — *Remove ``DoctrineError``,
raise ``ValueError`` from doctrine module*.
Anchor: ``decisions-011-public-api-stability`` + ``standards-separation-of-concerns``
— operational modules raise plain Python exceptions; Click-subclass exceptions
are forbidden outside ``cli.py``.

G15.5 flips every ``raise DoctrineError(...)`` site in ``src/lore/doctrine.py``
to ``raise ValueError(...)`` and removes the ``class DoctrineError`` /
``import click`` lines. The message text MUST stay byte-identical so CLI
parity tests (``test_api_parity_doctrine.py``) keep their stderr/exit-code
assertions green.

These tests assert the post-flip contract:

  * ``validate_doctrine_content`` raises ``ValueError`` on every validation
    failure path (missing required field, name/id mismatch, invalid YAML,
    invalid step structure).
  * ``create_doctrine`` raises ``ValueError`` on invalid name, invalid group,
    duplicate doctrine, missing source files, and YAML/design id mismatch.
  * ``update_doctrine`` raises ``ValueError`` on missing target, missing
    doctrines_dir, invalid name, malformed YAML content, and schema failure.
  * ``delete_doctrine`` raises ``ValueError`` on missing target, missing
    doctrines_dir, and invalid name.
  * Message text on every path remains unchanged (parity).

Red phase — every test below MUST fail until G15.5 Green lands.

Open Items for orchestrator: pre-existing tests still asserting
``pytest.raises(DoctrineError)`` are obsolete after G15.5 Green and need
authorization to migrate. They live in:

  * ``tests/unit/test_doctrine.py`` (numerous sites — imports
    ``DoctrineError`` at module top, line ~20).
  * ``tests/unit/test_doctrine_crud.py`` (``TestUpdateDoctrineErrorPaths`` +
    ``TestDeleteDoctrineErrorPaths`` classes — every test imports
    ``DoctrineError`` and uses ``pytest.raises(DoctrineError)``).
  * ``tests/e2e/test_python_api.py`` (US-006 + US-008 scenarios — multiple
    ``from lore.doctrine import DoctrineError, ...`` + ``raises(DoctrineError, ...)``).
  * ``tests/e2e/test_doctrine_show.py`` (docstring/comment references only —
    test body asserts CLI exit code; safe but stale wording).

Note: ``tests/unit/test_api_surface.py`` + ``tests/unit/test_api_all_matches_spec.py``
still list ``DoctrineError`` in the expected ``lore.api.__all__`` surface.
G15.5 removes ``DoctrineError`` from ``lore.api.__all__`` — those surface
tests also need authorization to drop the name from the expected list.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixtures — valid + invalid YAML content blocks
# ---------------------------------------------------------------------------


VALID_DOCTRINE_YAML = (
    "id: tdd\n"
    "title: TDD\n"
    "summary: Test-driven development workflow.\n"
    "description: A doctrine for TDD.\n"
    "steps:\n"
    "  - id: red\n"
    "    title: Red\n"
    "  - id: green\n"
    "    title: Green\n"
)


FULL_UPDATED_DOCTRINE_YAML = (
    "id: tdd\n"
    "title: TDD v2\n"
    "summary: Updated TDD doctrine.\n"
    "description: Updated description.\n"
    "steps:\n"
    "  - id: red\n"
    "    title: Red\n"
    "  - id: green\n"
    "    title: Green\n"
)


# Schema-invalid: missing required `steps` field.
SCHEMA_INVALID_YAML = (
    "id: tdd\n"
    "title: TDD\n"
    "summary: Missing steps field.\n"
    "description: A doctrine missing the steps field.\n"
)


# Name mismatch — id disagrees with caller arg.
NAME_MISMATCH_YAML = (
    "id: not-tdd\n"
    "title: Wrong ID\n"
    "summary: id mismatches caller arg.\n"
    "description: Should be rejected.\n"
    "steps:\n"
    "  - id: red\n"
    "    title: Red\n"
)


# Malformed YAML (unclosed bracket).
MALFORMED_YAML = "id: tdd\nsteps: [\n"


def _write_doctrine_dir(tmp_path, *, name: str = "tdd") -> "pytest.fixture":
    """Create a doctrines_dir with a single seeded doctrine and return it."""
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    (doctrines_dir / f"{name}.yaml").write_text(VALID_DOCTRINE_YAML)
    return doctrines_dir


# ---------------------------------------------------------------------------
# validate_doctrine_content — every failure path raises ValueError
# ---------------------------------------------------------------------------


class TestValidateDoctrineContentRaisesValueError:
    """``validate_doctrine_content`` raises plain ``ValueError`` on failure."""

    def test_schema_invalid_yaml_raises_valueerror(self):
        """Schema failure raises ``ValueError`` (not ``DoctrineError``)."""
        from lore import doctrine as doctrine_mod
        from lore.doctrine import validate_doctrine_content

        with pytest.raises(ValueError) as exc_info:
            validate_doctrine_content(SCHEMA_INVALID_YAML, "tdd")
        import click

        assert not isinstance(exc_info.value, click.ClickException), (
            "validate_doctrine_content still raises a click.ClickException "
            "subclass — G15.5 not landed."
        )
        # Re-invocation through the module alias must raise the same plain ValueError.
        with pytest.raises(ValueError):
            doctrine_mod.validate_doctrine_content(SCHEMA_INVALID_YAML, "tdd")

    def test_id_mismatch_raises_valueerror(self):
        """``id`` disagrees with caller arg → ``ValueError``."""
        from lore.doctrine import validate_doctrine_content

        with pytest.raises(ValueError):
            validate_doctrine_content(NAME_MISMATCH_YAML, "tdd")

    def test_malformed_yaml_raises_valueerror(self):
        """Unparseable YAML → ``ValueError`` (not ``DoctrineError``)."""
        from lore.doctrine import validate_doctrine_content

        with pytest.raises(ValueError):
            validate_doctrine_content(MALFORMED_YAML, "tdd")

    def test_non_mapping_yaml_raises_valueerror(self):
        """YAML scalar / list at top level → ``ValueError``."""
        from lore.doctrine import validate_doctrine_content

        with pytest.raises(ValueError):
            validate_doctrine_content("- just\n- a\n- list\n", "tdd")

    def test_message_text_unchanged_for_missing_steps(self):
        """Message text parity: ``Missing required property 'steps'.``"""
        from lore.doctrine import validate_doctrine_content

        with pytest.raises(ValueError) as exc_info:
            validate_doctrine_content(SCHEMA_INVALID_YAML, "tdd")
        assert "steps" in str(exc_info.value)

    def test_message_text_unchanged_for_id_mismatch(self):
        """Message text parity: ``Doctrine id "..." does not match ...``"""
        from lore.doctrine import validate_doctrine_content

        with pytest.raises(ValueError) as exc_info:
            validate_doctrine_content(NAME_MISMATCH_YAML, "tdd")
        msg = str(exc_info.value)
        assert "not-tdd" in msg and "tdd" in msg


# ---------------------------------------------------------------------------
# create_doctrine — every failure path raises ValueError
# ---------------------------------------------------------------------------


class TestCreateDoctrineRaisesValueError:
    """``create_doctrine`` raises plain ``ValueError`` on every failure path."""

    def test_invalid_name_raises_valueerror(self, tmp_path):
        """Invalid name format → ``ValueError`` before any file I/O."""
        from lore.doctrine import create_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            create_doctrine(
                tmp_path,
                "INVALID NAME",
                tmp_path / "src.yaml",
                tmp_path / "src.design.md",
            )

    def test_invalid_name_is_not_click_exception(self, tmp_path):
        """``create_doctrine`` invalid-name raise is not a ``click.ClickException``."""
        import click

        from lore.doctrine import create_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError) as exc_info:
            create_doctrine(
                tmp_path,
                "INVALID NAME",
                tmp_path / "src.yaml",
                tmp_path / "src.design.md",
            )
        assert not isinstance(exc_info.value, click.ClickException)

    def test_invalid_group_raises_valueerror(self, tmp_path):
        """Invalid group format → ``ValueError``."""
        from lore.doctrine import create_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            create_doctrine(
                tmp_path,
                "tdd",
                tmp_path / "src.yaml",
                tmp_path / "src.design.md",
                group="BAD GROUP",
            )

    def test_missing_yaml_source_raises_valueerror(self, tmp_path):
        """Missing YAML source file → ``ValueError`` with ``File not found:``."""
        from lore.doctrine import create_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError) as exc_info:
            create_doctrine(
                tmp_path,
                "tdd",
                tmp_path / "missing.yaml",
                tmp_path / "missing.design.md",
            )
        assert "File not found" in str(exc_info.value)

    def test_missing_design_source_raises_valueerror(self, tmp_path):
        """Missing design source file → ``ValueError`` with ``File not found:``."""
        from lore.doctrine import create_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        yaml_src = tmp_path / "src.yaml"
        yaml_src.write_text(VALID_DOCTRINE_YAML)
        with pytest.raises(ValueError) as exc_info:
            create_doctrine(
                tmp_path,
                "tdd",
                yaml_src,
                tmp_path / "missing.design.md",
            )
        assert "File not found" in str(exc_info.value)

    def test_duplicate_doctrine_raises_valueerror(self, tmp_path):
        """Duplicate in subtree → ``ValueError`` with ``already exists``."""
        from lore.doctrine import create_doctrine

        _doctrines_dir = _write_doctrine_dir(tmp_path)
        yaml_src = tmp_path / "src.yaml"
        yaml_src.write_text(VALID_DOCTRINE_YAML)
        design_src = tmp_path / "src.design.md"
        design_src.write_text("---\nid: tdd\n---\nbody\n")
        with pytest.raises(ValueError) as exc_info:
            create_doctrine(tmp_path, "tdd", yaml_src, design_src)
        assert "already exists" in str(exc_info.value)

    def test_yaml_parse_error_raises_valueerror(self, tmp_path):
        """Malformed source YAML → ``ValueError`` with ``YAML parsing error:``."""
        from lore.doctrine import create_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        yaml_src = tmp_path / "src.yaml"
        yaml_src.write_text(MALFORMED_YAML)
        design_src = tmp_path / "src.design.md"
        design_src.write_text("---\nid: tdd\n---\nbody\n")
        with pytest.raises(ValueError) as exc_info:
            create_doctrine(tmp_path, "tdd", yaml_src, design_src)
        assert "YAML parsing error" in str(exc_info.value)

    def test_yaml_id_mismatch_raises_valueerror(self, tmp_path):
        """YAML id != name arg → ``ValueError``."""
        from lore.doctrine import create_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        yaml_src = tmp_path / "src.yaml"
        yaml_src.write_text(VALID_DOCTRINE_YAML)
        design_src = tmp_path / "src.design.md"
        design_src.write_text("---\nid: not-tdd\n---\nbody\n")
        with pytest.raises(ValueError):
            # name is `not-tdd` so YAML (id=tdd) mismatches; covers
            # _validate_yaml_schema mismatch path.
            create_doctrine(tmp_path, "not-tdd", yaml_src, design_src)


# ---------------------------------------------------------------------------
# update_doctrine — every failure path raises ValueError
# ---------------------------------------------------------------------------


class TestUpdateDoctrineRaisesValueError:
    """``update_doctrine`` raises plain ``ValueError`` on every failure path."""

    def test_missing_target_raises_valueerror(self, tmp_path):
        """Missing on-disk doctrine → ``ValueError``."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            update_doctrine(tmp_path, "nonexistent", FULL_UPDATED_DOCTRINE_YAML)

    def test_missing_target_is_not_click_exception(self, tmp_path):
        """The raised exception must NOT be a ``click.ClickException`` subclass."""
        import click

        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError) as exc_info:
            update_doctrine(tmp_path, "nonexistent", FULL_UPDATED_DOCTRINE_YAML)
        assert not isinstance(exc_info.value, click.ClickException)

    def test_missing_doctrines_dir_raises_valueerror(self, tmp_path):
        """Missing ``doctrines_dir`` → ``ValueError``."""
        from lore.doctrine import update_doctrine

        _doctrines_dir = tmp_path / ".lore" / "doctrines"
        # intentionally NOT created
        with pytest.raises(ValueError):
            update_doctrine(tmp_path, "tdd", FULL_UPDATED_DOCTRINE_YAML)

    def test_invalid_name_raises_valueerror(self, tmp_path):
        """Invalid name format → ``ValueError`` (validate_name).

        ``validate_name`` already returns the error string; the doctrine
        module wraps it. Post-G15.5 the wrapper raises ``ValueError`` instead
        of ``DoctrineError``.
        """
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            update_doctrine(tmp_path, "INVALID NAME", FULL_UPDATED_DOCTRINE_YAML)

    def test_schema_failure_raises_valueerror(self, tmp_path):
        """Schema-invalid content → ``ValueError`` propagated from validation."""
        from lore.doctrine import update_doctrine

        _doctrines_dir = _write_doctrine_dir(tmp_path)
        with pytest.raises(ValueError):
            update_doctrine(tmp_path, "tdd", SCHEMA_INVALID_YAML)

    def test_malformed_yaml_raises_valueerror(self, tmp_path):
        """Malformed YAML content → ``ValueError`` with ``YAML parsing error:``."""
        from lore.doctrine import update_doctrine

        _doctrines_dir = _write_doctrine_dir(tmp_path)
        with pytest.raises(ValueError) as exc_info:
            update_doctrine(tmp_path, "tdd", MALFORMED_YAML)
        assert "YAML parsing error" in str(exc_info.value)

    def test_message_text_unchanged_for_missing_target(self, tmp_path):
        """Parity: ``Doctrine "nonexistent" not found.`` message preserved."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError) as exc_info:
            update_doctrine(tmp_path, "nonexistent", FULL_UPDATED_DOCTRINE_YAML)
        assert "nonexistent" in str(exc_info.value)
        assert "not found" in str(exc_info.value)


# ---------------------------------------------------------------------------
# delete_doctrine — every failure path raises ValueError
# ---------------------------------------------------------------------------


class TestDeleteDoctrineRaisesValueError:
    """``delete_doctrine`` raises plain ``ValueError`` on every failure path."""

    def test_missing_target_raises_valueerror(self, tmp_path):
        """Missing doctrine → ``ValueError`` (not idempotent)."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            delete_doctrine(tmp_path, "nonexistent")

    def test_missing_target_is_not_click_exception(self, tmp_path):
        """Delete miss must NOT raise a ``click.ClickException`` subclass."""
        import click

        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError) as exc_info:
            delete_doctrine(tmp_path, "nonexistent")
        assert not isinstance(exc_info.value, click.ClickException)

    def test_missing_doctrines_dir_raises_valueerror(self, tmp_path):
        """Missing ``doctrines_dir`` → ``ValueError``."""
        from lore.doctrine import delete_doctrine

        _doctrines_dir = tmp_path / ".lore" / "doctrines"
        # intentionally NOT created
        with pytest.raises(ValueError):
            delete_doctrine(tmp_path, "tdd")

    def test_invalid_name_raises_valueerror(self, tmp_path):
        """Invalid name format → ``ValueError``."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            delete_doctrine(tmp_path, "INVALID NAME")

    def test_message_text_unchanged_for_missing_target(self, tmp_path):
        """Parity: ``Doctrine "nonexistent" not found`` message preserved."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError) as exc_info:
            delete_doctrine(tmp_path, "nonexistent")
        assert "nonexistent" in str(exc_info.value)
        assert "not found" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Module-level invariants — DoctrineError class is removed
# ---------------------------------------------------------------------------


class TestDoctrineErrorClassRemoved:
    """G15.5: ``DoctrineError`` class is gone; no ``import click`` line."""

    def test_doctrine_module_has_no_doctrine_error_class(self):
        """``DoctrineError`` is no longer an attribute of ``lore.doctrine``."""
        from lore import doctrine as doctrine_mod

        assert not hasattr(doctrine_mod, "DoctrineError"), (
            "lore.doctrine still exposes DoctrineError — G15.5 not landed."
        )

    def test_doctrine_module_source_has_no_doctrine_error_text(self):
        """Grep-equivalent: ``DoctrineError`` substring absent from source."""
        from pathlib import Path

        import lore.doctrine as doctrine_mod

        src_path = Path(doctrine_mod.__file__)
        text = src_path.read_text()
        assert "DoctrineError" not in text, (
            "src/lore/doctrine.py still references DoctrineError — G15.5 not landed."
        )

    def test_doctrine_module_source_has_no_click_import(self):
        """Grep-equivalent: no ``import click`` / ``from click`` in doctrine.py."""
        from pathlib import Path

        import lore.doctrine as doctrine_mod

        src_path = Path(doctrine_mod.__file__)
        text = src_path.read_text()
        for line in text.splitlines():
            stripped = line.strip()
            assert not stripped.startswith("import click"), (
                "src/lore/doctrine.py still has `import click` — G15.5 not landed."
            )
            assert not stripped.startswith("from click"), (
                "src/lore/doctrine.py still has `from click ...` — G15.5 not landed."
            )

    def test_doctrine_module_ast_imports_no_click(self):
        """AST check: ``lore.doctrine`` imports no ``click`` name."""
        import ast
        from pathlib import Path

        import lore.doctrine as doctrine_mod

        src_path = Path(doctrine_mod.__file__)
        tree = ast.parse(src_path.read_text(), filename=str(src_path))
        bad: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "click" or alias.name.startswith("click."):
                        bad.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module == "click" or (node.module or "").startswith("click."):
                    bad.append(f"from {node.module} import ...")
        assert not bad, (
            f"src/lore/doctrine.py still imports click: {bad}. "
            "ADR-011 forbids click in operational modules."
        )
