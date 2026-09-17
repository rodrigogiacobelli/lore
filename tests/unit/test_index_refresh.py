"""Unit tests for the rendered index and the refresh that keeps it current.

Spec: codex-index-spec (``lore codex show codex-index-spec``) — Part 4, the
``_load_render`` and ``_refresh`` rows.

The render is a cache (N3): a missing, corrupt or wrong-version file is treated
as absent and rebuilt rather than raised on (D14), and the rebuild goes through
``safewrite.atomic_write_text`` so a concurrent reader never sees half of it
(D13, N4).
"""

from __future__ import annotations

import json
import os

import pytest

from lore.index import _codex_fingerprint, _load_render, _refresh
from lore.paths import index_rendered_path


def _render_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n"


def _write_render(project, payload: dict) -> None:
    path = index_rendered_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_text(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# _load_render
# ---------------------------------------------------------------------------


def test_an_absent_render_loads_as_nothing(tree):
    assert _load_render(tree.lore) is None


def test_an_unparseable_render_loads_as_nothing(tree):
    path = index_rendered_path(tree.lore)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")

    assert _load_render(tree.lore) is None


def test_a_render_of_the_wrong_version_loads_as_nothing(tree):
    _write_render(
        tree.lore,
        {"version": 2, "codex_fingerprint": "0" * 64, "clusters": []},
    )

    assert _load_render(tree.lore) is None


def test_a_render_missing_its_clusters_loads_as_nothing(tree):
    """A cache that can fail a command is not a cache (D14)."""
    _write_render(tree.lore, {"version": 1, "codex_fingerprint": "0" * 64})

    assert _load_render(tree.lore) is None


def test_a_well_formed_render_loads_as_its_payload(tree):
    payload = {"version": 1, "codex_fingerprint": "a" * 64, "clusters": []}
    _write_render(tree.lore, payload)

    assert _load_render(tree.lore) == payload


# ---------------------------------------------------------------------------
# _refresh
# ---------------------------------------------------------------------------


def test_an_unchanged_codex_leaves_the_render_untouched(tree):
    """The fast path: one ``stat`` per document and no write (D11, N6)."""
    tree.doc(tree.lore, "one")
    _refresh(tree.lore)
    path = index_rendered_path(tree.lore)
    os.utime(path, ns=(0, 0))

    _refresh(tree.lore)

    assert path.stat().st_mtime_ns == 0


def test_a_changed_codex_rewrites_the_render_with_the_new_fingerprint(tree):
    tree.doc(tree.lore, "one")
    _refresh(tree.lore)
    path = index_rendered_path(tree.lore)
    os.utime(path, ns=(0, 0))

    tree.doc(tree.lore, "two")
    payload = _refresh(tree.lore)

    assert path.stat().st_mtime_ns != 0
    assert payload["codex_fingerprint"] == _codex_fingerprint(tree.lore)
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_a_missing_render_is_written(tree):
    tree.doc(tree.lore, "one")
    path = index_rendered_path(tree.lore)

    payload = _refresh(tree.lore)

    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert [c["hub"] for c in payload["clusters"]] == ["one"]


def test_a_corrupt_render_is_rebuilt_rather_than_raised_on(tree):
    tree.doc(tree.lore, "one")
    path = index_rendered_path(tree.lore)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")

    payload = _refresh(tree.lore)

    assert payload["codex_fingerprint"] == _codex_fingerprint(tree.lore)
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_the_render_is_written_as_indented_json_with_a_trailing_newline(tree):
    tree.doc(tree.lore, "one")

    payload = _refresh(tree.lore)

    assert index_rendered_path(tree.lore).read_text(encoding="utf-8") == _render_text(
        payload
    )


def test_a_symlink_at_the_render_path_is_refused(tree, tmp_path):
    """``safewrite`` owns that refusal; the index writes no second copy (D13)."""
    tree.doc(tree.lore, "one")
    path = index_rendered_path(tree.lore)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(tmp_path / "elsewhere.json")

    with pytest.raises(ValueError):
        _refresh(tree.lore)
