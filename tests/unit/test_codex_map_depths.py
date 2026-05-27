"""Unit tests for `map_documents` symmetric-`depth` kwarg + conflict gate — G11 Red.

Plan: transient-public-api-facade-plan §G11.
Spec source: transient-public-api-facade-tech-spec §2 (Codex composition).

Today's signature (codex.py:202):

    map_documents(codex_dir, start_id, *, depth_out=1, depth_in=1, full=False)

G11 ADDS a new symmetric `depth` kwarg:

    map_documents(codex_dir, start_id, *, depth=None,
                  depth_out=1, depth_in=1, full=False)

Behaviour contract (Plan §G11 acceptance):

  - `depth=N` alone → traverses both directions to depth N.
  - `depth_in=N` alone → unchanged from today (no `depth` set).
  - `depth_out=N` alone → unchanged from today (no `depth` set).
  - `depth=N, depth_in=M` (together) → raises `ConflictingDepthFlags`.
  - `depth=N, depth_out=M` (together) → raises `ConflictingDepthFlags`.
  - FLAG #5 verify: passing ONLY directional flags (no `depth` set) does
    NOT raise.

`ConflictingDepthFlags` already exists at `lore.codex:11` (dormant — never
raised today). G11 first-activates it.

Every test in this module MUST fail until G11 Green lands.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lore.codex import ConflictingDepthFlags, map_documents


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_doc(
    codex_dir: Path,
    doc_id: str,
    *,
    related: list[str] | None = None,
) -> None:
    lines = [
        "---",
        f"id: {doc_id}",
        f"title: {doc_id.title()}",
        f"summary: Summary for {doc_id}.",
    ]
    if related is None:
        lines.append("related: []")
    else:
        lines.append("related:")
        for r in related:
            lines.append(f"  - {r}")
    lines.extend(["---", "", f"Body of {doc_id}.", ""])
    (codex_dir / f"{doc_id}.md").write_text("\n".join(lines))


@pytest.fixture()
def codex_graph(tmp_path: Path) -> Path:
    """Three-node chain: seed -> child -> grandchild.

    Returns the project_root (parent of .lore/) per amendment A1.
    """
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    _write_doc(codex_dir, "seed", related=["child"])
    _write_doc(codex_dir, "child", related=["grandchild"])
    _write_doc(codex_dir, "grandchild", related=[])
    return tmp_path


# ---------------------------------------------------------------------------
# `depth=N` alone — new symmetric kwarg works
# ---------------------------------------------------------------------------


class TestMapDocumentsDepthSymmetric:
    """`depth=N` alone traverses both directions with budget N."""

    def test_depth_one_returns_immediate_child(self, codex_graph: Path):
        """depth=1 from seed visits the direct outbound neighbour."""
        result = map_documents(codex_graph, "seed", depth=1)
        ids = [d["id"] for d in result]
        assert "child" in ids

    def test_depth_one_does_not_return_grandchild(self, codex_graph: Path):
        """depth=1 outbound stops at 1 hop — grandchild not included."""
        result = map_documents(codex_graph, "seed", depth=1)
        ids = [d["id"] for d in result]
        assert "grandchild" not in ids

    def test_depth_two_returns_grandchild(self, codex_graph: Path):
        """depth=2 outbound reaches 2 hops — grandchild present."""
        result = map_documents(codex_graph, "seed", depth=2)
        ids = [d["id"] for d in result]
        assert "grandchild" in ids

    def test_depth_zero_returns_empty(self, codex_graph: Path):
        """depth=0 — seed only, no neighbours collected."""
        result = map_documents(codex_graph, "seed", depth=0)
        assert result == []

    def test_depth_symmetric_uses_both_directions(self, codex_graph: Path):
        """depth=1 from grandchild traverses inbound to find child."""
        result = map_documents(codex_graph, "grandchild", depth=1)
        ids = [d["id"] for d in result]
        # Inbound BFS hop reaches `child`.
        assert "child" in ids


# ---------------------------------------------------------------------------
# `depth_in=N` / `depth_out=N` alone — unchanged from today (FLAG #5)
# ---------------------------------------------------------------------------


class TestMapDocumentsDirectionalAloneUnchanged:
    """FLAG #5: directional flags WITHOUT `depth` must NOT raise."""

    def test_depth_in_alone_does_not_raise(self, codex_graph: Path):
        """`map_documents(..., depth_in=N)` alone — no `ConflictingDepthFlags`."""
        try:
            result = map_documents(codex_graph, "grandchild", depth_in=2)
        except ConflictingDepthFlags as exc:  # pragma: no cover
            pytest.fail(
                f"depth_in alone must not raise ConflictingDepthFlags: {exc}"
            )
        assert isinstance(result, list)

    def test_depth_out_alone_does_not_raise(self, codex_graph: Path):
        """`map_documents(..., depth_out=N)` alone — no `ConflictingDepthFlags`."""
        try:
            result = map_documents(codex_graph, "seed", depth_out=2)
        except ConflictingDepthFlags as exc:  # pragma: no cover
            pytest.fail(
                f"depth_out alone must not raise ConflictingDepthFlags: {exc}"
            )
        assert isinstance(result, list)

    def test_depth_in_and_depth_out_together_alone_do_not_raise(
        self, codex_graph: Path
    ):
        """Both directional flags TOGETHER (no `depth`) — still no raise."""
        try:
            result = map_documents(
                codex_graph, "seed", depth_in=1, depth_out=2
            )
        except ConflictingDepthFlags as exc:  # pragma: no cover
            pytest.fail(
                f"depth_in + depth_out (no depth) must not raise: {exc}"
            )
        assert isinstance(result, list)

    def test_depth_out_alone_behaviour_matches_legacy(
        self, codex_graph: Path
    ):
        """depth_out=2 alone reaches grandchild (chain seed->child->grandchild)."""
        result = map_documents(codex_graph, "seed", depth_out=2)
        ids = [d["id"] for d in result]
        assert "grandchild" in ids

    def test_depth_in_alone_behaviour_matches_legacy(
        self, codex_graph: Path
    ):
        """depth_in=2 from grandchild reaches seed via inbound BFS."""
        result = map_documents(codex_graph, "grandchild", depth_in=2)
        ids = [d["id"] for d in result]
        assert "seed" in ids


# ---------------------------------------------------------------------------
# Conflict gate — `depth` + directional → ConflictingDepthFlags
# ---------------------------------------------------------------------------


class TestMapDocumentsConflictingDepthFlags:
    """`depth` combined with any directional flag raises `ConflictingDepthFlags`."""

    def test_depth_plus_depth_in_raises(self, codex_graph: Path):
        with pytest.raises(ConflictingDepthFlags):
            map_documents(codex_graph, "seed", depth=1, depth_in=1)

    def test_depth_plus_depth_out_raises(self, codex_graph: Path):
        with pytest.raises(ConflictingDepthFlags):
            map_documents(codex_graph, "seed", depth=1, depth_out=1)

    def test_depth_plus_both_directional_raises(self, codex_graph: Path):
        with pytest.raises(ConflictingDepthFlags):
            map_documents(
                codex_graph, "seed", depth=1, depth_in=1, depth_out=1
            )

    def test_conflicting_depth_flags_is_subclass_of_value_error(self):
        """`ConflictingDepthFlags` already subclasses ValueError (codex.py:11)."""
        assert issubclass(ConflictingDepthFlags, ValueError)

    def test_conflict_raises_before_disk_io(self, tmp_path: Path):
        """Conflict gate fires WITHOUT touching the codex directory.

        The check must short-circuit before `scan_codex` — passing a
        non-existent codex_dir is fine, the conflict still raises.
        """
        nonexistent = tmp_path / "no-such-codex-dir"
        with pytest.raises(ConflictingDepthFlags):
            map_documents(nonexistent, "seed", depth=1, depth_in=1)
