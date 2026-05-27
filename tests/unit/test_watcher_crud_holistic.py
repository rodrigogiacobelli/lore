"""Holistic CRUD sweep for ``lore.watcher`` — G16 Red.

Plan: ``transient-public-api-facade-plan`` §G16.
Amendment: ``transient-public-api-facade-create-stdz`` Sections A1, A2,
A4, A5, A6 + Section B (Watcher row) + Section F G16 step-list.

Pins the BREAKING contracts:

* First-arg flip — every callable takes ``project_root: Path`` instead of
  ``watchers_dir: Path``.
* ``read_watcher`` NEW — returns the 8-key dict ``{id, group, title,
  summary, filename, watch_target, interval, action}`` matching today's
  internal ``load_watcher`` shape.
* ``find_watcher`` + ``load_watcher`` reclassified internal
  (``_find_watcher`` / ``_load_watcher``); dropped from facade.
* ``delete_watcher`` envelope GAINS ``deleted_at: None`` per A2.
* Inline regex at ``watcher.py:80`` replaced by ``validate_name``
  (amendment A4 — patterns verified byte-identical).
* ``_validate_yaml`` raise type flipped from ``click.ClickException`` to
  ``ValueError`` (amendment Section E validation behaviour changes;
  finishes the G2 sweep into watcher).

Red phase — every test below MUST fail until G16 Green lands.
"""

from __future__ import annotations

import inspect
import textwrap

import pytest

import lore.watcher as _w_mod
from lore import api


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path):
    (tmp_path / ".lore" / "watchers").mkdir(parents=True)
    return tmp_path


WATCHER_YAML = textwrap.dedent(
    """\
    id: w1
    title: Watcher 1
    summary: A test watcher.
    watch_target: foo
    interval: 60
    action: bar
    """
)


# ---------------------------------------------------------------------------
# Facade __all__ — find_watcher + load_watcher dropped; read_watcher present.
# ---------------------------------------------------------------------------


class TestFacadeAllShape:
    def test_find_watcher_not_in_api_all(self):
        assert "find_watcher" not in api.__all__

    def test_load_watcher_not_in_api_all(self):
        assert "load_watcher" not in api.__all__

    def test_find_watcher_import_raises(self):
        with pytest.raises(ImportError):
            from lore.api import find_watcher  # noqa: F401

    def test_load_watcher_import_raises(self):
        with pytest.raises(ImportError):
            from lore.api import load_watcher  # noqa: F401

    def test_read_watcher_in_api_all(self):
        assert "read_watcher" in api.__all__

    def test_read_watcher_identity_reexport(self):
        assert api.read_watcher is _w_mod.read_watcher


# ---------------------------------------------------------------------------
# Signatures — project_root first; no watchers_dir parameter.
# ---------------------------------------------------------------------------


class TestWatcherSignaturesUseProjectRoot:
    @pytest.mark.parametrize(
        "fn_name",
        (
            "create_watcher",
            "read_watcher",
            "update_watcher",
            "delete_watcher",
            "list_watchers",
        ),
    )
    def test_first_positional_named_project_root(self, fn_name):
        fn = getattr(_w_mod, fn_name)
        params = list(inspect.signature(fn).parameters.values())
        assert params and params[0].name == "project_root", (
            f"{fn_name} first positional must be 'project_root' "
            f"(got {params[0].name if params else 'none'!r})."
        )

    @pytest.mark.parametrize(
        "fn_name",
        (
            "create_watcher",
            "read_watcher",
            "update_watcher",
            "delete_watcher",
            "list_watchers",
        ),
    )
    def test_no_watchers_dir_parameter(self, fn_name):
        fn = getattr(_w_mod, fn_name)
        assert "watchers_dir" not in inspect.signature(fn).parameters


# ---------------------------------------------------------------------------
# read_watcher — 8-key dict matching load_watcher shape.
# ---------------------------------------------------------------------------


class TestReadWatcherEightKeyDict:
    """``read_watcher(project_root, name)`` returns the 8-key dict."""

    def test_read_returns_dict(self, project_root):
        _w_mod.create_watcher(project_root, "w1", WATCHER_YAML)
        result = _w_mod.read_watcher(project_root, "w1")
        assert isinstance(result, dict)

    def test_read_has_eight_keys(self, project_root):
        _w_mod.create_watcher(project_root, "w1", WATCHER_YAML)
        result = _w_mod.read_watcher(project_root, "w1")
        assert set(result.keys()) == {
            "id",
            "group",
            "title",
            "summary",
            "filename",
            "watch_target",
            "interval",
            "action",
        }

    def test_read_field_values(self, project_root):
        _w_mod.create_watcher(project_root, "w1", WATCHER_YAML)
        result = _w_mod.read_watcher(project_root, "w1")
        assert result["id"] == "w1"
        assert result["title"] == "Watcher 1"
        assert result["summary"] == "A test watcher."
        assert result["filename"] == "w1.yaml"
        assert result["watch_target"] == "foo"
        assert result["interval"] == 60
        assert result["action"] == "bar"

    def test_read_missing_returns_none(self, project_root):
        assert _w_mod.read_watcher(project_root, "nope") is None

    def test_read_group_subdir(self, project_root):
        _w_mod.create_watcher(
            project_root, "w1", WATCHER_YAML, group="alerts"
        )
        result = _w_mod.read_watcher(project_root, "w1")
        assert result["group"] == "alerts"


# ---------------------------------------------------------------------------
# create_watcher envelope — {id, filename, group}; drops path.
# ---------------------------------------------------------------------------


class TestCreateWatcherEnvelope:
    def test_envelope_drops_path(self, project_root):
        result = _w_mod.create_watcher(project_root, "w1", WATCHER_YAML)
        assert "path" not in result, (
            "amendment B Watcher row: drop 'path' (separation-of-concerns)."
        )

    def test_envelope_keys(self, project_root):
        result = _w_mod.create_watcher(project_root, "w1", WATCHER_YAML)
        assert set(result.keys()) == {"id", "filename", "group"}


# ---------------------------------------------------------------------------
# delete_watcher envelope gains deleted_at: None.
# ---------------------------------------------------------------------------


class TestDeleteWatcherEnvelope:
    def test_delete_envelope_gains_deleted_at(self, project_root):
        _w_mod.create_watcher(project_root, "w1", WATCHER_YAML)
        result = _w_mod.delete_watcher(project_root, "w1")
        assert "deleted_at" in result, (
            "amendment A2: file-backed delete envelope gains deleted_at: None."
        )
        assert result["deleted_at"] is None


# ---------------------------------------------------------------------------
# Inline regex equivalence — validate_name swap (amendment A4).
#
# Patterns verified byte-identical at watcher.py:80 vs validators.py:15.
# After the swap, accept/reject behaviour on this corpus MUST be unchanged.
# ---------------------------------------------------------------------------


ACCEPT_CORPUS = (
    "w1",
    "alpha",
    "alpha-beta",
    "alpha_beta",
    "A",
    "0name",
    "x" * 64,
)

REJECT_CORPUS = (
    "",
    "-leading-dash",
    "_leading_underscore",
    "has space",
    "weird.name",
    "name!bang",
    "/slash",
    "back\\slash",
)


@pytest.mark.parametrize("name", ACCEPT_CORPUS)
def test_create_watcher_accepts_validate_name_corpus(project_root, name):
    """Every legal name accepted by validate_name passes create_watcher."""
    result = _w_mod.create_watcher(project_root, name, WATCHER_YAML)
    assert result["id"] == name


@pytest.mark.parametrize("name", REJECT_CORPUS)
def test_create_watcher_rejects_validate_name_corpus(project_root, name):
    """Every illegal name rejected by validate_name raises ValueError."""
    with pytest.raises(ValueError):
        _w_mod.create_watcher(project_root, name, WATCHER_YAML)


def test_create_watcher_uses_validate_name_not_inline_regex():
    """``re.match`` inline regex at watcher.py:80 must be gone post-G16."""
    import inspect as _inspect

    source = _inspect.getsource(_w_mod.create_watcher)
    assert "re.match" not in source, (
        "amendment A4: inline regex replaced by validators.validate_name."
    )


# ---------------------------------------------------------------------------
# _validate_yaml raises ValueError (not click.ClickException) — ADR-011.
# ---------------------------------------------------------------------------


class TestValidateYamlRaiseType:
    """``_validate_yaml`` raises ``ValueError`` post-G16 (was Click)."""

    def test_validate_yaml_raises_value_error_on_issues(self, monkeypatch):
        import lore.schemas as _schemas

        issue = _schemas.SchemaIssue(
            rule="required",
            pointer="/",
            message="Missing required property 'title'.",
        )
        monkeypatch.setattr(_schemas, "validate_entity", lambda k, d: [issue])
        if hasattr(_w_mod, "validate_entity"):
            monkeypatch.setattr(
                _w_mod, "validate_entity", lambda k, d: [issue]
            )

        with pytest.raises(ValueError):
            _w_mod._validate_yaml({"id": "w"})

    def test_validate_yaml_does_not_raise_click_exception(self, monkeypatch):
        import click as _click
        import lore.schemas as _schemas

        issue = _schemas.SchemaIssue(
            rule="required",
            pointer="/",
            message="Missing required property 'title'.",
        )
        monkeypatch.setattr(_schemas, "validate_entity", lambda k, d: [issue])
        if hasattr(_w_mod, "validate_entity"):
            monkeypatch.setattr(
                _w_mod, "validate_entity", lambda k, d: [issue]
            )

        with pytest.raises(ValueError):
            try:
                _w_mod._validate_yaml({"id": "w"})
            except _click.ClickException:  # pragma: no cover — must not match
                pytest.fail(
                    "watcher._validate_yaml raised click.ClickException; "
                    "ADR-011 + amendment require plain ValueError."
                )


# ---------------------------------------------------------------------------
# Internal reclassification — _find_watcher, _load_watcher exist.
# ---------------------------------------------------------------------------


class TestWatcherInternalReclassification:
    def test_underscore_find_watcher_exists(self):
        assert hasattr(_w_mod, "_find_watcher"), (
            "_find_watcher must exist after C4 reclass."
        )

    def test_underscore_load_watcher_exists(self):
        assert hasattr(_w_mod, "_load_watcher"), (
            "_load_watcher must exist after C4 reclass."
        )
