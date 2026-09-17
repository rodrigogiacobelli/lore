"""Unit tests for the codex index's two hashes.

Spec: codex-index-spec (``lore codex show codex-index-spec``) — Part 4, the
``_cluster_digest`` and ``_codex_fingerprint`` rows, plus ``_document_digest``
which C3 names alongside them.

The cluster digest answers "have these documents changed since the summary was
written" (D10) and the codex fingerprint answers "has anything at all changed
since the render" (D11). The first reads bytes; the second must not.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from lore.index import _cluster_digest, _codex_fingerprint, _document_digest

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _paths_by_id(project: Path, *doc_ids: str) -> dict[str, Path]:
    """Map each id to the file the ``tree`` fixture wrote for it."""
    codex_root = project / ".lore" / "codex"
    return {doc_id: codex_root / f"{doc_id}.md" for doc_id in doc_ids}


def _backdate(path: Path, nanoseconds: int) -> None:
    """Pin a file's mtime, so a fingerprint assertion cannot race the clock."""
    os.utime(path, ns=(nanoseconds, nanoseconds))


# ---------------------------------------------------------------------------
# _document_digest
# ---------------------------------------------------------------------------


def test_a_document_digest_is_the_sha256_of_the_file_bytes(tree):
    path = tree.doc(tree.lore, "one")

    assert _document_digest(path) == hashlib.sha256(path.read_bytes()).hexdigest()
    assert _HEX64.match(_document_digest(path))


def test_two_files_with_identical_bytes_share_a_document_digest(tree):
    first = tree.doc(tree.lore, "one")
    second = tree.lore / ".lore" / "codex" / "copy.md"
    second.write_bytes(first.read_bytes())

    assert _document_digest(first) == _document_digest(second)


# ---------------------------------------------------------------------------
# _cluster_digest
# ---------------------------------------------------------------------------


def test_a_cluster_digest_is_sixty_four_lowercase_hex_characters(tree):
    tree.doc(tree.lore, "one")
    tree.doc(tree.lore, "two")
    paths = _paths_by_id(tree.lore, "one", "two")

    assert _HEX64.match(_cluster_digest(["one", "two"], paths))


def test_identical_inputs_give_an_identical_cluster_digest(tree):
    tree.doc(tree.lore, "one")
    tree.doc(tree.lore, "two")
    paths = _paths_by_id(tree.lore, "one", "two")

    assert _cluster_digest(["one", "two"], paths) == _cluster_digest(
        ["one", "two"], paths
    )


def test_changing_one_members_bytes_changes_the_cluster_digest(tree):
    tree.doc(tree.lore, "one")
    tree.doc(tree.lore, "two")
    paths = _paths_by_id(tree.lore, "one", "two")
    before = _cluster_digest(["one", "two"], paths)

    tree.doc(tree.lore, "two", body="A different body entirely.")

    assert _cluster_digest(["one", "two"], paths) != before


def test_adding_a_member_changes_the_cluster_digest(tree):
    tree.doc(tree.lore, "one")
    tree.doc(tree.lore, "two")
    tree.doc(tree.lore, "three")
    paths = _paths_by_id(tree.lore, "one", "two", "three")

    assert _cluster_digest(["one", "two", "three"], paths) != _cluster_digest(
        ["one", "two"], paths
    )


def test_removing_a_member_changes_the_cluster_digest(tree):
    tree.doc(tree.lore, "one")
    tree.doc(tree.lore, "two")
    paths = _paths_by_id(tree.lore, "one", "two")

    assert _cluster_digest(["one"], paths) != _cluster_digest(["one", "two"], paths)


def test_changing_a_document_outside_the_cluster_leaves_its_digest_alone(tree):
    """The precision R6 asks for: a cluster drifts on its own members only."""
    tree.doc(tree.lore, "one")
    tree.doc(tree.lore, "two")
    tree.doc(tree.lore, "elsewhere")
    paths = _paths_by_id(tree.lore, "one", "two", "elsewhere")
    before = _cluster_digest(["one", "two"], paths)

    tree.doc(tree.lore, "elsewhere", body="Rewritten from top to bottom.")

    assert _cluster_digest(["one", "two"], paths) == before


def test_reordering_the_members_list_leaves_the_cluster_digest_alone(tree):
    tree.doc(tree.lore, "one")
    tree.doc(tree.lore, "two")
    tree.doc(tree.lore, "three")
    paths = _paths_by_id(tree.lore, "one", "two", "three")

    assert _cluster_digest(["three", "one", "two"], paths) == _cluster_digest(
        ["one", "two", "three"], paths
    )


def test_moving_a_members_file_without_changing_its_bytes_leaves_the_digest_alone(
    tree,
):
    """A member changing group refreshes the render, not the summary (D10)."""
    tree.doc(tree.lore, "one")
    tree.doc(tree.lore, "two")
    paths = _paths_by_id(tree.lore, "one", "two")
    before = _cluster_digest(["one", "two"], paths)

    moved = tree.lore / ".lore" / "codex" / "standards" / "two.md"
    moved.parent.mkdir(parents=True, exist_ok=True)
    paths["two"].rename(moved)
    paths["two"] = moved

    assert _cluster_digest(["one", "two"], paths) == before


# ---------------------------------------------------------------------------
# _codex_fingerprint
# ---------------------------------------------------------------------------


def test_a_codex_fingerprint_is_sixty_four_lowercase_hex_characters(tree):
    tree.doc(tree.lore, "one")

    assert _HEX64.match(_codex_fingerprint(tree.lore))


def test_a_codex_fingerprint_is_unchanged_on_an_untouched_tree(tree):
    tree.doc(tree.lore, "one")
    tree.doc(tree.lore, "two")

    assert _codex_fingerprint(tree.lore) == _codex_fingerprint(tree.lore)


def test_adding_a_document_changes_the_codex_fingerprint(tree):
    tree.doc(tree.lore, "one")
    before = _codex_fingerprint(tree.lore)

    tree.doc(tree.lore, "two")

    assert _codex_fingerprint(tree.lore) != before


def test_deleting_a_document_changes_the_codex_fingerprint(tree):
    tree.doc(tree.lore, "one")
    path = tree.doc(tree.lore, "two")
    before = _codex_fingerprint(tree.lore)

    path.unlink()

    assert _codex_fingerprint(tree.lore) != before


def test_editing_a_document_changes_the_codex_fingerprint(tree):
    path = tree.doc(tree.lore, "one")
    _backdate(path, 1_000_000_000_000_000_000)
    before = _codex_fingerprint(tree.lore)

    tree.doc(tree.lore, "one", body="A body of a plainly different length.")
    _backdate(path, 1_000_000_000_000_000_000)

    assert _codex_fingerprint(tree.lore) != before


def test_renaming_a_document_changes_the_codex_fingerprint(tree):
    path = tree.doc(tree.lore, "one")
    before = _codex_fingerprint(tree.lore)

    path.rename(path.with_name("renamed.md"))

    assert _codex_fingerprint(tree.lore) != before


def test_touching_a_document_changes_the_codex_fingerprint(tree):
    """Size alone would miss an edit of equal length; the mtime catches it."""
    path = tree.doc(tree.lore, "one")
    _backdate(path, 1_000_000_000_000_000_000)
    before = _codex_fingerprint(tree.lore)

    _backdate(path, 1_500_000_000_000_000_000)

    assert _codex_fingerprint(tree.lore) != before


def test_a_transient_document_is_outside_the_codex_fingerprint(tree):
    """Otherwise every `lore health` run would invalidate the index (D6)."""
    tree.doc(tree.lore, "one")
    before = _codex_fingerprint(tree.lore)

    tree.doc(tree.lore, "report", group="transient")

    assert _codex_fingerprint(tree.lore) == before


def test_a_sources_document_is_outside_the_codex_fingerprint(tree):
    tree.doc(tree.lore, "one")
    before = _codex_fingerprint(tree.lore)

    tree.doc(tree.lore, "raw", group="sources")

    assert _codex_fingerprint(tree.lore) == before


def test_the_codex_fingerprint_reads_no_file_content(tree, monkeypatch):
    """N6: one ``stat`` per document and no read — the fast path's whole point.

    The patch counts calls and delegates; it asserts on the count, never on a
    return value, and no real code path is stopped from running.
    """
    tree.doc(tree.lore, "one")
    tree.doc(tree.lore, "two")
    reads: list[str] = []

    for method in ("read_bytes", "read_text", "open"):
        original = getattr(Path, method)

        def counted(self, *args, _original=original, _method=method, **kwargs):
            reads.append(_method)
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(Path, method, counted)

    _codex_fingerprint(tree.lore)

    assert reads == []
