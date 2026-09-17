"""Unit tests for ``lore health --scope index``.

Spec: codex-index-spec (``lore codex show codex-index-spec``) — Part 4, the
``lore.health._check_index`` row, and Part 2's check table for the exact
severity, ``entity_type``, ``id``, ``check`` and ``detail`` of every row.

Two rulings from the spec's Pre-Dev Notes govern this file. Escalation E1
demotes ``duplicate_slug`` from an error to a warning: no caller resolves a
cluster by slug, so a collision breaks nothing — it only makes two rows
indistinguishable to the reader the index exists to serve. And the
``index-authored`` kind is deliberately absent from ``health._SCHEMA_KINDS``:
``--scope index`` is the single reporter for that file, the way
``decisions-033-unresolvable-reference-is-silent-on-read`` gives one fact one
reporter.
"""

from __future__ import annotations

import json

from lore.health import _ALL_SCOPES, _SCHEMA_KINDS, _check_index, health_check
from lore.index import build_index
from lore.paths import index_authored_path, index_rendered_path


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


def _entry(slug: str, digest: str) -> dict[str, str]:
    return {
        "slug": slug,
        "name": slug.title(),
        "summary": f"Everything {slug}.",
        "authored_against": digest,
    }


def _write_clique(tree, project, prefix: str) -> None:
    """Three documents linked to each other — one cluster, hub ``<prefix>-a``."""
    tree.doc(project, f"{prefix}-a", related=(f"{prefix}-b", f"{prefix}-c"))
    tree.doc(project, f"{prefix}-b", related=(f"{prefix}-a", f"{prefix}-c"))
    tree.doc(project, f"{prefix}-c", related=(f"{prefix}-a", f"{prefix}-b"))


def _digest_of(project, hub: str) -> str:
    render = json.loads(index_rendered_path(project).read_text(encoding="utf-8"))
    return next(c["digest"] for c in render["clusters"] if c["hub"] == hub)


def _built_clique(tree, prefix: str = "alpha"):
    """One clique, built once, so a test can read its current digest."""
    _write_clique(tree, tree.lore, prefix)
    build_index(tree.lore)
    return tree.lore


# ---------------------------------------------------------------------------
# The scope itself
# ---------------------------------------------------------------------------


def test_index_is_a_health_scope_token():
    assert "index" in _ALL_SCOPES
    assert _ALL_SCOPES.index("index") == _ALL_SCOPES.index("glossary") + 1


def test_the_index_scope_is_accepted_by_health_check(tree):
    report = health_check(tree.lore, scope=["index"])

    assert report.issues == ()


def test_the_index_scope_does_not_claim_a_schema_run(tree):
    """``schemas_ran`` drives the CLI's schema summary and is not this scope's."""
    assert health_check(tree.lore, scope=["index"]).schemas_ran is False


def test_the_authored_index_kind_is_not_in_the_schema_walk():
    """One file, one reporter: ``--scope index`` owns ``authored.yaml``."""
    assert "index-authored" not in {kind for _, kind, _, _ in _SCHEMA_KINDS}


# ---------------------------------------------------------------------------
# No authored file
# ---------------------------------------------------------------------------


def test_no_authored_file_produces_no_issues(tree):
    """A missing file is a valid state, the way a missing glossary is."""
    _write_clique(tree, tree.lore, "alpha")

    assert _check_index(tree.lore) == []


def test_the_audit_writes_no_render(tree):
    """ADR-021: a read-only audit touches no disk."""
    _write_clique(tree, tree.lore, "alpha")
    _write_authored(tree.lore, _authored_yaml({"alpha-a": _entry("alpha", "0" * 64)}))

    _check_index(tree.lore)

    assert not index_rendered_path(tree.lore).exists()


def test_the_audit_leaves_a_stale_render_in_place(tree):
    """The partition is recomputed in memory rather than written back (D20)."""
    project = _built_clique(tree)
    before = index_rendered_path(project).read_bytes()
    _write_clique(tree, project, "gamma")
    _write_authored(project, _authored_yaml({"alpha-a": _entry("alpha", "0" * 64)}))

    issues = _check_index(project)

    assert index_rendered_path(project).read_bytes() == before
    assert {issue.id for issue in issues} == {"alpha-a", "gamma-a"}


# ---------------------------------------------------------------------------
# schema — the error that short-circuits every other check
# ---------------------------------------------------------------------------


def test_broken_yaml_produces_exactly_one_schema_error(tree):
    _write_clique(tree, tree.lore, "alpha")
    _write_authored(tree.lore, "entries: [\n")

    issues = _check_index(tree.lore)

    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].entity_type == "index"
    assert issues[0].id == ".lore/index/authored.yaml"
    assert issues[0].check == "schema"
    assert issues[0].schema_id == "lore://schemas/index-authored"
    assert issues[0].rule == "yaml-parse"
    assert issues[0].pointer == "/"


def test_a_schema_violation_produces_only_schema_rows(tree):
    _write_clique(tree, tree.lore, "alpha")
    _write_authored(tree.lore, "version: 1\nentries:\n  alpha-a:\n    slug: SHOUTING\n")

    issues = _check_index(tree.lore)

    assert issues
    assert {issue.check for issue in issues} == {"schema"}
    for issue in issues:
        assert issue.severity == "error"
        assert issue.entity_type == "index"
        assert issue.id == ".lore/index/authored.yaml"
        assert issue.schema_id == "lore://schemas/index-authored"
        assert issue.rule is not None
        assert issue.pointer is not None


# ---------------------------------------------------------------------------
# unresolvable_hub — error
# ---------------------------------------------------------------------------


def test_an_entry_naming_no_document_at_all_is_an_unresolvable_hub(tree):
    project = _built_clique(tree)
    _write_authored(
        project,
        _authored_yaml(
            {
                "alpha-a": _entry("alpha", _digest_of(project, "alpha-a")),
                "no-such-doc": _entry("ghost", "0" * 64),
            }
        ),
    )

    issues = _check_index(project)

    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].entity_type == "index"
    assert issues[0].id == "no-such-doc"
    assert issues[0].check == "unresolvable_hub"
    assert issues[0].detail == (
        'entry "ghost" names a hub that is not a document in this codex'
    )


# ---------------------------------------------------------------------------
# duplicate_slug — warning (Escalation E1)
# ---------------------------------------------------------------------------


def test_two_entries_sharing_a_slug_are_a_warning(tree):
    project = _built_clique(tree)
    _write_clique(tree, project, "gamma")
    build_index(project)
    _write_authored(
        project,
        _authored_yaml(
            {
                "alpha-a": _entry("shared", _digest_of(project, "alpha-a")),
                "gamma-a": _entry("shared", _digest_of(project, "gamma-a")),
            }
        ),
    )

    issues = [i for i in _check_index(project) if i.check == "duplicate_slug"]

    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].entity_type == "index"
    assert issues[0].id == ".lore/index/authored.yaml"
    assert issues[0].detail == "'shared' is the slug of both alpha-a and gamma-a"


def test_a_duplicate_slug_does_not_raise_the_exit_code(tree):
    """E1 demoted the check; no index check joins the escalated set."""
    project = _built_clique(tree)
    _write_clique(tree, project, "gamma")
    build_index(project)
    _write_authored(
        project,
        _authored_yaml(
            {
                "alpha-a": _entry("shared", _digest_of(project, "alpha-a")),
                "gamma-a": _entry("shared", _digest_of(project, "gamma-a")),
            }
        ),
    )

    report = health_check(project, scope=["index"])

    assert report.has_errors is False
    assert "duplicate_slug" in {issue.check for issue in report.warnings}


# ---------------------------------------------------------------------------
# stale_entry — warning
# ---------------------------------------------------------------------------


def test_an_entry_keyed_on_a_document_that_heads_no_cluster_is_stale(tree):
    project = _built_clique(tree)
    _write_authored(
        project,
        _authored_yaml({"alpha-b": _entry("alpha", _digest_of(project, "alpha-a"))}),
    )

    issues = [i for i in _check_index(project) if i.check == "stale_entry"]

    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].entity_type == "index"
    assert issues[0].id == "alpha-b"
    assert issues[0].detail == (
        'entry "alpha" is attached to a hub that heads no cluster; '
        "re-key or retire it"
    )


# ---------------------------------------------------------------------------
# unauthored_cluster — warning
# ---------------------------------------------------------------------------


def test_a_cluster_with_no_entry_is_an_unauthored_cluster(tree):
    project = _built_clique(tree)
    _write_clique(tree, project, "gamma")
    build_index(project)
    _write_authored(
        project,
        _authored_yaml({"alpha-a": _entry("alpha", _digest_of(project, "alpha-a"))}),
    )

    issues = [i for i in _check_index(project) if i.check == "unauthored_cluster"]

    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].entity_type == "index"
    assert issues[0].id == "gamma-a"
    assert issues[0].detail == (
        "cluster of 3 documents has no entry in .lore/index/authored.yaml"
    )


def test_a_one_document_cluster_is_reported_in_the_singular(tree):
    tree.doc(tree.lore, "solo")
    _write_clique(tree, tree.lore, "alpha")
    build_index(tree.lore)
    _write_authored(
        tree.lore,
        _authored_yaml({"alpha-a": _entry("alpha", _digest_of(tree.lore, "alpha-a"))}),
    )

    issues = [i for i in _check_index(tree.lore) if i.check == "unauthored_cluster"]

    assert [i.id for i in issues] == ["solo"]
    assert issues[0].detail == (
        "cluster of 1 document has no entry in .lore/index/authored.yaml"
    )


# ---------------------------------------------------------------------------
# drifted_entry — warning
# ---------------------------------------------------------------------------


def test_an_entry_authored_against_another_digest_is_drifted(tree):
    project = _built_clique(tree)
    _write_authored(project, _authored_yaml({"alpha-a": _entry("alpha", "0" * 64)}))

    issues = [i for i in _check_index(project) if i.check == "drifted_entry"]

    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].entity_type == "index"
    assert issues[0].id == "alpha-a"
    assert issues[0].detail == (
        "summary was authored against a digest its members no longer produce"
    )


# ---------------------------------------------------------------------------
# Ordering — errors in table order, then warnings in table order
# ---------------------------------------------------------------------------


def test_rows_arrive_errors_first_then_warnings_in_the_table_order(tree):
    project = _built_clique(tree)
    _write_clique(tree, project, "gamma")
    _write_clique(tree, project, "delta")
    build_index(project)
    _write_authored(
        project,
        _authored_yaml(
            {
                "alpha-a": _entry("shared", "0" * 64),
                "delta-a": _entry("shared", _digest_of(project, "delta-a")),
                "gamma-b": _entry("misplaced", "0" * 64),
                "no-such-doc": _entry("ghost", "0" * 64),
            }
        ),
    )

    checks = [issue.check for issue in _check_index(project)]

    assert checks == [
        "unresolvable_hub",
        "duplicate_slug",
        "stale_entry",
        "unauthored_cluster",
        "drifted_entry",
    ]
