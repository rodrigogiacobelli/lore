"""E2E tests for the `lore index` command group.

Spec: codex-index-spec — Part 1 workflows W1-W4 and W9, Part 2 "CLI Surface"
and its failure table, Part 4 "E2E". Every expected output here is copied from
those sections character for character; a paraphrase would stop pinning them.

The CLI is a thin wrapper (ADR-011): each scenario drives the real Click app
through `CliRunner` against a real `lore init` project, and asserts on what the
terminal and the `--json` envelope actually carry.

Click 8.3 has no `mix_stderr` parameter: `result.stdout` and `result.stderr` are
read separately and never assembled into one string to assert on.
"""

from __future__ import annotations

import json
from pathlib import Path

from lore.cli import main

# ---------------------------------------------------------------------------
# The expected output blocks, from Part 1 and Part 2
# ---------------------------------------------------------------------------


W2_BUILD = """\
  SLUG          NAME            MEMBERS  STATUS
  (unauthored)  hub: alpha-hub  5        unauthored
  (unauthored)  hub: beta-hub   5        unauthored
  (unauthored)  hub: gamma-hub  5        unauthored
  (unauthored)  hub: solo       1        unauthored
4 clusters — 4 unauthored, 0 drifted.
"""


W1_BUILD = """\
  SLUG          NAME            MEMBERS  STATUS
  alpha-theme   Alpha Theme     5        ok
  (unauthored)  hub: gamma-hub  5        unauthored
  (unauthored)  hub: solo       1        unauthored
  beta-theme    Beta Theme      5        drifted
4 clusters — 2 unauthored, 1 drifted.
"""


W3_SEARCH_BETA = """\
  beta-theme — Beta Theme
    Everything beta.
    beta-a    beta-a.md
    beta-b    beta-b.md
    beta-c    beta-c.md
    beta-d    beta-d.md
    beta-hub  beta-hub.md
"""


W3_SEARCH_GAMMA = """\
  (unauthored) — hub: gamma-hub
    gamma-a    gamma-a.md
    gamma-b    gamma-b.md
    gamma-c    gamma-c.md
    gamma-d    gamma-d.md
    gamma-hub  gamma-hub.md
"""


W3_SEARCH_SOLO = """\
  (unauthored) — hub: solo
    solo  solo.md
"""


W4_NOT_AUTHORED = (
    "no index authored for this project. Run the update-index skill to author it."
)


def _members(prefix: str) -> list[str]:
    return [f"{prefix}-a", f"{prefix}-b", f"{prefix}-c", f"{prefix}-d", f"{prefix}-hub"]


def _paths(prefix: str) -> list[str]:
    return [f"{member}.md" for member in _members(prefix)]


W1_JSON = {
    "clusters": [
        {
            "slug": "alpha-theme",
            "name": "Alpha Theme",
            "hub": "alpha-hub",
            "status": "ok",
            "members": _members("alpha"),
            "member_paths": _paths("alpha"),
        },
        {
            "slug": None,
            "name": None,
            "hub": "gamma-hub",
            "status": "unauthored",
            "members": _members("gamma"),
            "member_paths": _paths("gamma"),
        },
        {
            "slug": None,
            "name": None,
            "hub": "solo",
            "status": "unauthored",
            "members": ["solo"],
            "member_paths": ["solo.md"],
        },
        {
            "slug": "beta-theme",
            "name": "Beta Theme",
            "hub": "beta-hub",
            "status": "drifted",
            "members": _members("beta"),
            "member_paths": _paths("beta"),
        },
    ],
    "unauthored": 2,
    "drifted": 1,
    "stale": [],
}


W3_JSON = {
    "clusters": [
        {
            "slug": "beta-theme",
            "name": "Beta Theme",
            "summary": "Everything beta.",
            "hub": "beta-hub",
            "members": _members("beta"),
            "member_paths": _paths("beta"),
        }
    ]
}


def _render(project_dir: Path) -> Path:
    return project_dir / ".lore" / "index" / "codex.json"


def _authored(project_dir: Path) -> Path:
    return project_dir / ".lore" / "index" / "authored.yaml"


# ===========================================================================
# W2 / W1 — lore index build
# ===========================================================================


def test_build_with_nothing_authored(index_project, runner):
    """W2 — every cluster `unauthored`, exit 0, and Lore authors nothing."""
    res = runner.invoke(main, ["index", "build"])

    assert res.exit_code == 0, res.output
    assert res.stdout == W2_BUILD
    assert _render(index_project).exists()
    assert not _authored(index_project).exists()


def test_build_with_one_ok_one_drifted_and_two_unauthored(w1_project, runner):
    """W1 — the four statuses in one table, ordered by status rank."""
    res = runner.invoke(main, ["index", "build"])

    assert res.exit_code == 0, res.output
    assert res.stdout == W1_BUILD


def test_build_is_deterministic_and_idempotent(index_project, runner):
    """SC — two runs on an unchanged codex print and write the same bytes."""
    first = runner.invoke(main, ["index", "build"])
    first_render = _render(index_project).read_bytes()
    second = runner.invoke(main, ["index", "build"])

    assert first.exit_code == 0 and second.exit_code == 0
    assert first.stdout == second.stdout
    assert first_render == _render(index_project).read_bytes()


def test_build_json_envelope(w1_project, runner):
    """Part 2 — the envelope is `build_index`'s dict and nothing else."""
    res = runner.invoke(main, ["--json", "index", "build"])

    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout) == W1_JSON


def test_build_on_an_empty_codex(index_project, runner):
    """Part 2 — zero indexed documents prints one line and nothing else."""
    for path in (index_project / ".lore" / "codex").rglob("*.md"):
        path.unlink()

    res = runner.invoke(main, ["index", "build"])

    assert res.exit_code == 0, res.output
    assert res.stdout == "No codex documents to index.\n"


def test_build_json_envelope_on_an_empty_codex(index_project, runner):
    """Part 2 — under `--json` the empty codex is the ordinary envelope."""
    for path in (index_project / ".lore" / "codex").rglob("*.md"):
        path.unlink()

    res = runner.invoke(main, ["--json", "index", "build"])

    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout) == {
        "clusters": [],
        "unauthored": 0,
        "drifted": 0,
        "stale": [],
    }


def test_build_reports_a_stale_entry_after_the_trailer(
    index_project, runner, write_authored
):
    """Part 2 — one line per stale entry, one wording per reason.

    `alpha-a` is a real document that heads no cluster; `tech-arch-lsp` is no
    document in this codex at all.
    """
    write_authored(
        index_project,
        "  alpha-a:\n"
        "    slug: database-and-storage\n"
        "    name: Database And Storage\n"
        "    summary: Storage.\n"
        f"    authored_against: \"{'0' * 64}\"\n"
        "  tech-arch-lsp:\n"
        "    slug: old-theme\n"
        "    name: Old Theme\n"
        "    summary: Retired.\n"
        f"    authored_against: \"{'0' * 64}\"\n",
    )

    res = runner.invoke(main, ["index", "build"])

    assert res.exit_code == 0, res.output
    assert res.stdout.endswith(
        'Stale entry "database-and-storage": hub alpha-a heads no cluster.\n'
        'Stale entry "old-theme": hub tech-arch-lsp is not a document in this codex.\n'
    )


def test_the_seeded_document_is_indexed_and_nothing_about_it_is_pinned(
    project_dir, runner
):
    """Part 4 — every id `codex list` returns lands in exactly one cluster.

    Named values would pin a seeded default's fields
    (`decisions-006-no-seed-content-tests`); this names none, so it holds
    whatever `lore init` seeds.
    """
    listed = runner.invoke(main, ["--json", "codex", "list"])
    built = runner.invoke(main, ["--json", "index", "build"])

    assert listed.exit_code == 0, listed.output
    assert built.exit_code == 0, built.output
    documents = {d["id"] for d in json.loads(listed.stdout)["codex"]}
    assert documents, "lore init seeds at least one codex document"
    indexed = [
        member
        for cluster in json.loads(built.stdout)["clusters"]
        for member in cluster["members"]
    ]
    assert sorted(indexed) == sorted(documents)
    assert len(indexed) == len(set(indexed))


# ===========================================================================
# W3 — lore index search
# ===========================================================================


def test_search_an_authored_cluster(w1_project, runner):
    """W3 — header, summary, then one padded line per member."""
    res = runner.invoke(main, ["index", "search", "beta"])

    assert res.exit_code == 0, res.output
    assert res.stdout == W3_SEARCH_BETA


def test_search_an_unauthored_cluster(w1_project, runner):
    """W3 / D19 — matched on member ids alone, rendered with the placeholder."""
    res = runner.invoke(main, ["index", "search", "gamma"])

    assert res.exit_code == 0, res.output
    assert res.stdout == W3_SEARCH_GAMMA


def test_search_finds_the_isolated_document(w1_project, runner):
    """R12 — a document with no edge to be absorbed along stays a cluster."""
    res = runner.invoke(main, ["index", "search", "solo"])

    assert res.exit_code == 0, res.output
    assert res.stdout == W3_SEARCH_SOLO


def test_search_with_no_match(w1_project, runner):
    """Draft ADR H, ruled (a) — a sentence, in `lore codex search`'s shape."""
    res = runner.invoke(main, ["index", "search", "zzzz"])

    assert res.exit_code == 0, res.output
    assert res.stdout == 'No clusters matching "zzzz".\n'


def test_search_json_envelope(w1_project, runner):
    """Part 2 — `{"clusters": [...]}`, the summary carried per row."""
    res = runner.invoke(main, ["--json", "index", "search", "beta"])

    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout) == W3_JSON


def test_search_json_envelope_with_no_match(w1_project, runner):
    """Part 2 — no match is `{"clusters": []}` at exit 0, never a failure."""
    res = runner.invoke(main, ["--json", "index", "search", "zzzz"])

    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout) == {"clusters": []}


def test_search_refreshes_after_a_codex_edit(w1_project, runner, write_document):
    """R5 — the answer is computed from the codex as it is now."""
    write_document(w1_project, "delta-hub", ["delta-a", "delta-b"])
    write_document(w1_project, "delta-a", [])
    write_document(w1_project, "delta-b", [])

    res = runner.invoke(main, ["index", "search", "delta"])

    assert res.exit_code == 0, res.output
    assert res.stdout == (
        "  (unauthored) — hub: delta-hub\n"
        "    delta-a    delta-a.md\n"
        "    delta-b    delta-b.md\n"
        "    delta-hub  delta-hub.md\n"
    )


def test_search_after_the_render_is_deleted(w1_project, runner):
    """N3 — deleting the cache loses nothing and the next command rebuilds it."""
    _render(w1_project).unlink()

    res = runner.invoke(main, ["index", "search", "beta"])

    assert res.exit_code == 0, res.output
    assert res.stdout == W3_SEARCH_BETA
    assert _render(w1_project).exists()


def test_search_after_the_render_is_corrupted(w1_project, runner):
    """D14 — an unreadable cache is treated as absent, never as a failure."""
    _render(w1_project).write_text("not json", encoding="utf-8")

    res = runner.invoke(main, ["index", "search", "beta"])

    assert res.exit_code == 0, res.output
    assert res.stdout == W3_SEARCH_BETA


# ===========================================================================
# W4 — searching an index that has never been authored
# ===========================================================================


def test_search_before_the_index_has_ever_been_authored(index_project, runner):
    """W4 — the refusal on stderr at exit 1, and stdout stays empty."""
    res = runner.invoke(main, ["index", "search", "beta"])

    assert res.exit_code == 1, res.output
    assert res.stdout == ""
    assert res.stderr == f"{W4_NOT_AUTHORED}\n"


def test_search_before_authoring_under_json(index_project, runner):
    """W4 — the same message, as the error envelope on stderr at exit 1."""
    res = runner.invoke(main, ["--json", "index", "search", "beta"])

    assert res.exit_code == 1, res.output
    assert json.loads(res.stderr) == {"error": W4_NOT_AUTHORED}


# ===========================================================================
# Failures — Part 2's failure table
# ===========================================================================


def test_an_unreadable_authored_file_fails_the_build(index_project, runner):
    """Part 2 — `index.py` composes the prefix and the CLI adds no wording."""
    _authored(index_project).parent.mkdir(parents=True, exist_ok=True)
    _authored(index_project).write_text("entries: [\n", encoding="utf-8")

    res = runner.invoke(main, ["index", "build"])

    assert res.exit_code == 1, res.output
    assert res.stdout == ""
    assert res.stderr.startswith(".lore/index/authored.yaml:")


def test_an_unreadable_authored_file_fails_the_search(index_project, runner):
    """Part 2 — the same failure, on the other command."""
    _authored(index_project).parent.mkdir(parents=True, exist_ok=True)
    _authored(index_project).write_text("entries: [\n", encoding="utf-8")

    res = runner.invoke(main, ["index", "search", "beta"])

    assert res.exit_code == 1, res.output
    assert res.stdout == ""
    assert res.stderr.startswith(".lore/index/authored.yaml:")


def test_a_render_path_that_is_a_symlink_is_refused(index_project, runner):
    """Part 2 — the `safewrite` refusal text, unchanged, on stderr at exit 1."""
    _render(index_project).parent.mkdir(parents=True, exist_ok=True)
    _render(index_project).symlink_to(index_project / "elsewhere.json")

    res = runner.invoke(main, ["index", "build"])

    assert res.exit_code == 1, res.output
    assert res.stdout == ""
    assert "a symlink to" in res.stderr


def test_project_is_refused_on_build(index_project, runner):
    """W9 / ADR-025 — a read selector the index group does not accept."""
    res = runner.invoke(main, ["--project", "other", "index", "build"])

    assert res.exit_code == 2, res.output
    assert (
        '--project is a read selector; it is not accepted on "index build".'
        in res.stderr
    )


def test_project_is_refused_on_search(index_project, runner):
    """W9 — the refusal names whichever subcommand was invoked."""
    res = runner.invoke(main, ["--project", "other", "index", "search", "beta"])

    assert res.exit_code == 2, res.output
    assert (
        '--project is a read selector; it is not accepted on "index search".'
        in res.stderr
    )


def test_search_with_no_keyword_is_clicks_usage_error(index_project, runner):
    """ADR-034 — a missing argument stays Click's usage error at exit 2."""
    res = runner.invoke(main, ["index", "search"])

    assert res.exit_code == 2, res.output
    assert "Missing argument 'KEYWORD'." in res.stderr


def test_the_group_with_no_subcommand_is_help_on_stderr_at_exit_2(
    index_project, runner
):
    """Part 2 — Click's `no_args_is_help`, restated by no handler."""
    res = runner.invoke(main, ["index"])

    assert res.exit_code == 2, res.output
    assert res.stdout == ""
    assert "Usage: lore index" in res.stderr


def test_an_unknown_subcommand_is_clicks_own_refusal(index_project, runner):
    """Part 2 — no index handler re-implements it."""
    res = runner.invoke(main, ["index", "frobnicate"])

    assert res.exit_code == 2, res.output
    assert "No such command 'frobnicate'." in res.stderr


# ===========================================================================
# ADR-008 — the group's help teaches the concept
# ===========================================================================


def test_group_help_teaches_the_concept(index_project, runner):
    """ADR-008 — one concept paragraph, not a syntax listing."""
    res = runner.invoke(main, ["index", "--help"])

    assert res.exit_code == 0, res.output
    for phrase in ("cluster", "lore index search", "lore index build", "update-index"):
        assert phrase in res.stdout, phrase
