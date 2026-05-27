"""Holistic CRUD sweep for ``lore.doctrine`` — G16 Red.

Plan: ``transient-public-api-facade-plan`` §G16.
Amendment: ``transient-public-api-facade-create-stdz`` Sections A1, A2,
A5, A6 + Section B (Doctrine row) + Section F G16 step-list.

Pins the BREAKING contracts:

* First-arg flip on every callable: ``create_doctrine`` /
  ``read_doctrine`` / ``update_doctrine`` / ``delete_doctrine`` /
  ``list_doctrines`` take ``project_root: Path`` first.
* ``create_doctrine`` positional reorder:
  ``(project_root, name, yaml_source_path, design_source_path, *, group=None)``.
* ``create_doctrine`` envelope ``{id, filename, group, design_filename}``
  — renames ``name``→``id``; drops ``path`` and ``yaml_filename``
  (``filename`` covers the primary slot).
* ``show_doctrine`` renamed to ``read_doctrine`` — returns
  ``dict | None`` (``None`` on miss, was raising ``DoctrineError`` per
  amendment Review Ledger CHANGED row + F-READ-DOCTRINE-RAISE-TO-NONE).
* ``delete_doctrine`` atomically renames BOTH ``.yaml`` and
  ``.design.md`` partners to ``.deleted`` (amendment Review Ledger
  CHANGED row "B Doctrine row — both-file behaviour"). Envelope gains
  ``deleted_at: None`` per A2.
* ``DoctrineError`` removed per G15.5 — module raises ``ValueError``.
* ``show_doctrine`` no longer in ``lore.api.__all__``.

Red phase — every test below MUST fail until G16 Green lands.
"""

from __future__ import annotations

import inspect
import textwrap

import pytest

import lore.doctrine as _d_mod
from lore import api


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path):
    (tmp_path / ".lore" / "doctrines").mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def doctrine_sources(tmp_path):
    """Return (yaml_path, design_path) for a valid doctrine named ``feat``."""
    yaml_path = tmp_path / "src.yaml"
    yaml_path.write_text(
        textwrap.dedent(
            """\
            id: feat
            title: Feat
            summary: A feature doctrine.
            steps:
              - id: red
                title: Red
                type: human
              - id: green
                title: Green
                type: human
            """
        )
    )
    design_path = tmp_path / "src.design.md"
    design_path.write_text(
        textwrap.dedent(
            """\
            ---
            id: feat
            title: Feat
            summary: A feature doctrine.
            ---
            # body
            """
        )
    )
    return yaml_path, design_path


# ---------------------------------------------------------------------------
# Facade — show_doctrine dropped; read_doctrine present.
# ---------------------------------------------------------------------------


class TestFacadeAllShape:
    def test_show_doctrine_not_in_api_all(self):
        assert "show_doctrine" not in api.__all__, (
            "G16: show_doctrine renamed to read_doctrine; drop from facade."
        )

    def test_show_doctrine_import_raises(self):
        with pytest.raises(ImportError):
            from lore.api import show_doctrine  # noqa: F401

    def test_read_doctrine_in_api_all(self):
        assert "read_doctrine" in api.__all__

    def test_read_doctrine_identity_reexport(self):
        assert api.read_doctrine is _d_mod.read_doctrine


# ---------------------------------------------------------------------------
# Signatures — project_root first; create_doctrine positional reorder.
# ---------------------------------------------------------------------------


class TestDoctrineSignaturesUseProjectRoot:
    @pytest.mark.parametrize(
        "fn_name",
        (
            "create_doctrine",
            "read_doctrine",
            "update_doctrine",
            "delete_doctrine",
            "list_doctrines",
        ),
    )
    def test_first_positional_named_project_root(self, fn_name):
        fn = getattr(_d_mod, fn_name)
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        assert params and params[0].name == "project_root", (
            f"{fn_name} first positional must be 'project_root' "
            f"(got {params[0].name if params else 'none'!r})."
        )

    @pytest.mark.parametrize(
        "fn_name",
        (
            "create_doctrine",
            "read_doctrine",
            "update_doctrine",
            "delete_doctrine",
            "list_doctrines",
        ),
    )
    def test_no_doctrines_dir_parameter(self, fn_name):
        fn = getattr(_d_mod, fn_name)
        assert "doctrines_dir" not in inspect.signature(fn).parameters

    def test_create_doctrine_positional_order(self):
        """``create_doctrine(project_root, name, yaml_source_path, design_source_path, *, group=None)``."""
        sig = inspect.signature(_d_mod.create_doctrine)
        positional = [
            p.name
            for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        assert positional == [
            "project_root",
            "name",
            "yaml_source_path",
            "design_source_path",
        ], f"Positional order: {positional}"

    def test_create_doctrine_group_is_keyword_only(self):
        sig = inspect.signature(_d_mod.create_doctrine)
        group_param = sig.parameters.get("group")
        assert group_param is not None
        assert group_param.kind == group_param.KEYWORD_ONLY


# ---------------------------------------------------------------------------
# create_doctrine envelope — {id, filename, group, design_filename}.
# ---------------------------------------------------------------------------


class TestCreateDoctrineReturnEnvelope:
    def test_envelope_keys_are_id_filename_group_design_filename(
        self, project_root, doctrine_sources
    ):
        yaml_path, design_path = doctrine_sources
        result = _d_mod.create_doctrine(
            project_root, "feat", yaml_path, design_path
        )
        assert set(result.keys()) == {
            "id",
            "filename",
            "group",
            "design_filename",
        }

    def test_envelope_id_key(self, project_root, doctrine_sources):
        yaml_path, design_path = doctrine_sources
        result = _d_mod.create_doctrine(
            project_root, "feat", yaml_path, design_path
        )
        assert result["id"] == "feat"

    def test_envelope_filename_is_yaml(self, project_root, doctrine_sources):
        yaml_path, design_path = doctrine_sources
        result = _d_mod.create_doctrine(
            project_root, "feat", yaml_path, design_path
        )
        assert result["filename"] == "feat.yaml"

    def test_envelope_design_filename(self, project_root, doctrine_sources):
        yaml_path, design_path = doctrine_sources
        result = _d_mod.create_doctrine(
            project_root, "feat", yaml_path, design_path
        )
        assert result["design_filename"] == "feat.design.md"

    def test_envelope_drops_name_key(self, project_root, doctrine_sources):
        yaml_path, design_path = doctrine_sources
        result = _d_mod.create_doctrine(
            project_root, "feat", yaml_path, design_path
        )
        assert "name" not in result, "amendment B: name→id rename"

    def test_envelope_drops_path_key(self, project_root, doctrine_sources):
        yaml_path, design_path = doctrine_sources
        result = _d_mod.create_doctrine(
            project_root, "feat", yaml_path, design_path
        )
        assert "path" not in result

    def test_envelope_drops_yaml_filename_key(
        self, project_root, doctrine_sources
    ):
        yaml_path, design_path = doctrine_sources
        result = _d_mod.create_doctrine(
            project_root, "feat", yaml_path, design_path
        )
        assert "yaml_filename" not in result, (
            "amendment B: filename covers the primary slot; drop yaml_filename."
        )

    def test_files_written_at_doctrines_subdir(
        self, project_root, doctrine_sources
    ):
        yaml_path, design_path = doctrine_sources
        _d_mod.create_doctrine(project_root, "feat", yaml_path, design_path)
        d = project_root / ".lore" / "doctrines"
        assert (d / "feat.yaml").is_file()
        assert (d / "feat.design.md").is_file()


# ---------------------------------------------------------------------------
# read_doctrine — None on miss; was raising DoctrineError.
# ---------------------------------------------------------------------------


class TestReadDoctrineNoneOnMiss:
    """``read_doctrine`` returns ``None`` on miss (was raising)."""

    def test_missing_returns_none_not_raise(self, project_root):
        result = _d_mod.read_doctrine(project_root, "nonexistent")
        assert result is None, (
            "amendment Review Ledger F-READ-DOCTRINE-RAISE-TO-NONE: "
            "read_doctrine returns None on miss (was DoctrineError raise)."
        )

    def test_missing_does_not_raise_value_error(self, project_root):
        # Sanity — even a generic exception must not surface for a miss.
        try:
            result = _d_mod.read_doctrine(project_root, "nonexistent")
        except Exception as exc:  # pragma: no cover — fail path
            pytest.fail(f"read_doctrine raised on miss: {exc!r}")
        assert result is None

    def test_existing_returns_dict(self, project_root, doctrine_sources):
        yaml_path, design_path = doctrine_sources
        _d_mod.create_doctrine(project_root, "feat", yaml_path, design_path)
        result = _d_mod.read_doctrine(project_root, "feat")
        assert isinstance(result, dict)
        assert result["id"] == "feat"


# ---------------------------------------------------------------------------
# delete_doctrine — renames BOTH .yaml AND .design.md atomically.
# ---------------------------------------------------------------------------


class TestDeleteDoctrineAtomicPair:
    """``delete_doctrine`` renames BOTH partner files (.yaml + .design.md)."""

    def test_delete_renames_yaml_partner(
        self, project_root, doctrine_sources
    ):
        yaml_path, design_path = doctrine_sources
        _d_mod.create_doctrine(project_root, "feat", yaml_path, design_path)
        _d_mod.delete_doctrine(project_root, "feat")
        d = project_root / ".lore" / "doctrines"
        assert not (d / "feat.yaml").exists()
        assert (d / "feat.yaml.deleted").is_file()

    def test_delete_renames_design_partner(
        self, project_root, doctrine_sources
    ):
        yaml_path, design_path = doctrine_sources
        _d_mod.create_doctrine(project_root, "feat", yaml_path, design_path)
        _d_mod.delete_doctrine(project_root, "feat")
        d = project_root / ".lore" / "doctrines"
        assert not (d / "feat.design.md").exists()
        assert (d / "feat.design.md.deleted").is_file()

    def test_delete_envelope_gains_deleted_at(
        self, project_root, doctrine_sources
    ):
        yaml_path, design_path = doctrine_sources
        _d_mod.create_doctrine(project_root, "feat", yaml_path, design_path)
        result = _d_mod.delete_doctrine(project_root, "feat")
        assert "deleted_at" in result
        assert result["deleted_at"] is None

    def test_delete_envelope_id_and_deleted_flag(
        self, project_root, doctrine_sources
    ):
        yaml_path, design_path = doctrine_sources
        _d_mod.create_doctrine(project_root, "feat", yaml_path, design_path)
        result = _d_mod.delete_doctrine(project_root, "feat")
        assert result["id"] == "feat"
        assert result["deleted"] is True


# ---------------------------------------------------------------------------
# DoctrineError gone — G15.5 already removed it; module raises ValueError.
# ---------------------------------------------------------------------------


class TestDoctrineErrorRemoved:
    def test_module_has_no_doctrine_error_symbol(self):
        assert not hasattr(_d_mod, "DoctrineError"), (
            "G15.5: DoctrineError class removed; doctrine raises ValueError."
        )

    def test_facade_has_no_doctrine_error(self):
        assert "DoctrineError" not in api.__all__, (
            "G15.5: DoctrineError dropped from facade."
        )


# ---------------------------------------------------------------------------
# list_doctrines — first-arg flip; returns list[dict].
# ---------------------------------------------------------------------------


class TestListDoctrines:
    def test_list_takes_project_root(self, project_root, doctrine_sources):
        yaml_path, design_path = doctrine_sources
        _d_mod.create_doctrine(project_root, "feat", yaml_path, design_path)
        records = _d_mod.list_doctrines(project_root)
        assert isinstance(records, list)
        assert any(r["id"] == "feat" for r in records)

    def test_list_empty_when_dir_absent(self, tmp_path):
        records = _d_mod.list_doctrines(tmp_path)
        assert records == []
