"""The nested-projects surface: ``--project``, the FR-14 gate, ORIGIN.

Spec: ``nested-projects-spec`` (``lore codex show nested-projects-spec``) —
Part 4 "E2E", units S2..S7. Every scenario builds a real tree on disk and
drives ``lore.cli.main`` through ``CliRunner``; nothing mocks a walk,
``tomllib`` or ``fnmatch``.

The tables asserted here are the spec's own W1/W2/W4/W6 blocks, character for
character. They are what makes ``--project`` a contract rather than a shape:
the ORIGIN column appears only when a non-``self`` row is in the result set
(D-15), so a project in no tree keeps the output it had (SC-7, pinned
separately in ``test_nested_projects_cost.py``).
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(*argv: str):
    """Invoke the CLI with ``argv`` in the current working directory."""
    return CliRunner().invoke(main, list(argv))


def lines(text: str) -> list[str]:
    """Split ``text`` into lines, dropping the trailing blank."""
    return text.rstrip("\n").split("\n")


W1_SEARCH_TABLE = [
    "  ORIGIN  ID                         TITLE              SUMMARY",
    "  self    camelot-dispatch-contract  Dispatch Contract  How the three projects hand work to each other.",
    "  realm   realm:tech-dispatch-loop   Dispatch Loop      How Realm turns a ready mission into a running agent.",
]

W2_LIST_TABLE = [
    "  ORIGIN  ID                        GROUP      TITLE          SUMMARY",
    "  realm   realm:tech-dispatch-loop  technical  Dispatch Loop  How Realm turns a ready mission into a running agent.",
]

W4_LIST_TABLE = [
    "  ORIGIN   ID                                 GROUP      TITLE              SUMMARY",
    "  camelot  camelot:camelot-dispatch-contract             Dispatch Contract  How the three projects hand work to each other.",
    "  camelot  camelot:standards-naming           standards  Naming             How every Camelot project names things.",
    "  self     tech-db-schema                     technical  DB Schema          The SQLite schema Lore stores state in.",
]

W6_MAP_TABLE = [
    "  ORIGIN   ID                        GROUP      TITLE          SUMMARY",
    "  citadel  citadel:tech-views        technical  Views          The screens Citadel renders.",
    "  lore     lore:tech-db-schema       technical  DB Schema      The SQLite schema Lore stores state in.",
    "  realm    realm:tech-dispatch-loop  technical  Dispatch Loop  How Realm turns a ready mission into a running agent.",
]

W6_MAP_TABLE_WITHOUT_CITADEL = [
    "  ORIGIN  ID                        GROUP      TITLE          SUMMARY",
    "  lore    lore:tech-db-schema       technical  DB Schema      The SQLite schema Lore stores state in.",
    "  realm   realm:tech-dispatch-loop  technical  Dispatch Loop  How Realm turns a ready mission into a running agent.",
]


_KNIGHT_MD = """\
---
id: nested-knight
title: Nested Knight
summary: A knight authored so a scoped knight read has a row.
---

# Nested Knight

Does nothing.
"""

_ARTIFACT_MD = """\
---
id: nested-artifact
title: Nested Artifact
summary: An artifact authored so a scoped artifact read has a row.
---

# Nested Artifact

A template.
"""

_DOCTRINE_DESIGN = """\
---
id: nested-doctrine
title: Nested Doctrine
summary: A doctrine authored so a scoped doctrine read has a row.
---

# Nested Doctrine

One step.
"""

_DOCTRINE_YAML = """\
id: nested-doctrine
title: Nested Doctrine
summary: A doctrine authored so a scoped doctrine read has a row.
steps:
  - id: only-step
    title: Do the thing
    type: knight
    knight: nested-knight
"""

_WATCHER_YAML = """\
id: nested-watcher
title: Nested Watcher
summary: A watcher authored so a scoped watcher read has a row.
watch_target:
  - src/lore/projects.py
interval: on_merge
action:
  - doctrine: nested-doctrine
"""

_RITE_YAML = """\
id: nested-rite
title: Restart the dispatch loop
summary: Bring the dispatcher back after a stall.
trigger: The dispatch loop has stalled.
nodes:
  - id: only-step
    do: Check the queue depth, then restart the worker.
    then: restarted
conclusions:
  restarted:
    audience: operators
    response: Dispatcher is running again.
"""

_GLOSSARY_YAML = """\
items:
  - keyword: Dispatcher
    definition: The component that hands a ready mission to an agent.
"""


def author_entities(project) -> None:
    """Write one entity of every non-codex readable kind into ``project``."""
    lore = project / ".lore"
    (lore / "knights" / "nested-knight.md").write_text(_KNIGHT_MD, encoding="utf-8")
    (lore / "artifacts" / "nested-artifact.md").write_text(
        _ARTIFACT_MD, encoding="utf-8"
    )
    (lore / "doctrines" / "nested-doctrine.design.md").write_text(
        _DOCTRINE_DESIGN, encoding="utf-8"
    )
    (lore / "doctrines" / "nested-doctrine.yaml").write_text(
        _DOCTRINE_YAML, encoding="utf-8"
    )
    (lore / "watchers" / "nested-watcher.yaml").write_text(
        _WATCHER_YAML, encoding="utf-8"
    )
    (lore / "rites" / "main" / "nested-rite.yaml").write_text(
        _RITE_YAML, encoding="utf-8"
    )
    (lore / "codex" / "glossary.yaml").write_text(_GLOSSARY_YAML, encoding="utf-8")


@pytest.fixture()
def realm_tree(nested_tree):
    """``nested_tree`` with one entity of every non-codex kind inside realm.

    The ancestor reads them back with ``--project realm``, which returns that
    project's own entities unfiltered (D-4) and so needs no export table.
    """
    author_entities(nested_tree / "realm")
    return nested_tree


# The W6 command. `--depth-out 1 --depth-in 0` is the form SC-4 and the
# workflow are written against: X-1 leaves the two-budget BFS alone, so this
# is what returns the direct-neighbour set on today's engine.
W6_MAP_ARGV = (
    "codex",
    "map",
    "camelot-dispatch-contract",
    "--depth-out",
    "1",
    "--depth-in",
    "0",
)


# ---------------------------------------------------------------------------
# W1 — an ancestor searches the whole subtree
# ---------------------------------------------------------------------------


def test_project_all_search_spans_the_subtree(nested_tree):
    # nested-projects-spec — W1 / FR-12 / FR-16: `all` is own + inherited +
    # every descendant's own entities, and the ORIGIN column leads the table
    result = run("--project", "all", "codex", "search", "dispatch")

    assert result.exit_code == 0, result.output
    assert lines(result.stdout) == W1_SEARCH_TABLE


def test_project_all_search_json_carries_origin_on_every_row(nested_tree):
    # nested-projects-spec — W1 / FR-16 / D-15: the envelope key stays
    # `documents` and `origin` is present on every row, always
    result = run("--json", "--project", "all", "codex", "search", "dispatch")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "documents": [
            {
                "id": "camelot-dispatch-contract",
                "title": "Dispatch Contract",
                "summary": "How the three projects hand work to each other.",
                "origin": "self",
            },
            {
                "id": "realm:tech-dispatch-loop",
                "title": "Dispatch Loop",
                "summary": "How Realm turns a ready mission into a running agent.",
                "origin": "realm",
            },
        ]
    }


# ---------------------------------------------------------------------------
# W2 — an ancestor reads one named descendant
# ---------------------------------------------------------------------------


def test_project_name_reads_that_descendant_alone(nested_tree):
    # nested-projects-spec — W2 / D-4: a named project returns its own
    # entities unfiltered, and not the ancestor's exports reflected back
    result = run("--project", "realm", "codex", "list")

    assert result.exit_code == 0, result.output
    assert lines(result.stdout) == W2_LIST_TABLE


def test_project_name_reads_that_descendant_alone_json(nested_tree):
    # nested-projects-spec — W2: the envelope key stays `codex`
    result = run("--json", "--project", "realm", "codex", "list")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "codex": [
            {
                "id": "realm:tech-dispatch-loop",
                "group": "technical",
                "title": "Dispatch Loop",
                "summary": "How Realm turns a ready mission into a running agent.",
                "origin": "realm",
            }
        ]
    }


def test_unknown_project_name_names_the_projects_in_scope(nested_tree):
    # nested-projects-spec — FR-18 / failure table: exit 1, stderr, and the
    # message lists what the reader could have asked for
    result = run("--project", "nope", "codex", "list")

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        'Unknown project "nope". Projects in scope: citadel, lore, realm.\n'
    )


def test_unknown_project_name_json_is_the_error_envelope(nested_tree):
    # nested-projects-spec — failure table: the four failure rows become
    # {"error": …} on stderr under --json, with the same exit code
    result = run("--json", "--project", "nope", "codex", "list")

    assert result.exit_code == 1
    assert json.loads(result.stderr) == {
        "error": 'Unknown project "nope". Projects in scope: citadel, lore, realm.'
    }


def test_unknown_project_name_in_a_standalone_project(project_dir):
    # nested-projects-spec — failure table row 3: with nothing else in scope
    # the message says so rather than printing an empty list
    result = run("--project", "nope", "codex", "list")

    assert result.exit_code == 1
    assert result.stderr == (
        'Unknown project "nope". No other Lore project is in scope.\n'
    )


# ---------------------------------------------------------------------------
# W4 — working inside a project that has an ancestor
# ---------------------------------------------------------------------------


def test_a_descendant_sees_inherited_documents_with_no_flag(nested_tree, monkeypatch):
    # nested-projects-spec — W4 / D-3 / A-7 / N-1: inheritance is
    # unconditional, so the listing a descendant already runs carries it
    monkeypatch.chdir(nested_tree / "lore")

    result = run("codex", "list")

    assert result.exit_code == 0, result.output
    assert lines(result.stdout) == W4_LIST_TABLE


def test_a_descendant_reads_an_inherited_document_by_qualified_id(
    nested_tree, monkeypatch
):
    # nested-projects-spec — W4 / FR-15 / decisions-006-id-references: a
    # foreign entity is reachable by qualified id and by nothing else
    monkeypatch.chdir(nested_tree / "lore")

    result = run("codex", "show", "camelot:camelot-dispatch-contract")

    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("=== camelot:camelot-dispatch-contract ===\n")
    assert "# Dispatch Contract" in result.stdout


def test_an_unexported_ancestor_document_is_invisible(nested_tree, monkeypatch):
    # nested-projects-spec — FR-9 / D-4: inheritance is the curated offer the
    # ancestor made, so a document outside it is a miss and not an error
    monkeypatch.chdir(nested_tree / "lore")

    result = run("codex", "show", "camelot:nothing-exported")

    assert result.exit_code == 1
    assert result.stderr == 'Document "camelot:nothing-exported" not found\n'


def test_seeded_defaults_never_cross_a_boundary(nested_tree, monkeypatch):
    # nested-projects-spec — W4 / FR-10 / D-10: an ancestor exporting "*"
    # still exports no seeded default, so the descendant's own default rows
    # stay bare and no ORIGIN column appears
    (nested_tree / ".lore" / "config.toml").write_text(
        'project-name = "camelot"\n\n[shared]\nexports = ["*"]\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(nested_tree / "lore")

    result = run("doctrine", "list")

    assert result.exit_code == 0, result.output
    assert "ORIGIN" not in result.stdout
    assert "camelot:" not in result.stdout
    assert "default/" in result.stdout


# ---------------------------------------------------------------------------
# FR-17 — an entity reached across a boundary is read-only
# ---------------------------------------------------------------------------


def test_a_foreign_delete_is_refused(nested_tree, monkeypatch):
    # nested-projects-spec — FR-17 / D-7 / failure table: the read-only rule
    # lives in the core and the CLI reports it at exit 1
    author_entities(nested_tree)
    monkeypatch.chdir(nested_tree / "lore")

    result = run("watcher", "delete", "camelot:nested-watcher")

    assert result.exit_code == 1
    assert result.stderr == (
        'Cannot write "camelot:nested-watcher": '
        "an entity from another project is read-only.\n"
    )
    assert (nested_tree / ".lore" / "watchers" / "nested-watcher.yaml").exists()


def test_a_foreign_edit_is_refused_as_the_error_envelope(
    nested_tree, monkeypatch, tmp_path
):
    # nested-projects-spec — FR-17: {"error": …} on stderr under --json, same
    # exit code, and the ancestor's file is untouched afterwards
    author_entities(nested_tree)
    target = nested_tree / ".lore" / "watchers" / "nested-watcher.yaml"
    before = target.read_bytes()
    source = tmp_path / "replacement.yaml"
    source.write_text("id: nested-watcher\ntitle: Mine\nsummary: Mine.\n")
    monkeypatch.chdir(nested_tree / "lore")

    result = run(
        "--json", "watcher", "edit", "camelot:nested-watcher", "-f", str(source)
    )

    assert result.exit_code == 1
    assert json.loads(result.stderr) == {
        "error": 'Cannot write "camelot:nested-watcher": '
        "an entity from another project is read-only."
    }
    assert target.read_bytes() == before


@pytest.mark.parametrize(
    "argv",
    [
        ("codex", "delete", "camelot:camelot-dispatch-contract"),
        ("knight", "delete", "camelot:nested-knight"),
        ("artifact", "delete", "camelot:nested-artifact"),
        ("doctrine", "delete", "camelot:nested-doctrine"),
    ],
)
def test_a_foreign_delete_is_refused_on_every_frontmatter_entity(
    nested_tree, monkeypatch, argv
):
    # nested-projects-spec — FR-17 / D-7: `cli._validate_name` runs ahead of
    # the core on these four kinds and its regex rejects a colon, so without
    # deferring to `projects.is_qualified` the user sees "Invalid name: …"
    # instead of the read-only refusal the failure table pins.
    author_entities(nested_tree)
    monkeypatch.chdir(nested_tree / "lore")

    result = run(*argv)

    assert result.exit_code == 1
    assert result.stderr == (
        f'Cannot write "{argv[2]}": '
        "an entity from another project is read-only.\n"
    )


def test_a_foreign_codex_edit_from_a_file_is_refused(nested_tree, monkeypatch, tmp_path):
    # nested-projects-spec — FR-17: the Part 4 scenario's command, on the
    # content-replacing path that reaches `codex.update_document`
    target = nested_tree / ".lore" / "codex" / "camelot-dispatch-contract.md"
    before = target.read_bytes()
    source = tmp_path / "mine.md"
    source.write_text(
        "---\nid: camelot-dispatch-contract\ntitle: Mine\nsummary: Mine.\n---\n\nMine.\n"
    )
    monkeypatch.chdir(nested_tree / "lore")

    result = run("codex", "edit", "camelot:camelot-dispatch-contract", "-f", str(source))

    assert result.exit_code == 1
    assert result.stderr == (
        'Cannot write "camelot:camelot-dispatch-contract": '
        "an entity from another project is read-only.\n"
    )
    assert target.read_bytes() == before


def test_an_invalid_bare_name_still_fails_name_validation(nested_tree, monkeypatch):
    # nested-projects-spec — the read-only refusal takes precedence for a
    # qualified id only; a bare name that is not a legal entity name is still
    # answered by the CLI's own pre-flight, exactly as before (SC-7).
    monkeypatch.chdir(nested_tree / "lore")

    result = run("codex", "delete", "has space")

    assert result.exit_code == 1
    assert result.stderr == (
        "Invalid name: must start with alphanumeric and contain only letters, "
        "digits, hyphens, underscores.\n"
    )


def test_the_part_four_field_edit_scenario_is_refused(nested_tree, monkeypatch):
    # nested-projects-spec — FR-17 / Part 4's own scenario. `--set` routes
    # through `frontmatter_edit.update_frontmatter_fields`, a public write
    # function D-7's wording covers and no lane's Project Structure row names.
    target = nested_tree / ".lore" / "codex" / "camelot-dispatch-contract.md"
    before = target.read_bytes()
    monkeypatch.chdir(nested_tree / "lore")

    result = run(
        "codex", "edit", "camelot:camelot-dispatch-contract", "--set", "title=Mine"
    )

    assert result.exit_code == 1
    assert result.stderr == (
        'Cannot write "camelot:camelot-dispatch-contract": '
        "an entity from another project is read-only.\n"
    )
    assert target.read_bytes() == before


@pytest.mark.parametrize(
    "kind,entity_id",
    [
        ("knight", "camelot:nested-knight"),
        ("artifact", "camelot:nested-artifact"),
        ("watcher", "camelot:nested-watcher"),
    ],
)
def test_a_foreign_field_edit_is_refused_on_every_kind(
    nested_tree, monkeypatch, kind, entity_id
):
    # nested-projects-spec — FR-17: the field-edit path is one function, so
    # the rule holds for every entity kind that reaches it
    author_entities(nested_tree)
    monkeypatch.chdir(nested_tree / "lore")

    result = run(kind, "edit", entity_id, "--set", "title=Mine")

    assert result.exit_code == 1
    assert result.stderr == (
        f'Cannot write "{entity_id}": '
        "an entity from another project is read-only.\n"
    )


# ---------------------------------------------------------------------------
# S5 — `watcher show` reads an inherited watcher
# ---------------------------------------------------------------------------


def test_watcher_show_prints_an_inherited_watchers_file(nested_tree, monkeypatch):
    # nested-projects-spec — W4 / FR-13a. Inheritance is unconditional, so
    # `watcher list` already carries this row; `show` must print the owning
    # project's file rather than look for it in the reader's own directory.
    author_entities(nested_tree)
    (nested_tree / ".lore" / "config.toml").write_text(
        'project-name = "camelot"\n\n[shared]\nexports = ["*"]\n', encoding="utf-8"
    )
    source = nested_tree / ".lore" / "watchers" / "nested-watcher.yaml"
    monkeypatch.chdir(nested_tree / "lore")

    result = run("watcher", "show", "camelot:nested-watcher")

    assert result.exit_code == 0, result.output
    assert result.stdout == source.read_text(encoding="utf-8")


def test_watcher_show_reads_a_named_descendant(realm_tree):
    # nested-projects-spec — FR-13a: `--project` is accepted on `watcher show`
    source = realm_tree / "realm" / ".lore" / "watchers" / "nested-watcher.yaml"

    result = run("--project", "realm", "watcher", "show", "realm:nested-watcher")

    assert result.exit_code == 0, result.output
    assert result.stdout == source.read_text(encoding="utf-8")


def test_watcher_show_json_envelope_is_unchanged(realm_tree):
    # nested-projects-spec — the record is the `--json` envelope, so it gains
    # no key: the raw text is a second entry shape, not a tenth field
    result = run("--json", "--project", "realm", "watcher", "show", "realm:nested-watcher")

    assert result.exit_code == 0, result.output
    assert set(json.loads(result.stdout)) == {
        "id",
        "group",
        "title",
        "summary",
        "filename",
        "watch_target",
        "interval",
        "action",
        "origin",
    }


def test_watcher_show_still_misses_an_unknown_name(nested_tree, monkeypatch):
    # nested-projects-spec — a miss stays a miss, at the message it had
    monkeypatch.chdir(nested_tree / "lore")

    result = run("watcher", "show", "camelot:nope")

    assert result.exit_code == 1
    assert result.stderr == 'Watcher "camelot:nope" not found.\n'


# ---------------------------------------------------------------------------
# FR-14 — --project is a read selector
# ---------------------------------------------------------------------------


def test_project_is_rejected_on_a_write_command(nested_tree, tmp_path):
    # nested-projects-spec — FR-14 / D-6 / failure table: a usage error at
    # exit 2, because which flags a command accepts is argument parsing
    source = tmp_path / "draft.md"
    source.write_text("---\nid: x\ntitle: X\nsummary: S\n---\n\nBody.\n")

    result = run("--project", "realm", "codex", "new", "x", "-f", str(source))

    assert result.exit_code == 2
    assert (
        'Error: --project is a read selector; it is not accepted on "codex new".'
        in result.stderr
    )


def test_project_is_rejected_on_a_mission_command(nested_tree):
    # nested-projects-spec — FR-14: no quest or mission command takes it
    result = run("--project", "realm", "claim", "q-aaaa/m-bbbb")

    assert result.exit_code == 2
    assert (
        'Error: --project is a read selector; it is not accepted on "claim".'
        in result.stderr
    )


def test_project_is_rejected_on_the_bare_dashboard(nested_tree):
    # nested-projects-spec — FR-14: `lore` with no subcommand is a quest
    # read, and the label is the command's own name, never "lore None"
    result = run("--project", "all")

    assert result.exit_code == 2
    assert (
        'Error: --project is a read selector; it is not accepted on "lore".'
        in result.stderr
    )


def test_project_is_rejected_on_a_bare_group(nested_tree):
    # nested-projects-spec — FR-14: `glossary` is invoke_without_command, so
    # its own invoke sees no subcommand and must not interpolate None
    result = run("--project", "all", "glossary")

    assert result.exit_code == 2
    assert (
        'Error: --project is a read selector; it is not accepted on "glossary".'
        in result.stderr
    )


def test_project_is_rejected_on_init(nested_tree):
    # nested-projects-spec — FR-14: the gate runs in `invoke`, ahead of
    # main's body, so the existing `init` early-return never sees it
    result = run("--project", "realm", "init")

    assert result.exit_code == 2
    assert (
        'Error: --project is a read selector; it is not accepted on "init".'
        in result.stderr
    )


def test_the_rejection_is_the_error_envelope_under_json(nested_tree, tmp_path):
    # nested-projects-spec — FR-14: `codex map`'s ConflictingDepthFlags
    # precedent — an envelope on stderr, still exit 2
    source = tmp_path / "draft.md"
    source.write_text("---\nid: x\ntitle: X\nsummary: S\n---\n\nBody.\n")

    result = run("--json", "--project", "realm", "codex", "new", "x", "-f", str(source))

    assert result.exit_code == 2
    assert json.loads(result.stderr) == {
        "error": '--project is a read selector; it is not accepted on "codex new".'
    }


# ---------------------------------------------------------------------------
# W6 — which projects does a document touch
# ---------------------------------------------------------------------------


def test_cross_project_map_reports_one_row_per_participating_project(nested_tree):
    # nested-projects-spec — W6 / SC-4 / FR-21 / X-1: built on
    # `--depth-out 1 --depth-in 0`, the form that returns the direct
    # neighbour set on today's engine
    result = run("--project", "all", *W6_MAP_ARGV)

    assert result.exit_code == 0, result.output
    assert lines(result.stdout) == W6_MAP_TABLE


def test_a_moved_descendant_degrades_to_a_missing_row(nested_tree):
    # nested-projects-spec — N-7 / W6: a `related` entry that resolves to
    # nothing drops out; no read command fails because a project went away
    import shutil

    shutil.rmtree(nested_tree / "citadel")

    result = run("--project", "all", *W6_MAP_ARGV)

    assert result.exit_code == 0, result.output
    assert lines(result.stdout) == W6_MAP_TABLE_WITHOUT_CITADEL


def test_cross_project_map_json_carries_origin(nested_tree):
    # nested-projects-spec — W6 / FR-16: the envelope key stays `codex` in
    # default mode and every row carries `origin`
    result = run("--json", "--project", "all", *W6_MAP_ARGV)

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "codex": [
            {
                "id": "citadel:tech-views",
                "group": "technical",
                "title": "Views",
                "summary": "The screens Citadel renders.",
                "origin": "citadel",
            },
            {
                "id": "lore:tech-db-schema",
                "group": "technical",
                "title": "DB Schema",
                "summary": "The SQLite schema Lore stores state in.",
                "origin": "lore",
            },
            {
                "id": "realm:tech-dispatch-loop",
                "group": "technical",
                "title": "Dispatch Loop",
                "summary": "How Realm turns a ready mission into a running agent.",
                "origin": "realm",
            },
        ]
    }


# ---------------------------------------------------------------------------
# S5 — the six remaining entity groups
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv,envelope_key,entity_id",
    [
        (("doctrine", "list"), "doctrines", "realm:nested-doctrine"),
        (("knight", "list"), "knights", "realm:nested-knight"),
        (("artifact", "list"), "artifacts", "realm:nested-artifact"),
        (("watcher", "list"), "watchers", "realm:nested-watcher"),
        (("rite", "list"), "rites", "realm:nested-rite"),
    ],
)
def test_a_scoped_list_keeps_its_envelope_key_and_gains_origin(
    realm_tree, argv, envelope_key, entity_id
):
    # nested-projects-spec — S5 / FR-16: every envelope key is the verified
    # one and every row gains `origin`. A named descendant's rows are
    # unfiltered, seeded defaults included: FR-10's exclusion governs
    # inheritance, never federation (D-4).
    result = run("--json", "--project", "realm", *argv)

    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)[envelope_key]
    assert entity_id in [row["id"] for row in rows]
    assert {row["origin"] for row in rows} == {"realm"}
    assert all(row["id"].startswith("realm:") for row in rows)


@pytest.mark.parametrize(
    "argv",
    [
        ("doctrine", "list"),
        ("knight", "list"),
        ("artifact", "list"),
        ("watcher", "list"),
        ("rite", "list"),
    ],
)
def test_a_scoped_list_leads_with_the_origin_column(realm_tree, argv):
    # nested-projects-spec — FR-16 / D-15: text mode gains the column only
    # when a non-`self` row is present, and then as the first column
    result = run("--project", "realm", *argv)

    assert result.exit_code == 0, result.output
    assert lines(result.stdout)[0].startswith("  ORIGIN  ")
    assert "  realm  " in lines(result.stdout)[1]


def test_a_scoped_doctrine_show_reads_the_foreign_pair(realm_tree):
    # nested-projects-spec — S5: `doctrine show` is a bare object and the
    # foreign design + yaml are read from the project that owns them
    result = run("--project", "realm", "doctrine", "show", "realm:nested-doctrine")

    assert result.exit_code == 0, result.output
    assert "# Nested Doctrine" in result.stdout
    assert "only-step" in result.stdout


def test_a_scoped_knight_show_reads_the_foreign_body(realm_tree):
    # nested-projects-spec — S5 / ADR-011: the JSON form is the record dict
    result = run("--json", "--project", "realm", "knight", "show", "realm:nested-knight")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["id"] == "realm:nested-knight"
    assert payload["origin"] == "realm"
    assert "# Nested Knight" in payload["body"]


def test_a_scoped_artifact_show_is_a_bare_record_with_origin(realm_tree):
    # nested-projects-spec — S5 / G16 amendment Section D: a single id is the
    # record dict, so `origin` is a top-level key
    result = run(
        "--json", "--project", "realm", "artifact", "show", "realm:nested-artifact"
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["id"] == "realm:nested-artifact"
    assert payload["origin"] == "realm"


def test_a_scoped_rite_show_inlines_the_foreign_rite(realm_tree):
    # nested-projects-spec — S5 / C5: `rite show` resolves through the new
    # scoped name and keeps the `rites` envelope
    result = run("--json", "--project", "realm", "rite", "show", "realm:nested-rite")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert [rite["id"] for rite in payload["rites"]] == ["realm:nested-rite"]
    assert payload["rites"][0]["origin"] == "realm"


def test_a_scoped_rite_search_keeps_its_three_keys_and_gains_origin(realm_tree):
    # nested-projects-spec — obligation 3 / ADR-016: `rite search`'s envelope
    # carries no `group` today and gains none, even though the scoped rows do
    result = run("--json", "--project", "realm", "rite", "search", "dispatch")

    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)["rites"]
    assert [row["id"] for row in rows] == ["realm:nested-rite"]
    assert set(rows[0]) == {"id", "trigger", "summary", "origin"}


def test_a_scoped_rite_list_keeps_group_beside_origin(realm_tree):
    # nested-projects-spec — decisions-016 as revised: `origin` is added
    # beside `group`, never instead of it
    result = run("--json", "--project", "realm", "rite", "list")

    assert result.exit_code == 0, result.output
    row = json.loads(result.stdout)["rites"][0]
    assert row["group"] is None
    assert row["origin"] == "realm"


def test_a_scoped_glossary_list_carries_origin(realm_tree):
    # nested-projects-spec — S5 / D-22: an inherited keyword stays bare and
    # carries its origin
    result = run("--json", "--project", "realm", "glossary", "list")

    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)["glossary"]
    assert [row["keyword"] for row in rows] == ["Dispatcher"]
    assert rows[0]["origin"] == "realm"


def test_a_scoped_glossary_list_leads_with_the_origin_column(realm_tree):
    # nested-projects-spec — FR-16: the glossary table gains the same
    # conditional column in the padding shape it already prints
    result = run("--project", "realm", "glossary", "list")

    assert result.exit_code == 0, result.output
    assert lines(result.stdout)[0].startswith("ORIGIN ")
    assert lines(result.stdout)[1].startswith("realm ")


def test_a_scoped_glossary_search_carries_origin(realm_tree):
    # nested-projects-spec — S5: `glossary search` keeps the `glossary` key
    result = run("--json", "--project", "realm", "glossary", "search", "dispatch")

    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)["glossary"]
    assert [row["keyword"] for row in rows] == ["Dispatcher"]
    assert rows[0]["origin"] == "realm"


def test_a_scoped_glossary_show_carries_origin(realm_tree):
    # nested-projects-spec — S5: `glossary show` keeps the `glossary` key and
    # gains no ORIGIN column, because it renders blocks and not a table
    result = run("--json", "--project", "realm", "glossary", "show", "Dispatcher")

    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)["glossary"]
    assert rows[0]["origin"] == "realm"


def test_a_scoped_codex_show_carries_the_qualified_header(nested_tree):
    # nested-projects-spec — S4: `codex show` keeps {documents, glossary} and
    # the `=== <id> ===` header carries the qualified id
    result = run("--json", "--project", "realm", "codex", "show", "realm:tech-dispatch-loop")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert set(payload) == {"documents", "glossary"}
    assert payload["documents"][0]["id"] == "realm:tech-dispatch-loop"
    assert payload["documents"][0]["origin"] == "realm"


def test_codex_map_full_keeps_the_documents_key(nested_tree):
    # nested-projects-spec — S4: `--full` switches the envelope key to
    # `documents` and the records reach it verbatim, `origin` included
    result = run("--json", "--project", "all", *W6_MAP_ARGV, "--full")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert set(payload) == {"documents"}
    assert {doc["origin"] for doc in payload["documents"]} == {
        "citadel",
        "lore",
        "realm",
    }


# ---------------------------------------------------------------------------
# S6 — impacts
# ---------------------------------------------------------------------------


def test_impacts_on_a_codex_seed_under_project(nested_tree):
    # nested-projects-spec — D-28: a codex-id seed is split by D-8 and run
    # against the resolved project's codex
    result = run("--json", "--project", "all", "impacts", "camelot-dispatch-contract")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"impacts": []}


def test_impacts_on_a_path_seed_resolves_per_project(nested_tree):
    # nested-projects-spec — D-28: a repo-relative path means a different
    # file in each project, so it is resolved against each in-scope root and
    # every row carries `origin`
    (nested_tree / ".lore" / "codex" / "tech-binder.md").write_text(
        "---\nid: tech-binder\ntitle: Binder\nsummary: Binds code.\n"
        "binds:\n  - src/app.py\n---\n\nBody.\n",
        encoding="utf-8",
    )
    (nested_tree / "realm" / ".lore" / "codex" / "tech-realm-binder.md").write_text(
        "---\nid: tech-realm-binder\ntitle: Realm Binder\nsummary: Binds code.\n"
        "binds:\n  - src/app.py\n---\n\nBody.\n",
        encoding="utf-8",
    )

    result = run("--json", "--project", "all", "impacts", "src/app.py")

    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)["impacts"]
    assert {(row["id"], row["origin"]) for row in rows} == {
        ("tech-binder", "self"),
        ("realm:tech-realm-binder", "realm"),
    }


def test_impacts_line_output_has_no_origin_column(nested_tree):
    # nested-projects-spec — D-28: `impacts` renders bare lines, so a foreign
    # code-seed id is qualified and no ORIGIN column is added
    (nested_tree / "realm" / ".lore" / "codex" / "tech-realm-binder.md").write_text(
        "---\nid: tech-realm-binder\ntitle: Realm Binder\nsummary: Binds code.\n"
        "binds:\n  - src/app.py\n---\n\nBody.\n",
        encoding="utf-8",
    )

    result = run("--project", "all", "impacts", "src/app.py")

    assert result.exit_code == 0, result.output
    assert result.stdout == "realm:tech-realm-binder\n"


# ---------------------------------------------------------------------------
# W5 — adopting a tree
# ---------------------------------------------------------------------------


def test_lore_init_asks_no_new_question_and_seeds_both_keys(tmp_path, monkeypatch):
    # nested-projects-spec — W5 / FR-1 / FR-2: `lore init` gains no new
    # behaviour; `render_default_settings()` writes every known key
    monkeypatch.chdir(tmp_path)

    result = run("init")

    assert result.exit_code == 0, result.output
    config = (tmp_path / ".lore" / "config.toml").read_text(encoding="utf-8")
    assert 'project-name = ""' in config
    assert 'default-project-scope = "self"' in config


def test_adopting_a_tree_lists_every_project(nested_tree):
    # nested-projects-spec — W5: `--project all` spans the ancestor and its
    # three descendants, and none of them gained a file
    result = run("--json", "--project", "all", "codex", "list")

    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)["codex"]
    assert {row["origin"] for row in rows} == {"self", "lore", "realm", "citadel"}


def test_the_schema_version_is_unchanged(nested_tree):
    # nested-projects-spec — SC-9 / N-10: no state crosses a boundary, so
    # there is no migration
    from lore.db import SCHEMA_VERSION

    assert SCHEMA_VERSION == 6


# ---------------------------------------------------------------------------
# S7 — --help teaches the concept
# ---------------------------------------------------------------------------


def test_top_level_help_teaches_the_tree(project_dir):
    # nested-projects-spec — decisions-008: one concept sentence at the top
    # level, self-contained and carrying no codex id
    result = run("--help")

    assert result.exit_code == 0, result.output
    assert (
        "A directory holding several Lore projects is itself a Lore project"
        in result.stdout
    )
    assert "conceptual-workflows-nested-projects" not in result.stdout


@pytest.mark.parametrize(
    "group",
    ["codex", "doctrine", "knight", "artifact", "watcher", "rite", "glossary"],
)
def test_each_affected_group_help_names_the_selector(project_dir, group):
    # nested-projects-spec — decisions-008: one sentence per affected group,
    # and no enrichment below the group level
    result = run(group, "--help")

    assert result.exit_code == 0, result.output
    assert (
        "Pass --project <name> or --project all to read the same entities in "
        "another project in this tree." in " ".join(result.stdout.split())
    )


def test_the_project_option_help_is_one_line(project_dir):
    # nested-projects-spec — decisions-008: flag help stays terse
    result = run("--help")

    assert result.exit_code == 0, result.output
    assert "--project NAME" in result.stdout
    assert "Read another project in this tree" in " ".join(result.stdout.split())
