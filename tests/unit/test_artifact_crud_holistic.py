"""Holistic CRUD sweep for ``lore.artifact`` — G16 Red.

Plan: ``transient-public-api-facade-plan`` §G16.
Amendment: ``transient-public-api-facade-create-stdz`` Sections A1, A2,
A4, A5, A6 + Section B (Artifact row) + Section F G16 step-list.

Pins the BREAKING contracts:

* First-arg flip — every callable takes ``project_root: Path`` instead of
  ``artifacts_dir: Path``.
* ``scan_artifacts`` renamed to ``list_artifacts`` per amendment Pattern
  1 (CRUD asymmetry) and Section E breaking list.
* ``read_artifact`` envelope GAINS ``filename`` and ``group`` keys
  (additive) per amendment A2 read-shape rule + Open Item 11 /
  F-ARTIFACT-MUTATION-CONTRACT.
* ``create_artifact`` envelope ``{id, filename, group}`` — drops ``path``.
* ``delete_artifact`` envelope gains ``deleted_at: None`` per A2.

Red phase — every test below MUST fail until G16 Green lands.
"""

from __future__ import annotations

import inspect

import pytest

import lore.artifact as _a_mod
from lore import api


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path):
    (tmp_path / ".lore" / "artifacts").mkdir(parents=True)
    return tmp_path


ARTIFACT_MD = (
    "---\n"
    "id: tmpl\n"
    "title: Template\n"
    "summary: An artifact template.\n"
    "---\n"
    "# body\n"
)


# ---------------------------------------------------------------------------
# Facade __all__ — scan_artifacts dropped; list_artifacts present.
# ---------------------------------------------------------------------------


class TestFacadeAllShape:
    def test_scan_artifacts_not_in_api_all(self):
        assert "scan_artifacts" not in api.__all__, (
            "G16: scan_artifacts renamed to list_artifacts; drop from facade."
        )

    def test_scan_artifacts_import_raises(self):
        with pytest.raises(ImportError):
            from lore.api import scan_artifacts  # noqa: F401

    def test_list_artifacts_in_api_all(self):
        assert "list_artifacts" in api.__all__

    def test_list_artifacts_identity_reexport(self):
        assert api.list_artifacts is _a_mod.list_artifacts


# ---------------------------------------------------------------------------
# Signatures — project_root first; no artifacts_dir parameter.
# ---------------------------------------------------------------------------


class TestArtifactSignaturesUseProjectRoot:
    @pytest.mark.parametrize(
        "fn_name",
        (
            "create_artifact",
            "read_artifact",
            "update_artifact",
            "delete_artifact",
            "list_artifacts",
        ),
    )
    def test_first_positional_named_project_root(self, fn_name):
        fn = getattr(_a_mod, fn_name)
        params = list(inspect.signature(fn).parameters.values())
        assert params and params[0].name == "project_root", (
            f"{fn_name} first positional must be 'project_root' "
            f"(got {params[0].name if params else 'none'!r})."
        )

    @pytest.mark.parametrize(
        "fn_name",
        (
            "create_artifact",
            "read_artifact",
            "update_artifact",
            "delete_artifact",
            "list_artifacts",
        ),
    )
    def test_no_artifacts_dir_parameter(self, fn_name):
        fn = getattr(_a_mod, fn_name)
        assert "artifacts_dir" not in inspect.signature(fn).parameters


# ---------------------------------------------------------------------------
# create_artifact envelope — {id, filename, group}; no path.
# ---------------------------------------------------------------------------


class TestCreateArtifactReturnEnvelope:
    def test_envelope_keys(self, project_root):
        result = _a_mod.create_artifact(project_root, "tmpl", ARTIFACT_MD)
        assert set(result.keys()) == {"id", "filename", "group"}

    def test_envelope_drops_path_key(self, project_root):
        result = _a_mod.create_artifact(project_root, "tmpl", ARTIFACT_MD)
        assert "path" not in result, (
            "amendment B: create_artifact drops 'path' (separation-of-concerns)."
        )

    def test_envelope_filename(self, project_root):
        result = _a_mod.create_artifact(project_root, "tmpl", ARTIFACT_MD)
        assert result["filename"] == "tmpl.md"

    def test_envelope_with_group(self, project_root):
        result = _a_mod.create_artifact(
            project_root, "tmpl", ARTIFACT_MD, group="templates"
        )
        assert result["group"] == "templates"


# ---------------------------------------------------------------------------
# read_artifact envelope GAINS filename + group keys (additive).
# ---------------------------------------------------------------------------


class TestReadArtifactEnvelopeGainsFilenameGroup:
    def test_read_envelope_has_filename(self, project_root):
        _a_mod.create_artifact(project_root, "tmpl", ARTIFACT_MD)
        result = _a_mod.read_artifact(project_root, "tmpl")
        assert "filename" in result, (
            "amendment B Artifact row: read_artifact dict GAINS filename key."
        )
        assert result["filename"] == "tmpl.md"

    def test_read_envelope_has_group(self, project_root):
        _a_mod.create_artifact(project_root, "tmpl", ARTIFACT_MD)
        result = _a_mod.read_artifact(project_root, "tmpl")
        assert "group" in result, (
            "amendment B Artifact row: read_artifact dict GAINS group key."
        )

    def test_read_envelope_keys_full_set(self, project_root):
        """Full key set: {id, title, summary, body, filename, group}."""
        _a_mod.create_artifact(project_root, "tmpl", ARTIFACT_MD)
        result = _a_mod.read_artifact(project_root, "tmpl")
        assert set(result.keys()) == {
            "id",
            "title",
            "summary",
            "body",
            "filename",
            "group",
        }

    def test_read_group_subdir(self, project_root):
        _a_mod.create_artifact(
            project_root, "tmpl", ARTIFACT_MD, group="templates"
        )
        result = _a_mod.read_artifact(project_root, "tmpl")
        assert result["group"] == "templates"

    def test_read_missing_returns_none(self, project_root):
        assert _a_mod.read_artifact(project_root, "nope") is None


# ---------------------------------------------------------------------------
# delete_artifact envelope gains deleted_at: None.
# ---------------------------------------------------------------------------


class TestDeleteArtifactEnvelope:
    def test_delete_envelope_includes_deleted_at(self, project_root):
        _a_mod.create_artifact(project_root, "tmpl", ARTIFACT_MD)
        result = _a_mod.delete_artifact(project_root, "tmpl")
        assert "deleted_at" in result
        assert result["deleted_at"] is None


# ---------------------------------------------------------------------------
# list_artifacts — first-arg flip; replaces scan_artifacts.
# ---------------------------------------------------------------------------


class TestListArtifactsProjectRoot:
    def test_list_takes_project_root(self, project_root):
        _a_mod.create_artifact(project_root, "tmpl", ARTIFACT_MD)
        records = _a_mod.list_artifacts(project_root)
        assert isinstance(records, list)
        assert any(r["id"] == "tmpl" for r in records)

    def test_list_empty_when_dir_absent(self, tmp_path):
        assert _a_mod.list_artifacts(tmp_path) == []

    def test_module_has_no_scan_artifacts_symbol(self):
        assert not hasattr(_a_mod, "scan_artifacts"), (
            "scan_artifacts must be removed; use list_artifacts."
        )
