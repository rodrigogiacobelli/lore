"""Holistic CRUD sweep for ``lore.knight`` — G16 Red.

Plan: ``transient-public-api-facade-plan`` §G16 (file-backed sweep).
Amendment: ``transient-public-api-facade-create-stdz`` Sections A1, A2,
A4, A5, A6 + Section B (Knight row) + Section F G16 step-list.

Pins the BREAKING contracts:

* First-arg flip — every operational callable takes ``project_root: Path``
  instead of ``knights_dir: Path``.
* ``create_knight`` returns ``{id, filename, group}`` — renames ``name``
  to ``id`` and drops ``path`` (internal-layout leak per
  ``standards-separation-of-concerns``).
* ``update_knight`` / ``delete_knight`` keep their existing envelopes but
  also take ``project_root``.
* ``delete_knight`` gains ``deleted_at: None`` per amendment A2 delete-
  shape (file-backed entities use ``None`` because rename-based delete
  has no UTC stamp).
* ``read_knight`` returns the full record ``{id, group, title, summary,
  filename, body}`` or ``None`` on miss. This SUPERSEDES the canonical
  Section 4 text-shape (which returned ``str``); per amendment Review
  Ledger CHANGED row "B Knight row — read_knight return shape".
* ``find_knight`` no longer in ``lore.api.__all__`` (reclassified to
  internal ``_find_knight`` per amendment C4 / F-READ-KNIGHT-SUPERSEDES).
* Frontmatter parse routes through ``frontmatter.parse_frontmatter_text``
  + ``schemas.validate_entity("knight-frontmatter", meta)`` and raises
  ``ValueError`` on invalid input (amendment A4 / A5).
* ``entity_location`` is the only locator helper used internally
  (amendment A3 / C1) — ``knights_dir`` is no longer the parameter name.

Red phase — every test below MUST fail until G16 Green lands.

Source spec docs::

    lore codex show transient-public-api-facade-plan
    lore codex show transient-public-api-facade-create-stdz
"""

from __future__ import annotations

import inspect

import pytest

import lore.knight as _k_mod
from lore import api


# ---------------------------------------------------------------------------
# Fixture — minimal project root with .lore/knights/ created.
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path):
    """Bare project root with ``.lore/knights/`` ready to receive files."""
    (tmp_path / ".lore" / "knights").mkdir(parents=True)
    return tmp_path


PERSONA_MD = (
    "---\n"
    "id: reviewer\n"
    "title: Reviewer\n"
    "summary: A reviewer persona.\n"
    "---\n"
    "# body text\n"
)


# ---------------------------------------------------------------------------
# Facade __all__ — find_knight removed; read_knight stays; new signatures.
# ---------------------------------------------------------------------------


class TestFacadeAllShape:
    """``lore.api.__all__`` drops ``find_knight``; ``read_knight`` is dict-returning."""

    def test_find_knight_not_in_api_all(self):
        assert "find_knight" not in api.__all__, (
            "G16: find_knight reclassified internal (_find_knight); "
            "must be removed from lore.api.__all__."
        )

    def test_find_knight_raises_import_error_from_api(self):
        """Direct ``from lore.api import find_knight`` must fail post-G16."""
        with pytest.raises(ImportError):
            from lore.api import find_knight  # noqa: F401

    def test_read_knight_in_api_all(self):
        assert "read_knight" in api.__all__

    def test_read_knight_is_identity_reexport(self):
        assert api.read_knight is _k_mod.read_knight


# ---------------------------------------------------------------------------
# Signature — first-arg flip; parameter names use project_root, NOT *_dir.
# ---------------------------------------------------------------------------


class TestKnightSignaturesUseProjectRoot:
    """Every operational ``*_knight`` callable's first positional is project_root."""

    @pytest.mark.parametrize(
        "fn_name",
        (
            "create_knight",
            "read_knight",
            "update_knight",
            "delete_knight",
            "list_knights",
        ),
    )
    def test_first_positional_named_project_root(self, fn_name):
        fn = getattr(_k_mod, fn_name)
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        assert params, f"{fn_name} has no parameters"
        assert params[0].name == "project_root", (
            f"{fn_name} first positional must be 'project_root' "
            f"(got {params[0].name!r}); amendment A1."
        )

    @pytest.mark.parametrize(
        "fn_name",
        (
            "create_knight",
            "read_knight",
            "update_knight",
            "delete_knight",
            "list_knights",
        ),
    )
    def test_no_knights_dir_parameter(self, fn_name):
        fn = getattr(_k_mod, fn_name)
        sig = inspect.signature(fn)
        assert "knights_dir" not in sig.parameters, (
            f"{fn_name} still has knights_dir parameter — amendment A1 "
            "flips first arg to project_root."
        )


# ---------------------------------------------------------------------------
# create_knight envelope — {id, filename, group}; no path; no name.
# ---------------------------------------------------------------------------


class TestCreateKnightReturnEnvelope:
    """``create_knight(project_root, ...)`` returns ``{id, filename, group}``."""

    def test_create_returns_id_filename_group_keys_only(self, project_root):
        result = _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        assert set(result.keys()) == {"id", "filename", "group"}, (
            f"create_knight envelope keys mismatch: got {sorted(result)}"
        )

    def test_create_id_key_is_name(self, project_root):
        result = _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        assert result["id"] == "reviewer"

    def test_create_filename_is_basename(self, project_root):
        result = _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        assert result["filename"] == "reviewer.md"

    def test_create_group_default_is_none(self, project_root):
        result = _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        assert result["group"] is None

    def test_create_drops_path_key(self, project_root):
        result = _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        assert "path" not in result, (
            "create_knight envelope must NOT include 'path' (internal-"
            "layout leak per standards-separation-of-concerns)."
        )

    def test_create_drops_name_key(self, project_root):
        result = _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        assert "name" not in result, (
            "create_knight: amendment B renames 'name' key to 'id'."
        )

    def test_create_with_group_populates_group_key(self, project_root):
        result = _k_mod.create_knight(
            project_root, "reviewer", PERSONA_MD, group="default"
        )
        assert result["group"] == "default"

    def test_create_with_group_writes_under_subdir(self, project_root):
        _k_mod.create_knight(
            project_root, "reviewer", PERSONA_MD, group="default"
        )
        target = (
            project_root / ".lore" / "knights" / "default" / "reviewer.md"
        )
        assert target.is_file()


# ---------------------------------------------------------------------------
# read_knight — full dict shape {id, group, title, summary, filename, body}.
# ---------------------------------------------------------------------------


class TestReadKnightReturnsFullDict:
    """``read_knight(project_root, name)`` returns the full record dict."""

    def test_read_returns_dict_not_string(self, project_root):
        _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        result = _k_mod.read_knight(project_root, "reviewer")
        assert isinstance(result, dict), (
            "read_knight return shape supersedes canonical Section 4 "
            "(text-only); amendment B Knight row + A2 read-shape."
        )

    def test_read_returns_full_six_key_dict(self, project_root):
        _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        result = _k_mod.read_knight(project_root, "reviewer")
        assert set(result.keys()) == {
            "id",
            "group",
            "title",
            "summary",
            "filename",
            "body",
        }

    def test_read_id_field(self, project_root):
        _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        result = _k_mod.read_knight(project_root, "reviewer")
        assert result["id"] == "reviewer"

    def test_read_title_field(self, project_root):
        _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        result = _k_mod.read_knight(project_root, "reviewer")
        assert result["title"] == "Reviewer"

    def test_read_summary_field(self, project_root):
        _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        result = _k_mod.read_knight(project_root, "reviewer")
        assert result["summary"] == "A reviewer persona."

    def test_read_filename_field(self, project_root):
        _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        result = _k_mod.read_knight(project_root, "reviewer")
        assert result["filename"] == "reviewer.md"

    def test_read_group_field_root_is_empty_or_none(self, project_root):
        """Root-placed knight: group is "" (derive_group convention) or None."""
        _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        result = _k_mod.read_knight(project_root, "reviewer")
        assert result["group"] in ("", None)

    def test_read_group_field_subdir(self, project_root):
        _k_mod.create_knight(
            project_root, "reviewer", PERSONA_MD, group="default"
        )
        result = _k_mod.read_knight(project_root, "reviewer")
        assert result["group"] == "default"

    def test_read_body_field_contains_body_text(self, project_root):
        _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        result = _k_mod.read_knight(project_root, "reviewer")
        assert "# body text" in result["body"]

    def test_read_missing_returns_none(self, project_root):
        result = _k_mod.read_knight(project_root, "nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# delete_knight envelope gains deleted_at: None.
# ---------------------------------------------------------------------------


class TestDeleteKnightEnvelope:
    """``delete_knight`` envelope gains ``deleted_at: None`` per amendment A2."""

    def test_delete_envelope_includes_deleted_at_none(self, project_root):
        _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        result = _k_mod.delete_knight(project_root, "reviewer")
        assert "deleted_at" in result, (
            "amendment A2: file-backed delete envelope gains "
            "deleted_at: None (rename-based; no UTC stamp)."
        )
        assert result["deleted_at"] is None


# ---------------------------------------------------------------------------
# Validation — empty content, invalid frontmatter raise ValueError.
# ---------------------------------------------------------------------------


class TestCreateKnightValidation:
    """``create_knight`` validation routes through schemas + raises ValueError."""

    def test_create_empty_content_raises_value_error(self, project_root):
        with pytest.raises(ValueError):
            _k_mod.create_knight(project_root, "reviewer", "")

    def test_create_whitespace_content_raises_value_error(self, project_root):
        with pytest.raises(ValueError):
            _k_mod.create_knight(project_root, "reviewer", "   \n\n   ")

    def test_create_missing_frontmatter_raises_value_error(self, project_root):
        with pytest.raises(ValueError):
            _k_mod.create_knight(
                project_root, "reviewer", "no frontmatter just body"
            )

    def test_create_missing_required_field_raises_value_error(
        self, project_root
    ):
        bad = "---\nid: reviewer\ntitle: T\n---\n# body\n"  # no summary
        with pytest.raises(ValueError):
            _k_mod.create_knight(project_root, "reviewer", bad)


# ---------------------------------------------------------------------------
# list_knights — first-arg flip; returns list[dict].
# ---------------------------------------------------------------------------


class TestListKnightsProjectRoot:
    def test_list_takes_project_root(self, project_root):
        _k_mod.create_knight(project_root, "reviewer", PERSONA_MD)
        records = _k_mod.list_knights(project_root)
        assert isinstance(records, list)
        assert any(r["id"] == "reviewer" for r in records)

    def test_list_empty_when_dir_absent(self, tmp_path):
        records = _k_mod.list_knights(tmp_path)  # no .lore/knights
        assert records == []


# ---------------------------------------------------------------------------
# Internal reclassification — _find_knight present, find_knight gone.
# ---------------------------------------------------------------------------


class TestFindKnightReclassifiedInternal:
    """``find_knight`` renamed to ``_find_knight`` per amendment C4."""

    def test_find_knight_public_name_removed(self):
        assert not hasattr(_k_mod, "find_knight") or _k_mod.find_knight is not _k_mod.find_knight, (
            "find_knight must be removed from lore.knight public surface; "
            "use _find_knight or read_knight."
        )

    def test_underscore_find_knight_exists(self):
        assert hasattr(_k_mod, "_find_knight"), (
            "_find_knight (internal locator) must exist after C4 reclass."
        )
