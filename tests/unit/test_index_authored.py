"""Unit tests for the authored index, the classification and the two callables.

Spec: codex-index-spec (``lore codex show codex-index-spec``) — Part 4, the
``_load_authored``, ``_classify``, ``build_index`` and ``search_index`` rows.

Lore reads ``.lore/index/authored.yaml`` and never writes it (R14, D9): repair
is an authoring act. Every assertion here is on that contract or on the two
envelopes Part 2 documents.
"""

from __future__ import annotations

import json

import pytest

from lore.index import (
    CodexIndexError,
    CodexIndexNotAuthoredError,
    _classify,
    _load_authored,
    build_index,
    search_index,
)
from lore.paths import index_authored_path, index_rendered_path

NOT_AUTHORED_MESSAGE = (
    "no index authored for this project. Run the update-index skill to author it."
)


def _write_authored(project, text: str) -> None:
    path = index_authored_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _authored_yaml(entries: dict[str, dict[str, str]]) -> str:
    lines = ["version: 1", "entries:"]
    for hub, entry in entries.items():
        lines.append(f"  {hub}:")
        for field in ("slug", "name", "summary", "authored_against"):
            # JSON-quoted so a colon in a summary and a digest of all zeroes
            # both read back as the strings the schema requires.
            lines.append(f"    {field}: {json.dumps(entry[field])}")
    return "\n".join(lines) + "\n"


def _write_clique(tree, project, prefix: str) -> None:
    """Three documents linked to each other — one cluster, hub ``<prefix>-a``."""
    tree.doc(project, f"{prefix}-a", related=(f"{prefix}-b", f"{prefix}-c"))
    tree.doc(project, f"{prefix}-b", related=(f"{prefix}-a", f"{prefix}-c"))
    tree.doc(project, f"{prefix}-c", related=(f"{prefix}-a", f"{prefix}-b"))


def _digest_of(project, hub: str) -> str:
    """The current digest of the cluster headed by ``hub``, from the render."""
    render = json.loads(index_rendered_path(project).read_text(encoding="utf-8"))
    return next(c["digest"] for c in render["clusters"] if c["hub"] == hub)


def _cluster(hub: str, members: list[str], digest: str) -> dict:
    """One rendered cluster, as ``_build_clusters`` shapes it."""
    return {
        "hub": hub,
        "members": members,
        "member_paths": [f"{m}.md" for m in members],
        "digest": digest,
    }


def _entry(slug: str, digest: str, *, name: str = "", summary: str = "") -> dict:
    return {
        "slug": slug,
        "name": name or slug.title(),
        "summary": summary or f"Everything {slug}.",
        "authored_against": digest,
    }


# ---------------------------------------------------------------------------
# The exception types
# ---------------------------------------------------------------------------


def test_the_index_exceptions_shadow_no_python_builtin():
    """ADR draft F: a name in the facade never equals a builtin (D17)."""
    assert issubclass(CodexIndexNotAuthoredError, CodexIndexError)
    assert issubclass(CodexIndexError, ValueError)


# ---------------------------------------------------------------------------
# _load_authored
# ---------------------------------------------------------------------------


def test_an_absent_authored_file_refuses_by_name(tree):
    with pytest.raises(CodexIndexNotAuthoredError) as excinfo:
        _load_authored(tree.lore)

    assert str(excinfo.value) == NOT_AUTHORED_MESSAGE


def test_broken_yaml_in_the_authored_file_raises_a_codex_index_error(tree):
    _write_authored(tree.lore, "entries: [\n")

    with pytest.raises(CodexIndexError) as excinfo:
        _load_authored(tree.lore)

    assert not isinstance(excinfo.value, CodexIndexNotAuthoredError)
    assert str(excinfo.value).startswith(".lore/index/authored.yaml:")


def test_a_schema_violation_in_the_authored_file_names_the_file(tree):
    _write_authored(tree.lore, "version: 1\nentries:\n  hub:\n    slug: SHOUTING\n")

    with pytest.raises(CodexIndexError) as excinfo:
        _load_authored(tree.lore)

    assert str(excinfo.value).startswith(".lore/index/authored.yaml:")


def test_a_valid_authored_file_reads_back_as_a_mapping_from_hub_to_entry(tree):
    _write_authored(tree.lore, _authored_yaml({"alpha-a": _entry("alpha", "0" * 64)}))

    entries = _load_authored(tree.lore)

    assert entries == {
        "alpha-a": {
            "slug": "alpha",
            "name": "Alpha",
            "summary": "Everything alpha.",
            "authored_against": "0" * 64,
        }
    }


# ---------------------------------------------------------------------------
# _classify
# ---------------------------------------------------------------------------


def test_a_matching_entry_and_a_matching_digest_is_ok():
    clusters = [_cluster("hub", ["hub", "one", "two"], "a" * 64)]

    result = _classify(clusters, {"hub": _entry("theme", "a" * 64)})

    assert result["clusters"][0]["status"] == "ok"
    assert result["clusters"][0]["slug"] == "theme"
    assert result["clusters"][0]["name"] == "Theme"
    assert result["unauthored"] == 0
    assert result["drifted"] == 0


def test_a_matching_entry_with_a_different_digest_is_drifted():
    clusters = [_cluster("hub", ["hub", "one", "two"], "a" * 64)]

    result = _classify(clusters, {"hub": _entry("theme", "b" * 64)})

    assert result["clusters"][0]["status"] == "drifted"
    assert result["drifted"] == 1


def test_a_cluster_with_no_entry_is_unauthored():
    clusters = [_cluster("hub", ["hub", "one", "two"], "a" * 64)]

    result = _classify(clusters, {})

    assert result["clusters"][0]["status"] == "unauthored"
    assert result["clusters"][0]["slug"] is None
    assert result["clusters"][0]["name"] is None
    assert result["unauthored"] == 1


def test_an_entry_whose_hub_is_an_indexed_document_heading_no_cluster_is_stale():
    clusters = [_cluster("hub", ["hub", "one", "two"], "a" * 64)]

    result = _classify(clusters, {"one": _entry("theme", "a" * 64)})

    assert result["stale"] == [
        {"slug": "theme", "hub": "one", "reason": "hub_not_a_hub"}
    ]


def test_an_entry_whose_hub_is_not_an_indexed_document_is_unresolvable():
    clusters = [_cluster("hub", ["hub", "one", "two"], "a" * 64)]

    result = _classify(clusters, {"gone": _entry("theme", "a" * 64)})

    assert result["stale"] == [
        {"slug": "theme", "hub": "gone", "reason": "hub_not_found"}
    ]


def test_stale_entries_are_ordered_by_ascending_slug():
    clusters = [_cluster("hub", ["hub", "one", "two"], "a" * 64)]
    entries = {
        "gone": _entry("zebra", "a" * 64),
        "one": _entry("aardvark", "a" * 64),
    }

    result = _classify(clusters, entries)

    assert [row["slug"] for row in result["stale"]] == ["aardvark", "zebra"]


def test_the_counters_equal_the_number_of_rows_with_each_status():
    clusters = [
        _cluster("ok-hub", ["ok-hub", "a", "b"], "a" * 64),
        _cluster("drift-hub", ["drift-hub", "c", "d"], "b" * 64),
        _cluster("bare-hub", ["bare-hub", "e", "f"], "c" * 64),
        _cluster("other-hub", ["other-hub", "g", "h"], "d" * 64),
    ]
    entries = {
        "ok-hub": _entry("ok", "a" * 64),
        "drift-hub": _entry("drift", "z" * 64),
    }

    result = _classify(clusters, entries)

    statuses = [row["status"] for row in result["clusters"]]
    assert result["unauthored"] == statuses.count("unauthored") == 2
    assert result["drifted"] == statuses.count("drifted") == 1


def test_clusters_are_ordered_by_status_then_descending_size_then_hub():
    clusters = [
        _cluster("zeta", ["zeta", "a", "b"], "a" * 64),
        _cluster("small", ["small"], "b" * 64),
        _cluster("wide", ["wide", "c", "d", "e"], "c" * 64),
        _cluster("alpha", ["alpha", "f", "g"], "d" * 64),
        _cluster("drifting", ["drifting", "h", "i"], "e" * 64),
    ]
    entries = {
        "zeta": _entry("zeta-theme", "a" * 64),
        "drifting": _entry("drifting-theme", "z" * 64),
    }

    result = _classify(clusters, entries)

    assert [row["hub"] for row in result["clusters"]] == [
        "zeta",      # ok
        "wide",      # unauthored, 4 members
        "alpha",     # unauthored, 3 members, hub before "small"
        "small",     # unauthored, 1 member
        "drifting",  # drifted
    ]


def test_a_classified_cluster_carries_exactly_the_documented_keys():
    clusters = [_cluster("hub", ["hub", "one", "two"], "a" * 64)]

    result = _classify(clusters, {})

    assert set(result["clusters"][0]) == {
        "slug",
        "name",
        "hub",
        "status",
        "members",
        "member_paths",
    }


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------


def test_build_index_writes_the_render(tree):
    _write_clique(tree, tree.lore, "alpha")

    build_index(tree.lore)

    render = json.loads(index_rendered_path(tree.lore).read_text(encoding="utf-8"))
    assert render["version"] == 1
    assert [c["hub"] for c in render["clusters"]] == ["alpha-a"]


def test_build_index_never_creates_the_authored_file(tree):
    _write_clique(tree, tree.lore, "alpha")

    build_index(tree.lore)

    assert not index_authored_path(tree.lore).exists()


def test_build_index_reports_every_cluster_unauthored_with_no_authored_file(tree):
    _write_clique(tree, tree.lore, "alpha")

    result = build_index(tree.lore)

    assert [row["status"] for row in result["clusters"]] == ["unauthored"]
    assert result["unauthored"] == 1


def test_the_render_does_not_depend_on_the_authored_file(tree):
    """R13: two projects with identical codexes render identically."""
    _write_clique(tree, tree.lore, "alpha")
    build_index(tree.lore)
    without = index_rendered_path(tree.lore).read_bytes()

    _write_authored(
        tree.lore,
        _authored_yaml({"alpha-a": _entry("alpha", _digest_of(tree.lore, "alpha-a"))}),
    )
    build_index(tree.lore)

    assert index_rendered_path(tree.lore).read_bytes() == without


def test_build_index_returns_the_documented_envelope_keys_and_no_others(tree):
    _write_clique(tree, tree.lore, "alpha")

    result = build_index(tree.lore)

    assert set(result) == {"clusters", "unauthored", "drifted", "stale"}


def test_build_index_reports_an_authored_cluster_as_ok(tree):
    _write_clique(tree, tree.lore, "alpha")
    build_index(tree.lore)
    _write_authored(
        tree.lore,
        _authored_yaml({"alpha-a": _entry("alpha", _digest_of(tree.lore, "alpha-a"))}),
    )

    result = build_index(tree.lore)

    assert [row["status"] for row in result["clusters"]] == ["ok"]
    assert result["unauthored"] == 0


def test_build_index_raises_on_an_unreadable_authored_file(tree):
    _write_clique(tree, tree.lore, "alpha")
    _write_authored(tree.lore, "entries: [\n")

    with pytest.raises(CodexIndexError):
        build_index(tree.lore)


def test_build_index_on_an_empty_codex_returns_an_empty_envelope(tree):
    result = build_index(tree.lore)

    assert result == {"clusters": [], "unauthored": 0, "drifted": 0, "stale": []}


# ---------------------------------------------------------------------------
# search_index
# ---------------------------------------------------------------------------


def _authored_project(tree):
    """A codex of two clusters with one of them authored, ready to search."""
    _write_clique(tree, tree.lore, "alpha")
    _write_clique(tree, tree.lore, "gamma")
    build_index(tree.lore)
    _write_authored(
        tree.lore,
        _authored_yaml(
            {
                "alpha-a": {
                    "slug": "alpha-theme",
                    "name": "Alpha Theme",
                    "summary": "Everything alpha, and the parchment it is on.",
                    "authored_against": _digest_of(tree.lore, "alpha-a"),
                }
            }
        ),
    )
    return tree.lore


def test_search_matches_on_an_entry_name(tree):
    project = _authored_project(tree)

    assert [row["hub"] for row in search_index(project, "Theme")] == ["alpha-a"]


def test_search_matches_on_an_entry_summary(tree):
    project = _authored_project(tree)

    assert [row["hub"] for row in search_index(project, "parchment")] == ["alpha-a"]


def test_search_matches_on_a_member_id(tree):
    project = _authored_project(tree)

    assert [row["hub"] for row in search_index(project, "alpha-b")] == ["alpha-a"]


def test_search_is_case_insensitive_on_both_sides(tree):
    project = _authored_project(tree)

    assert [row["hub"] for row in search_index(project, "ALPHA THEME")] == ["alpha-a"]
    assert [row["hub"] for row in search_index(project, "everything alpha")] == [
        "alpha-a"
    ]


def test_search_does_not_match_a_keyword_that_occurs_only_in_a_slug(tree):
    """The slug is a display key, not a searched field (D19)."""
    _write_clique(tree, tree.lore, "alpha")
    build_index(tree.lore)
    _write_authored(
        tree.lore,
        _authored_yaml(
            {
                "alpha-a": {
                    "slug": "sluggish",
                    "name": "Alpha Theme",
                    "summary": "Everything alpha.",
                    "authored_against": _digest_of(tree.lore, "alpha-a"),
                }
            }
        ),
    )

    assert search_index(tree.lore, "sluggish") == []


def test_search_does_not_match_a_keyword_that_occurs_only_in_a_body(tree):
    _write_clique(tree, tree.lore, "alpha")
    tree.doc(
        tree.lore,
        "alpha-b",
        related=("alpha-a", "alpha-c"),
        body="A word found nowhere else: chrysoprase.",
    )
    build_index(tree.lore)
    _write_authored(
        tree.lore,
        _authored_yaml({"alpha-a": _entry("alpha", _digest_of(tree.lore, "alpha-a"))}),
    )

    assert search_index(tree.lore, "chrysoprase") == []


def test_search_matches_an_unauthored_cluster_on_a_member_id(tree):
    project = _authored_project(tree)

    rows = search_index(project, "gamma")

    assert [row["hub"] for row in rows] == ["gamma-a"]
    assert rows[0]["slug"] is None
    assert rows[0]["name"] is None
    assert rows[0]["summary"] is None


def test_search_with_no_match_returns_nothing(tree):
    project = _authored_project(tree)

    assert search_index(project, "zzzz") == []


def test_search_orders_authored_clusters_by_slug_then_unauthored_by_hub(tree):
    _write_clique(tree, tree.lore, "one")
    _write_clique(tree, tree.lore, "two")
    _write_clique(tree, tree.lore, "three")
    _write_clique(tree, tree.lore, "four")
    build_index(tree.lore)
    _write_authored(
        tree.lore,
        _authored_yaml(
            {
                "one-a": {
                    "slug": "zebra",
                    "name": "Zebra",
                    "summary": "A shared word: parchment.",
                    "authored_against": _digest_of(tree.lore, "one-a"),
                },
                "two-a": {
                    "slug": "aardvark",
                    "name": "Aardvark",
                    "summary": "A shared word: parchment.",
                    "authored_against": _digest_of(tree.lore, "two-a"),
                },
            }
        ),
    )

    rows = search_index(tree.lore, "-a")

    assert [row["hub"] for row in rows] == ["two-a", "one-a", "four-a", "three-a"]


def test_a_search_row_carries_exactly_the_documented_keys(tree):
    project = _authored_project(tree)

    row = search_index(project, "alpha-b")[0]

    assert set(row) == {
        "slug",
        "name",
        "summary",
        "hub",
        "members",
        "member_paths",
    }


def test_search_refuses_when_no_index_has_ever_been_authored(tree):
    _write_clique(tree, tree.lore, "alpha")

    with pytest.raises(CodexIndexNotAuthoredError) as excinfo:
        search_index(tree.lore, "alpha")

    assert str(excinfo.value) == NOT_AUTHORED_MESSAGE


def test_search_refreshes_a_stale_render_before_matching(tree):
    """R5: the answer is computed from the codex as it is now."""
    project = _authored_project(tree)

    _write_clique(tree, project, "delta")
    rows = search_index(project, "delta")

    assert [row["hub"] for row in rows] == ["delta-a"]
    assert rows[0]["members"] == ["delta-a", "delta-b", "delta-c"]


def test_search_raises_on_an_unreadable_authored_file(tree):
    _write_clique(tree, tree.lore, "alpha")
    _write_authored(tree.lore, "entries: [\n")

    with pytest.raises(CodexIndexError):
        search_index(tree.lore, "alpha")
