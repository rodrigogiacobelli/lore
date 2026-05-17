"""Unit tests for the refactored `lore.codex.map_documents`.

Spec:
- codex-map-us-1 — default neighbourhood scan returns list-shape table.
- codex-map-us-8 — seed exclusion + cross-direction dedupe.
- codex-map-us-9 — unknown seed + empty neighbourhood semantics.

Tech spec: codex-map-tech-spec.

These tests target the NEW signature:

    map_documents(codex_dir, start_id, *, depth_out=1, depth_in=1, full=False)

The legacy positional `depth` parameter is removed. The function returns
a list of records with keys {id, group, title, summary} in default mode
(seed always excluded, sorted alphabetically by id, deduplicated by id).
It returns None when start_id is not in the codex index, and [] when
the seed exists but has no neighbours in the active direction.
"""

from pathlib import Path

from lore.codex import map_documents


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_doc(
    codex_dir: Path,
    doc_id: str,
    *,
    related: list[str] | None = None,
    omit_related: bool = False,
    body: str | None = None,
    subdir: str | None = None,
) -> Path:
    """Write a minimal valid codex doc and return its path.

    `subdir` (slash-separated) is created under codex_dir; the doc is
    placed there. Used to test the GROUP column / group derivation.
    """
    body_text = body if body is not None else f"Body of {doc_id}."
    lines = [
        "---",
        f"id: {doc_id}",
        f"title: {doc_id.replace('-', ' ').title()}",
        f"summary: Summary for {doc_id}.",
    ]
    if not omit_related:
        if related is None:
            lines.append("related: []")
        else:
            lines.append("related:")
            for r in related:
                lines.append(f"  - {r}")
    lines.extend(["---", "", body_text, ""])
    content = "\n".join(lines)
    target_dir = codex_dir
    if subdir:
        target_dir = codex_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
    filepath = target_dir / f"{doc_id}.md"
    filepath.write_text(content)
    return filepath


def _make_codex_dir(tmp_path: Path) -> Path:
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    return codex_dir


# ===========================================================================
# US-001 — default neighbourhood scan
# ===========================================================================


# Unit — bidirectional default returns both directions
def test_map_documents_bidirectional_default_returns_both_directions(tmp_path):
    """seed -> child-a (outbound), parent-b -> seed (inbound).

    Default kwargs (depth_out=1, depth_in=1, full=False) returns both
    child-a and parent-b in alphabetical order by id, with seed excluded.
    """
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["child-a"])
    _write_doc(codex_dir, "child-a", related=[])
    _write_doc(codex_dir, "parent-b", related=["seed"])

    result = map_documents(codex_dir, "seed")

    assert result is not None
    ids = [r["id"] for r in result]
    assert ids == ["child-a", "parent-b"]


# Unit — default-mode record shape
def test_map_documents_default_mode_records_have_four_keys(tmp_path):
    """Each record has exactly {id, group, title, summary} — no body, no related."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["child-a"])
    _write_doc(codex_dir, "child-a", related=[])

    result = map_documents(codex_dir, "seed")

    assert result is not None
    assert len(result) == 1
    record = result[0]
    assert set(record.keys()) == {"id", "group", "title", "summary"}
    assert "body" not in record
    assert "related" not in record


# Unit — alphabetical sort regardless of BFS visitation order
def test_map_documents_result_sorted_alphabetically_by_id(tmp_path):
    """Seed with three outbound neighbours zebra/apple/mango at depth 1.

    Result ids must come out ["apple", "mango", "zebra"] regardless of
    BFS visitation order.
    """
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["zebra", "apple", "mango"])
    _write_doc(codex_dir, "zebra", related=[])
    _write_doc(codex_dir, "apple", related=[])
    _write_doc(codex_dir, "mango", related=[])

    result = map_documents(codex_dir, "seed")

    assert result is not None
    ids = [r["id"] for r in result]
    assert ids == ["apple", "mango", "zebra"]


# Unit — GROUP derived from path
def test_map_documents_group_derived_from_path(tmp_path):
    """Neighbour under .lore/codex/foo/bar/ reports group="foo/bar"."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["neighbour"], subdir="foo/bar")
    _write_doc(codex_dir, "neighbour", related=[], subdir="foo/bar")

    result = map_documents(codex_dir, "seed")

    assert result is not None
    assert len(result) == 1
    assert result[0]["group"] == "foo/bar"


# ===========================================================================
# US-008 — seed exclusion + cross-direction dedupe
# ===========================================================================


# Unit — seed with frontmatter self-loop is still excluded
def test_map_documents_seed_never_in_result(tmp_path):
    """Seed with related:[seed, child-a] — result excludes seed."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["seed", "child-a"])
    _write_doc(codex_dir, "child-a", related=[])

    result = map_documents(codex_dir, "seed")

    assert result is not None
    ids = [r["id"] for r in result]
    assert "seed" not in ids


# Unit — cross-direction dedupe in default mode
def test_map_documents_dedupes_cross_direction_neighbour(tmp_path):
    """Mutual citation seed <-> shared.

    map_documents(..., depth_out=1, depth_in=1) returns shared exactly once.
    """
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["shared"])
    _write_doc(codex_dir, "shared", related=["seed"])

    result = map_documents(codex_dir, "seed", depth_out=1, depth_in=1)

    assert result is not None
    ids = [r["id"] for r in result]
    assert ids.count("shared") == 1
    assert ids == ["shared"]


# Unit — two inbound paths to a shared grandparent deduped
def test_map_documents_dedupe_across_two_inbound_paths(tmp_path):
    """parent-a, parent-b cite seed; grandparent-c cites both parents.

    With depth_in=2, depth_out=0, grandparent-c appears exactly once.
    """
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=[])
    _write_doc(codex_dir, "parent-a", related=["seed"])
    _write_doc(codex_dir, "parent-b", related=["seed"])
    _write_doc(codex_dir, "grandparent-c", related=["parent-a", "parent-b"])

    result = map_documents(codex_dir, "seed", depth_out=0, depth_in=2)

    assert result is not None
    ids = [r["id"] for r in result]
    assert ids.count("grandparent-c") == 1
    # parent-a and parent-b also reachable inbound at depth 1
    assert set(ids) == {"parent-a", "parent-b", "grandparent-c"}


# Unit — dedupe under full=True
def test_map_documents_dedupe_full_mode_cross_direction(tmp_path):
    """Mutual citation seed <-> shared with full=True returns one record per id."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["shared"])
    _write_doc(codex_dir, "shared", related=["seed"])

    result = map_documents(codex_dir, "seed", depth_out=1, depth_in=1, full=True)

    assert result is not None
    ids = [r["id"] for r in result]
    assert ids == ["shared"]


# ===========================================================================
# US-009 — unknown seed + empty neighbourhood
# ===========================================================================


# Unit — None for unknown seed
def test_map_documents_returns_none_for_unknown_seed(tmp_path):
    """Unknown seed -> None (preserving today's contract)."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=[])

    result = map_documents(codex_dir, "does-not-exist")

    assert result is None


# Unit — empty list when seed exists but has no neighbours
def test_map_documents_returns_empty_list_when_no_neighbours(tmp_path):
    """Isolated seed with no related and no citers -> [] (not None)."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=[])

    result = map_documents(codex_dir, "seed")

    assert result is not None  # specifically NOT None
    assert result == []


# Unit — depth 0 in both directions returns empty list
def test_map_documents_depth_0_returns_empty_list(tmp_path):
    """Fixture with neighbours present; depth_out=0, depth_in=0 -> []."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["child-a"])
    _write_doc(codex_dir, "child-a", related=[])
    _write_doc(codex_dir, "parent-b", related=["seed"])

    result = map_documents(codex_dir, "seed", depth_out=0, depth_in=0)

    assert result is not None  # seed exists -> [] not None
    assert result == []


# ===========================================================================
# CLI handler unit tests (US-009 — pinned error wording)
# ===========================================================================


# Unit — CLI handler exits 1 with pinned text-mode message for unknown seed
def test_codex_map_unknown_seed_exits_one_with_pinned_message(tmp_path, monkeypatch):
    """CliRunner-driven CLI handler test.

    Click 8.3 removed mix_stderr=False — use result.stderr separately.
    """
    from click.testing import CliRunner
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    runner = CliRunner()
    result = runner.invoke(main, ["codex", "map", "does-not-exist"])

    assert result.exit_code == 1
    assert 'Document "does-not-exist" not found' in result.stderr


# Unit — CLI handler emits JSON error envelope on stderr for unknown seed
def test_codex_map_unknown_seed_json_envelope_uses_error_key(tmp_path, monkeypatch):
    """`lore --json codex map <missing>` emits {"error": ...} to stderr, exit 1."""
    import json
    from click.testing import CliRunner
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    runner = CliRunner()
    result = runner.invoke(main, ["--json", "codex", "map", "does-not-exist"])

    assert result.exit_code == 1
    parsed = json.loads(result.stderr.strip())
    assert parsed == {"error": 'Document "does-not-exist" not found'}


# ===========================================================================
# US-002 — Outbound-only deep walk via --depth-out (unit / map_documents)
# ===========================================================================


# Unit — outbound-only with depth_in=0
# eager-impl from G1; locking in
def test_map_documents_outbound_only_when_depth_in_0(tmp_path):
    """seed -> a -> b and parent -> seed; depth_out=1, depth_in=0 -> ["a"]."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["a"])
    _write_doc(codex_dir, "a", related=["b"])
    _write_doc(codex_dir, "b", related=[])
    _write_doc(codex_dir, "parent", related=["seed"])

    result = map_documents(codex_dir, "seed", depth_out=1, depth_in=0)

    assert result is not None
    ids = [r["id"] for r in result]
    assert ids == ["a"]


# Unit — depth_in=0 excludes inbound at any depth_out
# eager-impl from G1; locking in
def test_map_documents_depth_in_0_excludes_inbound_at_any_depth_out(tmp_path):
    """One inbound parent + 3-hop outbound chain; depth_out=5, depth_in=0.

    Inbound parent's id is NOT in returned ids regardless of large outbound budget.
    """
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["a"])
    _write_doc(codex_dir, "a", related=["b"])
    _write_doc(codex_dir, "b", related=["c"])
    _write_doc(codex_dir, "c", related=[])
    _write_doc(codex_dir, "parent", related=["seed"])

    result = map_documents(codex_dir, "seed", depth_out=5, depth_in=0)

    assert result is not None
    ids = [r["id"] for r in result]
    assert "parent" not in ids
    assert set(ids) == {"a", "b", "c"}


# Unit — depth_out=2 walks two outbound hops, excludes depth-3 child
# eager-impl from G1; locking in
def test_map_documents_depth_out_2_includes_depth_2_chain(tmp_path):
    """seed -> a -> b -> c; depth_out=2, depth_in=0 -> exactly ["a", "b"]."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["a"])
    _write_doc(codex_dir, "a", related=["b"])
    _write_doc(codex_dir, "b", related=["c"])
    _write_doc(codex_dir, "c", related=[])

    result = map_documents(codex_dir, "seed", depth_out=2, depth_in=0)

    assert result is not None
    ids = [r["id"] for r in result]
    assert ids == ["a", "b"]


# Unit — negative depth_out raises ValueError before I/O
# eager-impl from G1; locking in
def test_map_documents_negative_depth_out_raises_valueerror(tmp_path):
    """depth_out=-1 raises ValueError before any file I/O."""
    import pytest as _pytest

    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=[])

    with _pytest.raises(ValueError):
        map_documents(codex_dir, "seed", depth_out=-1, depth_in=0)


# ===========================================================================
# US-003 — Inbound-only backlink scan via --depth-in (unit / map_documents)
# ===========================================================================


# Unit — inbound-only with depth_out=0
# eager-impl from G1; locking in
def test_map_documents_inbound_only_when_depth_out_0(tmp_path):
    """seed -> outbound-x and cite-a -> seed; depth_out=0, depth_in=1 -> ["cite-a"]."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["outbound-x"])
    _write_doc(codex_dir, "outbound-x", related=[])
    _write_doc(codex_dir, "cite-a", related=["seed"])

    result = map_documents(codex_dir, "seed", depth_out=0, depth_in=1)

    assert result is not None
    ids = [r["id"] for r in result]
    assert ids == ["cite-a"]


# Unit — depth_out=0 excludes outbound at any depth_in
# eager-impl from G1; locking in
def test_map_documents_depth_out_0_excludes_outbound_at_any_depth_in(tmp_path):
    """One outbound child + 3-hop inbound chain; depth_out=0, depth_in=5.

    Outbound child's id is NOT in returned ids.
    """
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["child"])
    _write_doc(codex_dir, "child", related=[])
    _write_doc(codex_dir, "parent-1", related=["seed"])
    _write_doc(codex_dir, "parent-2", related=["parent-1"])
    _write_doc(codex_dir, "parent-3", related=["parent-2"])

    result = map_documents(codex_dir, "seed", depth_out=0, depth_in=5)

    assert result is not None
    ids = [r["id"] for r in result]
    assert "child" not in ids
    assert set(ids) == {"parent-1", "parent-2", "parent-3"}


# Unit — negative depth_in raises ValueError before I/O
# eager-impl from G1; locking in
def test_map_documents_negative_depth_in_raises_valueerror(tmp_path):
    """depth_in=-1 raises ValueError before any file I/O."""
    import pytest as _pytest

    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=[])

    with _pytest.raises(ValueError):
        map_documents(codex_dir, "seed", depth_out=0, depth_in=-1)


# ===========================================================================
# US-004 — Symmetric --depth shortcut and conflict error (unit)
# ===========================================================================


# Pinned conflict message — must match cli.py and the PRD byte-for-byte.
_CONFLICT_MSG = (
    "--depth cannot be combined with --depth-in or --depth-out. "
    "Use --depth for symmetric traversal, or --depth-in and/or "
    "--depth-out for directional traversal."
)


# Unit — handler raises UsageError when --depth combined with --depth-out
# eager-impl from G1; locking in
def test_codex_map_handler_raises_usage_error_when_depth_combined_with_depth_out(
    tmp_path, monkeypatch
):
    """`--depth 2 --depth-out 1` -> UsageError, no map_documents call."""
    import click
    from click.testing import CliRunner
    from lore.cli import main
    from lore import codex as codex_module

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    calls: list = []

    def _spy(*args, **kwargs):
        calls.append((args, kwargs))
        return []

    monkeypatch.setattr(codex_module, "map_documents", _spy)

    runner = CliRunner()
    result = runner.invoke(
        main, ["codex", "map", "seed", "--depth", "2", "--depth-out", "1"]
    )

    assert result.exit_code == 2
    assert calls == []
    # Click writes the UsageError to stderr prefixed with "Error: ".
    assert f"Error: {_CONFLICT_MSG}" in result.stderr
    # Underlying exception is click.UsageError when caught.
    if result.exception is not None and not isinstance(result.exception, SystemExit):
        assert isinstance(result.exception, click.UsageError)
        assert result.exception.message == _CONFLICT_MSG


# Unit — handler raises UsageError when --depth combined with --depth-in
# eager-impl from G1; locking in
def test_codex_map_handler_raises_usage_error_when_depth_combined_with_depth_in(
    tmp_path, monkeypatch
):
    """`--depth 2 --depth-in 1` -> UsageError, no map_documents call."""
    import click
    from click.testing import CliRunner
    from lore.cli import main
    from lore import codex as codex_module

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    calls: list = []

    def _spy(*args, **kwargs):
        calls.append((args, kwargs))
        return []

    monkeypatch.setattr(codex_module, "map_documents", _spy)

    runner = CliRunner()
    result = runner.invoke(
        main, ["codex", "map", "seed", "--depth", "2", "--depth-in", "1"]
    )

    assert result.exit_code == 2
    assert calls == []
    assert f"Error: {_CONFLICT_MSG}" in result.stderr
    if result.exception is not None and not isinstance(result.exception, SystemExit):
        assert isinstance(result.exception, click.UsageError)
        assert result.exception.message == _CONFLICT_MSG


# Unit — handler accepts --depth-in and --depth-out together
# eager-impl from G1; locking in
def test_codex_map_handler_accepts_depth_in_and_depth_out_together(
    tmp_path, monkeypatch
):
    """`--depth-in 1 --depth-out 2` -> map_documents called with depth_in=1, depth_out=2."""
    from click.testing import CliRunner
    from lore.cli import main
    from lore import codex as codex_module

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    captured: dict = {}

    def _spy(codex_dir, start_id, *, depth_out, depth_in, full=False):
        captured["depth_out"] = depth_out
        captured["depth_in"] = depth_in
        captured["start_id"] = start_id
        return []

    monkeypatch.setattr(codex_module, "map_documents", _spy)

    runner = CliRunner()
    result = runner.invoke(
        main, ["codex", "map", "seed", "--depth-in", "1", "--depth-out", "2"]
    )

    assert result.exit_code == 0, result.stderr
    assert captured["depth_out"] == 2
    assert captured["depth_in"] == 1


# Unit — `--depth` alone folds to symmetric budgets
# eager-impl from G1; locking in
def test_codex_map_handler_depth_alone_sets_symmetric_budgets(tmp_path, monkeypatch):
    """`--depth 3` -> map_documents called with depth_out=3, depth_in=3."""
    from click.testing import CliRunner
    from lore.cli import main
    from lore import codex as codex_module

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    captured: dict = {}

    def _spy(codex_dir, start_id, *, depth_out, depth_in, full=False):
        captured["depth_out"] = depth_out
        captured["depth_in"] = depth_in
        return []

    monkeypatch.setattr(codex_module, "map_documents", _spy)

    runner = CliRunner()
    result = runner.invoke(main, ["codex", "map", "seed", "--depth", "3"])

    assert result.exit_code == 0, result.stderr
    assert captured["depth_out"] == 3
    assert captured["depth_in"] == 3


# Unit — ConflictingDepthFlags is a ValueError subclass importable from lore.codex
# NOT eager — class does not exist yet, this test should FAIL.
def test_conflicting_depth_flags_is_valueerror_subclass():
    """`lore.codex.ConflictingDepthFlags` exists and subclasses ValueError."""
    from lore.codex import ConflictingDepthFlags

    assert issubclass(ConflictingDepthFlags, ValueError)


# ===========================================================================
# US-005 — Full-body bidirectional dump via --full (unit / map_documents)
# ===========================================================================


# Unit — full-mode record shape: six keys
# eager-impl from G1/G2; locking in
def test_map_documents_full_mode_records_have_six_keys(tmp_path):
    """seed -> a; full=True -> each record has {id, title, summary, group, related, body}."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["a"])
    _write_doc(codex_dir, "a", related=[])

    result = map_documents(codex_dir, "seed", depth_out=1, depth_in=0, full=True)

    assert result is not None
    assert len(result) == 1
    record = result[0]
    assert set(record.keys()) == {"id", "title", "summary", "group", "related", "body"}


# Unit — full-mode excludes seed body even with mutual citation
# eager-impl from G1/G2; locking in
def test_map_documents_full_mode_excludes_seed(tmp_path):
    """seed body 'SEED-SENTINEL'; full=True returns no record with seed id/body."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["a"], body="SEED-SENTINEL")
    _write_doc(codex_dir, "a", related=["seed"])

    result = map_documents(codex_dir, "seed", depth_out=1, depth_in=1, full=True)

    assert result is not None
    for r in result:
        assert r["id"] != "seed"
        assert "SEED-SENTINEL" not in r["body"]


# Unit — full-mode dedupe cross-direction
# eager-impl from G1/G2; locking in
def test_map_documents_full_mode_dedupes_cross_direction_neighbour(tmp_path):
    """Mutual seed <-> shared with full=True returns exactly one shared record."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["shared"])
    _write_doc(codex_dir, "shared", related=["seed"])

    result = map_documents(codex_dir, "seed", depth_out=1, depth_in=1, full=True)

    assert result is not None
    shared_recs = [r for r in result if r["id"] == "shared"]
    assert len(shared_recs) == 1


# Unit — full-mode alphabetical sort
# eager-impl from G1/G2; locking in
def test_map_documents_full_mode_result_sorted_alphabetically_by_id(tmp_path):
    """Neighbours zebra/apple/mango; full=True -> ids ['apple','mango','zebra']."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["zebra", "apple", "mango"])
    _write_doc(codex_dir, "zebra", related=[])
    _write_doc(codex_dir, "apple", related=[])
    _write_doc(codex_dir, "mango", related=[])

    result = map_documents(codex_dir, "seed", depth_out=1, depth_in=0, full=True)

    assert result is not None
    ids = [r["id"] for r in result]
    assert ids == ["apple", "mango", "zebra"]


# Unit — full-mode record includes group derived from path and related list
# eager-impl from G1/G2; locking in
def test_map_documents_full_mode_record_includes_group_and_related_keys(tmp_path):
    """Neighbour at foo/bar/ with related:['x'] -> group=='foo/bar', related==['x']."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["n"])
    _write_doc(codex_dir, "n", related=["x"], subdir="foo/bar")
    _write_doc(codex_dir, "x", related=[])

    result = map_documents(codex_dir, "seed", depth_out=1, depth_in=0, full=True)

    assert result is not None
    n_rec = next((r for r in result if r["id"] == "n"), None)
    assert n_rec is not None
    assert n_rec["group"] == "foo/bar"
    assert n_rec["related"] == ["x"]


# Unit — full-mode skips unparseable neighbours silently
# eager-impl from G1/G2; locking in
def test_map_documents_full_mode_skips_unparseable_neighbour(tmp_path):
    """Neighbour file with broken frontmatter is silently skipped under full=True."""
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed", related=["good", "broken"])
    _write_doc(codex_dir, "good", related=[])
    broken = codex_dir / "broken.md"
    broken.write_text(
        "---\nid: broken\ntitle: Broken\nsummary: B\nrelated: []\n---\nbody"
    )
    result = map_documents(codex_dir, "seed", depth_out=1, depth_in=0, full=True)

    assert result is not None
    ids = [r["id"] for r in result]
    assert "good" in ids
    # No exception was raised — that is the property under test.


# ===========================================================================
# US-006 — Default JSON envelope keyed on `codex` (CLI handler unit)
# ===========================================================================


# Unit — top-level envelope key is exactly "codex"
# eager-impl from G1/G2; locking in
def test_codex_map_json_default_uses_codex_envelope_key(tmp_path, monkeypatch):
    """`lore --json codex map seed` -> top-level dict has key 'codex', not 'documents'."""
    import json as _json
    from click.testing import CliRunner
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    codex_dir = tmp_path / ".lore" / "codex"
    _write_doc(codex_dir, "seed", related=["child-a"])
    _write_doc(codex_dir, "child-a", related=[])

    result = CliRunner().invoke(main, ["--json", "codex", "map", "seed"])

    assert result.exit_code == 0, result.stderr
    parsed = _json.loads(result.stdout)
    assert set(parsed.keys()) == {"codex"}
    assert "documents" not in parsed


# Unit — each default-mode entry has exactly four keys
# eager-impl from G1/G2; locking in
def test_codex_map_json_default_entry_has_four_keys(tmp_path, monkeypatch):
    """Each entry under 'codex' has exactly {id, group, title, summary}."""
    import json as _json
    from click.testing import CliRunner
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    codex_dir = tmp_path / ".lore" / "codex"
    _write_doc(codex_dir, "seed", related=["child-a"])
    _write_doc(codex_dir, "child-a", related=[])

    result = CliRunner().invoke(main, ["--json", "codex", "map", "seed"])

    assert result.exit_code == 0, result.stderr
    parsed = _json.loads(result.stdout)
    for entry in parsed["codex"]:
        assert set(entry.keys()) == {"id", "group", "title", "summary"}
        assert "body" not in entry
        assert "related" not in entry


# Unit — empty neighbourhood -> {"codex": []}
# eager-impl from G1/G2; locking in
def test_codex_map_json_empty_neighbourhood_returns_empty_list(tmp_path, monkeypatch):
    """Isolated seed -> stdout parses to {'codex': []} exactly."""
    import json as _json
    from click.testing import CliRunner
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    codex_dir = tmp_path / ".lore" / "codex"
    _write_doc(codex_dir, "seed", related=[])

    result = CliRunner().invoke(main, ["--json", "codex", "map", "seed"])

    assert result.exit_code == 0, result.stderr
    parsed = _json.loads(result.stdout)
    assert parsed == {"codex": []}


# Unit — empty-string group serialised as null in JSON
# eager-impl from G1/G2; locking in
def test_codex_map_json_default_empty_group_serialised_as_null(tmp_path, monkeypatch):
    """Neighbour at codex root (group '') -> JSON 'group' is None."""
    import json as _json
    from click.testing import CliRunner
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    codex_dir = tmp_path / ".lore" / "codex"
    _write_doc(codex_dir, "seed", related=["root-neighbour"])
    _write_doc(codex_dir, "root-neighbour", related=[])  # no subdir -> empty group

    result = CliRunner().invoke(main, ["--json", "codex", "map", "seed"])

    assert result.exit_code == 0, result.stderr
    parsed = _json.loads(result.stdout)
    rn = next((e for e in parsed["codex"] if e["id"] == "root-neighbour"), None)
    assert rn is not None
    assert rn["group"] is None


# ===========================================================================
# US-007 — Full-mode JSON envelope keyed on `documents` (CLI handler unit)
# ===========================================================================


# Unit — top-level envelope key is exactly "documents" under --full --json
# eager-impl from G1/G2; locking in
def test_codex_map_json_full_uses_documents_envelope_key(tmp_path, monkeypatch):
    """`lore --json codex map seed --full` -> top-level key 'documents', not 'codex'."""
    import json as _json
    from click.testing import CliRunner
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    codex_dir = tmp_path / ".lore" / "codex"
    _write_doc(codex_dir, "seed", related=["a"])
    _write_doc(codex_dir, "a", related=[])

    result = CliRunner().invoke(main, ["--json", "codex", "map", "seed", "--full"])

    assert result.exit_code == 0, result.stderr
    parsed = _json.loads(result.stdout)
    assert set(parsed.keys()) == {"documents"}
    assert "codex" not in parsed


# Unit — each --full --json entry has exactly six keys
# eager-impl from G1/G2; locking in
def test_codex_map_json_full_entry_has_six_keys(tmp_path, monkeypatch):
    """Each entry under 'documents' has {id, title, summary, group, related, body}."""
    import json as _json
    from click.testing import CliRunner
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    codex_dir = tmp_path / ".lore" / "codex"
    _write_doc(codex_dir, "seed", related=["a"])
    _write_doc(codex_dir, "a", related=[])

    result = CliRunner().invoke(main, ["--json", "codex", "map", "seed", "--full"])

    assert result.exit_code == 0, result.stderr
    parsed = _json.loads(result.stdout)
    for entry in parsed["documents"]:
        assert set(entry.keys()) == {
            "id", "title", "summary", "group", "related", "body",
        }


# Unit — empty under --full --json -> {"documents": []}
# eager-impl from G1/G2; locking in
def test_codex_map_json_full_empty_neighbourhood_returns_empty_list(
    tmp_path, monkeypatch
):
    """Isolated seed with --full --json -> stdout parses to {'documents': []}."""
    import json as _json
    from click.testing import CliRunner
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    codex_dir = tmp_path / ".lore" / "codex"
    _write_doc(codex_dir, "seed", related=[])

    result = CliRunner().invoke(main, ["--json", "codex", "map", "seed", "--full"])

    assert result.exit_code == 0, result.stderr
    parsed = _json.loads(result.stdout)
    assert parsed == {"documents": []}


# ===========================================================================
# Regression — YAML multi-line plain scalar in `summary:` must not break the
# index. Real codex files wrap summaries onto continuation lines for readability;
# a prior parser stripped per-line whitespace and corrupted the YAML, dropping
# affected docs from the index ("Document <id> not found").
# ===========================================================================


def test_map_documents_handles_multiline_summary_continuation(tmp_path):
    """Summary wrapped over multiple lines (2-space indent) is still indexed."""
    codex_dir = _make_codex_dir(tmp_path)
    multiline = (
        "---\n"
        "id: wrapped\n"
        "title: Wrapped Summary\n"
        "summary: ADR recording the decision to add a per-quest auto_close toggle, defaulting\n"
        "  to disabled for new quests. Covers the schema design, migration default split, and\n"
        "  the mechanism for manually closing quests.\n"
        "related:\n"
        "  - peer\n"
        "---\n\nBody.\n"
    )
    (codex_dir / "wrapped.md").write_text(multiline)
    _write_doc(codex_dir, "peer", related=[])

    result = map_documents(codex_dir, "wrapped", depth_out=1, depth_in=0)

    assert result is not None
    assert [r["id"] for r in result] == ["peer"]
