"""Unit tests for lore.projects — topology, export resolution, qualification.

Spec: nested-projects-spec (lore codex show nested-projects-spec) — F5..F10
Decisions: D-1 (one home for topology), D-2 (the reader callback), D-3 (two
           axes), D-4 (what each scope returns), D-7 (the read-only rule),
           D-8 (origin-qualified ids), D-9 (the ID-glob matcher), D-10 (seeded
           defaults), D-11 (path identity), D-13/D-14 (the two walks),
           D-16 (ordering), A-2 (transient and sources never export)
Standards: standards-dry, standards-single-responsibility,
           standards-dependency-inversion

``projects.py`` owns topology, export resolution and qualification and nothing
else. It never reads an entity file — a caller hands it a reader — so every
test here builds a real tree on disk and passes its own callback.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(root: Path, config: str = "") -> Path:
    """Create ``root/.lore/`` and, when given, ``root/.lore/config.toml``."""
    (root / ".lore").mkdir(parents=True, exist_ok=True)
    if config:
        (root / ".lore" / "config.toml").write_text(config, encoding="utf-8")
    return root


@pytest.fixture(autouse=True)
def _reset_warned_latch():
    """Reset ``config._warned`` so each test sees a fresh latch.

    ``projects`` reads configs through ``config.load_config``, which emits at
    most one warning per process. A test asserting on stderr needs the latch
    open.
    """
    import lore.config as cfg_mod

    cfg_mod._warned = False
    yield
    cfg_mod._warned = False


# ---------------------------------------------------------------------------
# F5 — the ID algebra
# ---------------------------------------------------------------------------


class TestSplitQualified:
    def test_a_qualified_token_splits_into_origin_and_id(self):
        # nested-projects-spec — D-8
        from lore.projects import split_qualified

        assert split_qualified("camelot:x") == ("camelot", "x")

    def test_a_bare_token_has_no_origin(self):
        # nested-projects-spec — D-8: the whole token is a local ID
        from lore.projects import split_qualified

        assert split_qualified("x") == (None, "x")

    def test_it_splits_on_the_first_colon_only(self):
        # nested-projects-spec — D-8: codex ids are free-form, so a local id
        # holding a colon must keep working
        from lore.projects import split_qualified

        assert split_qualified("a:b:c") == ("a", "b:c")

    def test_it_performs_no_resolution(self):
        # nested-projects-spec — D-8: deciding whether the left half names a
        # real project is the caller's job
        from lore.projects import split_qualified

        assert split_qualified("no-such-project:x") == ("no-such-project", "x")


class TestQualify:
    def test_it_joins_an_origin_to_an_id(self):
        # nested-projects-spec — FR-15
        from lore.projects import qualify

        assert qualify("camelot", "x") == "camelot:x"

    def test_the_self_origin_leaves_the_id_bare(self):
        # nested-projects-spec — FR-16: a self row is never qualified
        from lore.projects import qualify

        assert qualify("self", "x") == "x"

    def test_qualify_round_trips_through_split_qualified(self):
        # nested-projects-spec — D-8
        from lore.projects import qualify, split_qualified

        for origin in ("camelot", "lore-2", "a_b"):
            for entity_id in ("x", "tech-arch-db", "weird:id"):
                assert split_qualified(qualify(origin, entity_id)) == (
                    origin,
                    entity_id,
                )


class TestIsQualified:
    def test_it_is_true_for_a_qualified_token(self):
        from lore.projects import is_qualified

        assert is_qualified("camelot:x") is True

    def test_it_is_false_for_a_bare_token(self):
        from lore.projects import is_qualified

        assert is_qualified("x") is False

    def test_it_agrees_with_split_qualified(self):
        # nested-projects-spec — `is_qualified(t)` is `split_qualified(t)[0] is
        # not None`, and is the only place that question is answered
        from lore.projects import is_qualified, split_qualified

        for token in ("x", "a:b", "a:b:c", "x-y", ":x"):
            assert is_qualified(token) is (split_qualified(token)[0] is not None)


class TestIndexKey:
    def test_a_qualifier_equal_to_our_own_name_is_stripped(self):
        # nested-projects-spec — D-17: an ancestor's `related: [lore:x]`, read
        # from inside `lore`, resolves to the local `x`
        from lore.projects import index_key

        assert index_key("lore:x", self_name="lore") == "x"

    def test_another_project_qualifier_is_left_alone(self):
        # nested-projects-spec — D-17
        from lore.projects import index_key

        assert index_key("realm:x", self_name="lore") == "realm:x"

    def test_a_bare_entry_is_left_alone(self):
        # nested-projects-spec — D-17
        from lore.projects import index_key

        assert index_key("x", self_name="lore") == "x"


class TestMatchesExport:
    def test_a_non_glob_pattern_is_compared_literally(self):
        # nested-projects-spec — D-9
        from lore.projects import matches_export

        assert matches_export("standards-dry", "standards-dry") is True

    def test_a_strict_prefix_is_not_a_match(self):
        # nested-projects-spec — D-9: a literal pattern is equality, never a
        # prefix test
        from lore.projects import matches_export

        assert matches_export("standards-dry", "standards") is False

    def test_a_star_glob_matches_the_prefix_family(self):
        # nested-projects-spec — FR-5
        from lore.projects import matches_export

        assert matches_export("standards-dry", "standards-*") is True

    def test_a_star_glob_does_not_match_a_mid_string_hit(self):
        # nested-projects-spec — FR-5: the pattern is anchored at both ends
        from lore.projects import matches_export

        assert matches_export("tech-standards", "standards-*") is False

    def test_a_question_mark_matches_exactly_one_character(self):
        # nested-projects-spec — FR-5
        from lore.projects import matches_export

        assert matches_export("us-1", "us-?") is True
        assert matches_export("us-12", "us-?") is False

    def test_a_character_class_behaves(self):
        # nested-projects-spec — FR-5
        from lore.projects import matches_export

        assert matches_export("us-a", "us-[ab]") is True
        assert matches_export("us-c", "us-[ab]") is False

    def test_matching_is_case_sensitive_on_every_platform(self):
        # nested-projects-spec — D-9: `fnmatchcase`, never `fnmatch`, so macOS
        # and Linux cannot disagree
        from lore.projects import matches_export

        assert matches_export("STANDARDS-dry", "standards-*") is False
        assert matches_export("standards-dry", "STANDARDS-*") is False

    def test_a_pattern_carrying_a_slash_matches_nothing(self):
        # nested-projects-spec — D-9: entity ids carry no path separator, so
        # path semantics have no meaning here
        from lore.projects import matches_export

        assert matches_export("standards-dry", "standards/*") is False

    def test_it_classifies_through_the_one_glob_classifier(self):
        # nested-projects-spec — D-9 / standards-dry: `is_glob_pattern`
        # classifies, `fnmatchcase` matches; no second classifier
        from lore.projects import matches_export
        from lore.validators import is_glob_pattern

        assert is_glob_pattern("standards-*") is True
        assert is_glob_pattern("standards-dry") is False
        assert matches_export("standards-*", "standards-*") is True


class TestIsSeededDefault:
    @pytest.mark.parametrize("group", ["default", "default/x", "default/x/y"])
    def test_the_default_subtree_is_seeded(self, group):
        # nested-projects-spec — D-10 / A-3
        from lore.projects import is_seeded_default

        assert is_seeded_default(group) is True

    @pytest.mark.parametrize("group", ["", "defaults", "x/default", "Default"])
    def test_everything_else_is_authored(self, group):
        # nested-projects-spec — D-10: the boundary is the group prefix, not a
        # substring
        from lore.projects import is_seeded_default

        assert is_seeded_default(group) is False


class TestRejectForeign:
    def test_a_bare_id_is_writable(self):
        # nested-projects-spec — D-7 / FR-17
        from lore.projects import reject_foreign

        assert reject_foreign("tech-arch-db") is None

    def test_a_qualified_id_raises_with_the_exact_message(self):
        # nested-projects-spec — SC-5: the exact stderr line
        from lore.projects import ForeignEntityError, reject_foreign

        with pytest.raises(ForeignEntityError) as excinfo:
            reject_foreign("camelot:camelot-dispatch-contract")
        assert str(excinfo.value) == (
            'Cannot write "camelot:camelot-dispatch-contract": '
            "an entity from another project is read-only."
        )


# ---------------------------------------------------------------------------
# F6 — ProjectRef, project_name, resolve_ancestors
# ---------------------------------------------------------------------------


class TestProjectRef:
    def test_it_carries_a_name_a_root_and_a_relation(self, tmp_path):
        # nested-projects-spec — Part 2 Python API surface
        from lore.projects import ProjectRef

        ref = ProjectRef(name="lore", root=tmp_path, relation="self")
        assert (ref.name, ref.root, ref.relation) == ("lore", tmp_path, "self")

    def test_it_is_frozen(self, tmp_path):
        import dataclasses

        from lore.projects import ProjectRef

        ref = ProjectRef(name="lore", root=tmp_path, relation="self")
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(ref, "name", "other")


class TestProjectName:
    def test_it_falls_back_to_the_directory_name(self, tmp_path):
        # nested-projects-spec — FR-1
        from lore.projects import project_name

        root = _make_project(tmp_path / "camelot")
        assert project_name(root) == "camelot"

    def test_an_empty_config_value_falls_back_to_the_directory_name(self, tmp_path):
        # nested-projects-spec — FR-1 / D-24
        from lore.projects import project_name

        root = _make_project(tmp_path / "camelot", 'project-name = ""\n')
        assert project_name(root) == "camelot"

    def test_a_configured_name_wins(self, tmp_path):
        # nested-projects-spec — FR-1 / A-5: a project names itself
        from lore.projects import project_name

        root = _make_project(tmp_path / "on-disk", 'project-name = "camelot"\n')
        assert project_name(root) == "camelot"

    def test_an_unusable_config_never_raises(self, tmp_path, capsys):
        # nested-projects-spec — N-9: a project's own entities stay resolvable
        from lore.projects import project_name

        root = _make_project(tmp_path / "camelot", "not = = toml\n")
        assert project_name(root) == "camelot"
        capsys.readouterr()


class TestResolveAncestors:
    def test_a_project_with_no_ancestor_has_none(self, tmp_path):
        # nested-projects-spec — FR-8
        from lore.projects import resolve_ancestors

        root = _make_project(tmp_path / "solo")
        assert resolve_ancestors(root) == ()

    def test_an_ancestor_with_no_export_table_is_inert(self, tmp_path):
        # nested-projects-spec — D-14: a stray `.lore/` above a project
        # exports nothing, so it is not an ancestor for this purpose
        from lore.projects import resolve_ancestors

        _make_project(tmp_path / "above")
        root = _make_project(tmp_path / "above" / "lore")
        assert resolve_ancestors(root) == ()

    def test_a_shared_exports_block_makes_a_directory_an_ancestor(self, tmp_path):
        # nested-projects-spec — FR-3 / FR-8
        from lore.projects import resolve_ancestors

        _make_project(tmp_path / "camelot", '[shared]\nexports = ["standards-*"]\n')
        root = _make_project(tmp_path / "camelot" / "lore")

        refs = resolve_ancestors(root)
        assert len(refs) == 1
        assert refs[0].name == "camelot"
        assert refs[0].root == (tmp_path / "camelot").resolve()
        assert refs[0].relation == "ancestor"

    def test_a_glossary_export_alone_makes_a_directory_an_ancestor(self, tmp_path):
        # nested-projects-spec — FR-3: `glossary = true` is an export
        from lore.projects import resolve_ancestors

        _make_project(tmp_path / "camelot", "[shared]\nglossary = true\n")
        root = _make_project(tmp_path / "camelot" / "lore")

        assert [ref.name for ref in resolve_ancestors(root)] == ["camelot"]

    def test_an_empty_shared_block_exports_nothing(self, tmp_path):
        # nested-projects-spec — D-14
        from lore.projects import resolve_ancestors

        _make_project(tmp_path / "camelot", "[shared]\nexports = []\n")
        root = _make_project(tmp_path / "camelot" / "lore")

        assert resolve_ancestors(root) == ()

    def test_a_descendants_block_naming_this_project_makes_an_ancestor(self, tmp_path):
        # nested-projects-spec — FR-4 / D-11: identity is the block's `path`
        from lore.projects import resolve_ancestors

        _make_project(
            tmp_path / "camelot",
            '[[descendants]]\nname = "whatever"\npath = "lore"\nexports = ["x"]\n',
        )
        root = _make_project(tmp_path / "camelot" / "lore")

        assert [ref.name for ref in resolve_ancestors(root)] == ["camelot"]

    def test_a_descendants_block_naming_another_project_is_inert(self, tmp_path):
        # nested-projects-spec — D-11 / FR-9: no intermediate project relays
        from lore.projects import resolve_ancestors

        _make_project(
            tmp_path / "camelot",
            '[[descendants]]\nname = "realm"\npath = "realm"\n',
        )
        root = _make_project(tmp_path / "camelot" / "lore")

        assert resolve_ancestors(root) == ()

    def test_an_ancestor_reaches_a_project_at_any_depth(self, tmp_path):
        # nested-projects-spec — FR-9: at any depth, with no relay
        from lore.projects import resolve_ancestors

        _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        root = _make_project(tmp_path / "camelot" / "apps" / "lore")

        assert [ref.name for ref in resolve_ancestors(root)] == ["camelot"]

    def test_two_ancestors_come_back_nearest_first(self, tmp_path):
        # nested-projects-spec — D-14: nearest ancestor first
        from lore.projects import resolve_ancestors

        _make_project(tmp_path / "top", '[shared]\nexports = ["*"]\n')
        _make_project(tmp_path / "top" / "mid", '[shared]\nexports = ["*"]\n')
        root = _make_project(tmp_path / "top" / "mid" / "leaf")

        assert [ref.name for ref in resolve_ancestors(root)] == ["mid", "top"]

    def test_an_unparseable_ancestor_config_yields_no_ref_and_no_raise(
        self, tmp_path, capsys
    ):
        # nested-projects-spec — N-7 / N-9: a broken config above never breaks
        # a project's own commands
        from lore.projects import resolve_ancestors

        _make_project(tmp_path / "camelot", "this is = = not toml\n")
        root = _make_project(tmp_path / "camelot" / "lore")

        assert resolve_ancestors(root) == ()
        capsys.readouterr()

    def test_the_walk_reads_at_most_one_config_per_directory(
        self, tmp_path, monkeypatch
    ):
        # nested-projects-spec — N-4: the cost budget, stated exactly.
        # Counting `Path.open` rather than trusting the environment is the
        # convention Part 4 sets for this assertion; monkeypatch only counts,
        # it never replaces behaviour.
        from lore.projects import resolve_ancestors

        _make_project(tmp_path / "top", '[shared]\nexports = ["*"]\n')
        (tmp_path / "top" / "mid").mkdir()
        _make_project(tmp_path / "top" / "mid" / "leaf")

        opened: list[Path] = []
        real_open = Path.open

        def counting_open(self, *args, **kwargs):
            opened.append(Path(self))
            return real_open(self, *args, **kwargs)

        monkeypatch.setattr(Path, "open", counting_open)
        resolve_ancestors(tmp_path / "top" / "mid" / "leaf")

        configs = [p for p in opened if p.name == "config.toml"]
        assert configs == [(tmp_path / "top" / ".lore" / "config.toml").resolve()]

    def test_an_ancestor_carries_its_configured_name(self, tmp_path):
        # nested-projects-spec — A-5: a project's name is its own to set
        from lore.projects import resolve_ancestors

        _make_project(
            tmp_path / "on-disk",
            'project-name = "camelot"\n[shared]\nexports = ["*"]\n',
        )
        root = _make_project(tmp_path / "on-disk" / "lore")

        assert [ref.name for ref in resolve_ancestors(root)] == ["camelot"]


# ---------------------------------------------------------------------------
# F7 — discover_descendants
# ---------------------------------------------------------------------------


class TestDiscoverDescendants:
    def test_a_project_with_no_descendants_has_none(self, tmp_path):
        # nested-projects-spec — FR-7
        from lore.projects import discover_descendants

        root = _make_project(tmp_path / "solo")
        assert discover_descendants(root) == ()

    def test_it_finds_a_project_one_level_down(self, tmp_path):
        # nested-projects-spec — FR-7: no registration, a filesystem walk
        from lore.projects import discover_descendants

        root = _make_project(tmp_path / "camelot")
        _make_project(root / "lore")

        refs = discover_descendants(root)
        assert len(refs) == 1
        assert refs[0].name == "lore"
        assert refs[0].root == (root / "lore").resolve()
        assert refs[0].relation == "descendant"

    def test_it_finds_a_project_three_levels_down(self, tmp_path):
        # nested-projects-spec — FR-7 / design point 1: any depth
        from lore.projects import discover_descendants

        root = _make_project(tmp_path / "camelot")
        _make_project(root / "a" / "b" / "realm")

        assert [ref.name for ref in discover_descendants(root)] == ["realm"]

    def test_it_skips_the_project_root_itself(self, tmp_path):
        # nested-projects-spec — D-13
        from lore.projects import discover_descendants

        root = _make_project(tmp_path / "camelot")
        assert [ref.root for ref in discover_descendants(root)] == []

    @pytest.mark.parametrize(
        "pruned", [".git", "node_modules", ".venv", "__pycache__", ".lore"]
    )
    def test_it_prunes_the_directories_n3_names(self, tmp_path, pruned):
        # nested-projects-spec — N-3 / D-13: pruned in place, so the walk never
        # descends into them at all
        from lore.projects import discover_descendants

        root = _make_project(tmp_path / "camelot")
        _make_project(root / pruned / "buried")

        assert discover_descendants(root) == ()

    def test_it_descends_into_a_discovered_project(self, tmp_path):
        # nested-projects-spec — D-13: a project nested inside a project is
        # still found
        from lore.projects import discover_descendants

        root = _make_project(tmp_path / "camelot")
        _make_project(root / "lore")
        _make_project(root / "lore" / "plugin")

        assert [ref.name for ref in discover_descendants(root)] == ["lore", "plugin"]

    def test_it_does_not_follow_a_symlink_out_of_the_subtree(self, tmp_path):
        # nested-projects-spec — D-13 / N-5: `followlinks=False` prevents the
        # walk escaping the subtree
        from lore.projects import discover_descendants

        outside = tmp_path / "outside"
        _make_project(outside / "stranger")
        root = _make_project(tmp_path / "camelot")
        (root / "link").symlink_to(outside, target_is_directory=True)

        assert discover_descendants(root) == ()

    def test_results_are_sorted_by_name(self, tmp_path):
        # nested-projects-spec — F7
        from lore.projects import discover_descendants

        root = _make_project(tmp_path / "camelot")
        _make_project(root / "zulu")
        _make_project(root / "alpha")
        _make_project(root / "mike")

        assert [ref.name for ref in discover_descendants(root)] == [
            "alpha",
            "mike",
            "zulu",
        ]

    def test_a_descendant_carries_its_configured_name(self, tmp_path):
        # nested-projects-spec — A-5 / D-11: `--project <name>` matches a
        # project's own resolved name, never a block's label
        from lore.projects import discover_descendants

        root = _make_project(tmp_path / "camelot")
        _make_project(root / "on-disk", 'project-name = "realm"\n')

        assert [ref.name for ref in discover_descendants(root)] == ["realm"]

    def test_a_descendant_with_an_unreadable_config_is_still_returned(
        self, tmp_path, capsys
    ):
        # nested-projects-spec — a malformed config never removes a project
        # from the tree; it only removes its exports
        from lore.projects import discover_descendants

        root = _make_project(tmp_path / "camelot")
        _make_project(root / "lore", "not = = toml\n")

        assert [ref.name for ref in discover_descendants(root)] == ["lore"]
        capsys.readouterr()


# ---------------------------------------------------------------------------
# F8 — exported_ids, exports_glossary
# ---------------------------------------------------------------------------


class TestExportedIds:
    def test_a_shared_pattern_reaches_every_descendant(self, tmp_path):
        # nested-projects-spec — FR-3
        from lore.projects import ExportCandidate, exported_ids

        ancestor = _make_project(
            tmp_path / "camelot", '[shared]\nexports = ["standards-*"]\n'
        )
        descendant = _make_project(ancestor / "lore")

        assert exported_ids(
            ancestor,
            descendant,
            candidates=[
                ExportCandidate("standards-dry", group=""),
                ExportCandidate("tech-arch-db", group=""),
            ],
        ) == frozenset({"standards-dry"})

    def test_the_union_of_shared_and_the_matching_block_is_exported(self, tmp_path):
        # nested-projects-spec — FR-9: the union of exports from every
        # ancestor that names the project
        from lore.projects import ExportCandidate, exported_ids

        ancestor = _make_project(
            tmp_path / "camelot",
            '[shared]\nexports = ["standards-*"]\n\n'
            '[[descendants]]\nname = "lore"\npath = "lore"\n'
            'exports = ["camelot-dispatch-contract"]\n',
        )
        descendant = _make_project(ancestor / "lore")

        assert exported_ids(
            ancestor,
            descendant,
            candidates=[
                ExportCandidate("standards-dry", group=""),
                ExportCandidate("camelot-dispatch-contract", group=""),
                ExportCandidate("tech-arch-db", group=""),
            ],
        ) == frozenset({"standards-dry", "camelot-dispatch-contract"})

    def test_a_block_for_another_project_contributes_nothing(self, tmp_path):
        # nested-projects-spec — D-11: export resolution is keyed on `path`
        from lore.projects import ExportCandidate, exported_ids

        ancestor = _make_project(
            tmp_path / "camelot",
            '[[descendants]]\nname = "realm"\npath = "realm"\nexports = ["x"]\n',
        )
        descendant = _make_project(ancestor / "lore")

        assert (
            exported_ids(
                ancestor,
                descendant,
                candidates=[ExportCandidate("x", group="")],
            )
            == frozenset()
        )

    def test_a_block_label_that_disagrees_with_the_real_name_is_inert(self, tmp_path):
        # nested-projects-spec — D-11: a block `name` names nothing and breaks
        # nothing; the `path` is the identity
        from lore.projects import ExportCandidate, exported_ids

        ancestor = _make_project(
            tmp_path / "camelot",
            '[[descendants]]\nname = "mislabelled"\npath = "lore"\nexports = ["x"]\n',
        )
        descendant = _make_project(ancestor / "lore", 'project-name = "lore"\n')

        assert exported_ids(
            ancestor, descendant, candidates=[ExportCandidate("x", group="")]
        ) == frozenset({"x"})

    def test_no_export_configuration_exports_nothing(self, tmp_path):
        # nested-projects-spec — FR-3: exports are opt-in
        from lore.projects import ExportCandidate, exported_ids

        ancestor = _make_project(tmp_path / "camelot")
        descendant = _make_project(ancestor / "lore")

        assert (
            exported_ids(
                ancestor, descendant, candidates=[ExportCandidate("x", group="")]
            )
            == frozenset()
        )

    def test_a_seeded_default_is_excluded_even_when_a_pattern_matches(self, tmp_path):
        # nested-projects-spec — FR-10 / D-10: a project's own copy of a
        # seeded default is the only one that applies to it
        from lore.projects import ExportCandidate, exported_ids

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        assert exported_ids(
            ancestor,
            descendant,
            candidates=[
                ExportCandidate("tdd-implementation", group="default/feature"),
                ExportCandidate("update-changelog", group="default"),
                ExportCandidate("our-own", group="workflow"),
            ],
        ) == frozenset({"our-own"})

    def test_a_candidate_with_no_group_skips_the_seeded_default_filter(self, tmp_path):
        # nested-projects-spec — D-10: no codex document is a seeded default,
        # so there is nothing for the filter to remove
        from lore.projects import ExportCandidate, exported_ids

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        assert exported_ids(
            ancestor, descendant, candidates=[ExportCandidate("default")]
        ) == frozenset({"default"})

    def test_a_transient_codex_document_is_never_exportable(self, tmp_path):
        # nested-projects-spec — A-2: every export of a transient document is
        # a guaranteed future dangling reference in another repository
        from lore.paths import codex_dir
        from lore.projects import ExportCandidate, exported_ids

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        assert exported_ids(
            ancestor,
            descendant,
            candidates=[
                ExportCandidate(
                    "feature-spec",
                    path=codex_dir(ancestor) / "transient" / "feature-spec.md",
                ),
                ExportCandidate(
                    "standards-dry",
                    path=codex_dir(ancestor) / "standards" / "standards-dry.md",
                ),
            ],
        ) == frozenset({"standards-dry"})

    def test_a_source_codex_document_is_never_exportable(self, tmp_path):
        # nested-projects-spec — A-2: a source is disposable raw input whose
        # whole point is that deleting it dangles nothing
        from lore.paths import codex_dir
        from lore.projects import ExportCandidate, exported_ids

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        assert (
            exported_ids(
                ancestor,
                descendant,
                candidates=[
                    ExportCandidate(
                        "raw-notes",
                        path=codex_dir(ancestor) / "sources" / "raw-notes.md",
                    ),
                    ExportCandidate(
                        "nested-source",
                        path=codex_dir(ancestor)
                        / "sources"
                        / "team"
                        / "nested-source.md",
                    ),
                ],
            )
            == frozenset()
        )

    def test_a_path_outside_the_codex_tree_carries_no_layer(self, tmp_path):
        # nested-projects-spec — A-2: the layer question is a codex question;
        # a knight or doctrine path is not asked it
        from lore.paths import knights_dir
        from lore.projects import ExportCandidate, exported_ids

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        assert exported_ids(
            ancestor,
            descendant,
            candidates=[
                ExportCandidate(
                    "scout",
                    group="research",
                    path=knights_dir(ancestor) / "research" / "scout.md",
                )
            ],
        ) == frozenset({"scout"})


class TestExportsGlossary:
    def test_it_is_false_by_default(self, tmp_path):
        # nested-projects-spec — FR-3: the glossary is opt-in
        from lore.projects import exports_glossary

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        assert exports_glossary(ancestor, descendant) is False

    def test_it_is_true_when_the_shared_block_asks(self, tmp_path):
        # nested-projects-spec — FR-3 / D-22: the whole file is the export unit
        from lore.projects import exports_glossary

        ancestor = _make_project(tmp_path / "camelot", "[shared]\nglossary = true\n")
        descendant = _make_project(ancestor / "lore")

        assert exports_glossary(ancestor, descendant) is True

    def test_an_unreadable_ancestor_config_exports_no_glossary(self, tmp_path, capsys):
        # nested-projects-spec — N-9
        from lore.projects import exports_glossary

        ancestor = _make_project(tmp_path / "camelot", "not = = toml\n")
        descendant = _make_project(ancestor / "lore")

        assert exports_glossary(ancestor, descendant) is False
        capsys.readouterr()


# ---------------------------------------------------------------------------
# F9 — list_projects, resolve_project, resolve_scope
# ---------------------------------------------------------------------------


def _tree(tmp_path: Path) -> Path:
    """An ancestor exporting to one descendant, plus two more descendants."""
    ancestor = _make_project(
        tmp_path / "camelot",
        '[shared]\nexports = ["standards-*"]\n',
    )
    _make_project(ancestor / "lore")
    _make_project(ancestor / "realm")
    _make_project(ancestor / "citadel")
    return ancestor


class TestListProjects:
    def test_a_standalone_project_lists_only_itself(self, tmp_path):
        # nested-projects-spec — SC-6 / FR-11
        from lore.projects import list_projects

        root = _make_project(tmp_path / "solo")
        refs = list_projects(root)
        assert [(ref.name, ref.relation) for ref in refs] == [("solo", "self")]

    def test_the_order_is_self_then_ancestors_then_descendants(self, tmp_path):
        # nested-projects-spec — F9
        from lore.projects import list_projects

        ancestor = _tree(tmp_path)
        refs = list_projects(ancestor)
        assert [(ref.name, ref.relation) for ref in refs] == [
            ("camelot", "self"),
            ("citadel", "descendant"),
            ("lore", "descendant"),
            ("realm", "descendant"),
        ]

    def test_a_descendant_lists_itself_then_its_ancestor(self, tmp_path):
        # nested-projects-spec — F9: the self ref always comes first
        from lore.projects import list_projects

        ancestor = _tree(tmp_path)
        refs = list_projects(ancestor / "lore")
        assert [(ref.name, ref.relation) for ref in refs] == [
            ("lore", "self"),
            ("camelot", "ancestor"),
        ]


class TestResolveProject:
    def test_a_known_descendant_resolves(self, tmp_path):
        # nested-projects-spec — SC-2
        from lore.projects import resolve_project

        ancestor = _tree(tmp_path)
        ref = resolve_project(ancestor, "realm")
        assert (ref.name, ref.relation) == ("realm", "descendant")
        assert ref.root == (ancestor / "realm").resolve()

    def test_a_project_can_resolve_itself_by_name(self, tmp_path):
        # nested-projects-spec — D-25 / F9
        from lore.projects import resolve_project

        ancestor = _tree(tmp_path)
        assert resolve_project(ancestor, "camelot").relation == "self"

    def test_an_unknown_name_names_the_projects_that_are_in_scope(self, tmp_path):
        # nested-projects-spec — W2 / FR-18: the exact message
        from lore.projects import UnknownProjectError, resolve_project

        ancestor = _tree(tmp_path)
        with pytest.raises(UnknownProjectError) as excinfo:
            resolve_project(ancestor, "nope")
        assert str(excinfo.value) == (
            'Unknown project "nope". Projects in scope: citadel, lore, realm.'
        )

    def test_an_unknown_name_in_a_standalone_project_says_so(self, tmp_path):
        # nested-projects-spec — W2 / FR-18: the second exact message
        from lore.projects import UnknownProjectError, resolve_project

        root = _make_project(tmp_path / "solo")
        with pytest.raises(UnknownProjectError) as excinfo:
            resolve_project(root, "nope")
        assert str(excinfo.value) == (
            'Unknown project "nope". No other Lore project is in scope.'
        )


class TestResolveScope:
    def test_self_is_the_project_and_its_ancestors(self, tmp_path):
        # nested-projects-spec — D-3 / A-7: inheritance is unconditional
        from lore.projects import resolve_scope

        ancestor = _tree(tmp_path)
        refs = resolve_scope(ancestor / "lore", "self")
        assert [(ref.name, ref.relation) for ref in refs] == [
            ("lore", "self"),
            ("camelot", "ancestor"),
        ]

    def test_all_adds_every_descendant(self, tmp_path):
        # nested-projects-spec — D-4 / FR-12
        from lore.projects import resolve_scope

        ancestor = _tree(tmp_path)
        refs = resolve_scope(ancestor, "all")
        assert [ref.name for ref in refs] == ["camelot", "citadel", "lore", "realm"]

    def test_all_in_a_standalone_project_is_the_self_ref_alone(self, tmp_path):
        # nested-projects-spec — SC-6
        from lore.projects import resolve_scope

        root = _make_project(tmp_path / "solo")
        refs = resolve_scope(root, "all")
        assert [(ref.name, ref.relation) for ref in refs] == [("solo", "self")]

    def test_a_named_project_is_that_project_alone(self, tmp_path):
        # nested-projects-spec — D-4: an ancestor asking for `realm` wants
        # realm's material, not its own exports reflected back
        from lore.projects import resolve_scope

        ancestor = _tree(tmp_path)
        refs = resolve_scope(ancestor, "realm")
        assert [(ref.name, ref.relation) for ref in refs] == [("realm", "descendant")]

    def test_none_reads_the_configured_default(self, tmp_path):
        # nested-projects-spec — FR-2 / A-7: the downward axis is off unless
        # asked, and the config is one way of asking
        from lore.projects import resolve_scope

        ancestor = _make_project(
            tmp_path / "camelot", 'default-project-scope = "all"\n'
        )
        _make_project(ancestor / "lore")

        assert [ref.name for ref in resolve_scope(ancestor, None)] == [
            "camelot",
            "lore",
        ]

    def test_none_defaults_to_self_when_the_config_is_silent(self, tmp_path):
        # nested-projects-spec — FR-2 / N-3
        from lore.projects import resolve_scope

        ancestor = _tree(tmp_path)
        assert [ref.name for ref in resolve_scope(ancestor, None)] == ["camelot"]

    def test_an_unknown_name_raises(self, tmp_path):
        # nested-projects-spec — FR-18
        from lore.projects import UnknownProjectError, resolve_scope

        ancestor = _tree(tmp_path)
        with pytest.raises(UnknownProjectError):
            resolve_scope(ancestor, "nope")


# ---------------------------------------------------------------------------
# F10 — collect
# ---------------------------------------------------------------------------


class TestCollect:
    def test_a_standalone_project_gets_its_own_rows_tagged_self(self, tmp_path):
        # nested-projects-spec — FR-16: `origin` is on every row, always
        from lore.projects import collect

        root = _make_project(tmp_path / "solo")
        rows = collect(root, "self", read=lambda _root: [{"id": "a", "title": "A"}])
        assert rows == [{"id": "a", "title": "A", "origin": "self"}]

    def test_an_inherited_row_is_qualified_and_tagged(self, tmp_path):
        # nested-projects-spec — SC-3 / FR-15
        from lore.projects import collect

        ancestor = _make_project(
            tmp_path / "camelot", '[shared]\nexports = ["standards-*"]\n'
        )
        descendant = _make_project(ancestor / "lore")

        def read(root: Path) -> list[dict]:
            if root == descendant:
                return [{"id": "own-doc", "group": ""}]
            return [{"id": "standards-dry", "group": ""}]

        rows = collect(descendant, "self", read=read)
        assert rows == [
            {"id": "own-doc", "group": "", "origin": "self"},
            {"id": "camelot:standards-dry", "group": "", "origin": "camelot"},
        ]

    def test_an_ancestor_row_outside_the_export_set_is_dropped(self, tmp_path):
        # nested-projects-spec — FR-3: an export list is what an agent sees
        from lore.projects import collect

        ancestor = _make_project(
            tmp_path / "camelot", '[shared]\nexports = ["standards-*"]\n'
        )
        descendant = _make_project(ancestor / "lore")

        def read(root: Path) -> list[dict]:
            if root == descendant:
                return []
            return [
                {"id": "standards-dry", "group": ""},
                {"id": "tech-arch-db", "group": ""},
            ]

        rows = collect(descendant, "self", read=read)
        assert [row["id"] for row in rows] == ["camelot:standards-dry"]

    def test_a_descendant_ref_is_never_export_filtered(self, tmp_path):
        # nested-projects-spec — D-4 / design point 2: FR-10's exclusion
        # governs inheritance, never federation
        from lore.projects import collect

        ancestor = _make_project(tmp_path / "camelot")
        _make_project(ancestor / "lore")

        def read(root: Path) -> list[dict]:
            if root == ancestor:
                return []
            return [
                {"id": "anything", "group": ""},
                {"id": "seeded", "group": "default/x"},
            ]

        rows = collect(ancestor, "all", read=read)
        assert [row["id"] for row in rows] == ["lore:anything", "lore:seeded"]
        assert all(row["origin"] == "lore" for row in rows)

    def test_exportable_false_suppresses_the_export_filter(self, tmp_path):
        # nested-projects-spec — D-22: the glossary resolves its own export
        # set, whole-file, and has no per-item pattern to match
        from lore.projects import collect

        ancestor = _make_project(tmp_path / "camelot", "[shared]\nglossary = true\n")
        descendant = _make_project(ancestor / "lore")

        def read(root: Path) -> list[dict]:
            if root == descendant:
                return []
            return [{"id": "quest", "group": ""}]

        rows = collect(descendant, "self", read=read, exportable=False)
        assert [row["id"] for row in rows] == ["camelot:quest"]

    def test_the_id_key_is_the_key_that_is_qualified(self, tmp_path):
        # nested-projects-spec — `id_key` names the key holding the entity id
        from lore.projects import collect

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        def read(root: Path) -> list[dict]:
            if root == descendant:
                return []
            return [{"keyword": "quest", "definition": "a body of work"}]

        rows = collect(descendant, "self", read=read, id_key="keyword", group_key=None)
        assert rows == [
            {
                "keyword": "camelot:quest",
                "definition": "a body of work",
                "origin": "camelot",
            }
        ]

    def test_group_key_none_applies_no_seeded_default_filter(self, tmp_path):
        # nested-projects-spec — the codex caller passes `group_key=None`
        # because `list_codex` returns no group, and no codex document is a
        # seeded default
        from lore.projects import collect

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        def read(root: Path) -> list[dict]:
            if root == descendant:
                return []
            return [{"id": "default", "title": "t"}]

        rows = collect(descendant, "self", read=read, group_key=None)
        assert [row["id"] for row in rows] == ["camelot:default"]

    def test_a_group_key_applies_the_seeded_default_filter(self, tmp_path):
        # nested-projects-spec — FR-10
        from lore.projects import collect

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        def read(root: Path) -> list[dict]:
            if root == descendant:
                return []
            return [
                {"id": "seeded", "group": "default"},
                {"id": "authored", "group": "ours"},
            ]

        rows = collect(descendant, "self", read=read)
        assert [row["id"] for row in rows] == ["camelot:authored"]

    def test_a_missing_group_key_is_not_an_error(self, tmp_path):
        # nested-projects-spec — `collect` does not fabricate a group, does not
        # read the filesystem to derive one, and does not treat a missing key
        # as an error
        from lore.projects import collect

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        def read(root: Path) -> list[dict]:
            if root == descendant:
                return []
            return [{"id": "no-group-here"}]

        rows = collect(descendant, "self", read=read)
        assert [row["id"] for row in rows] == ["camelot:no-group-here"]

    def test_a_transient_ancestor_document_never_crosses(self, tmp_path):
        # nested-projects-spec — A-2, through `collect`'s own export filter
        from lore.paths import codex_dir
        from lore.projects import collect

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        def read(root: Path) -> list[dict]:
            if root == descendant:
                return []
            return [
                {"id": "spec", "path": codex_dir(ancestor) / "transient" / "spec.md"},
                {"id": "adr", "path": codex_dir(ancestor) / "decisions" / "adr.md"},
            ]

        rows = collect(descendant, "self", read=read, group_key=None)
        assert [row["id"] for row in rows] == ["camelot:adr"]

    def test_an_oserror_from_read_yields_no_rows_and_one_stderr_line(
        self, tmp_path, capsys
    ):
        # nested-projects-spec — N-7: no read command fails because a project
        # below has gone away
        from lore.projects import collect

        ancestor = _make_project(tmp_path / "camelot")
        descendant = _make_project(ancestor / "lore")

        def read(root: Path) -> list[dict]:
            if root == descendant:
                raise OSError("No such file or directory")
            return [{"id": "mine", "group": ""}]

        rows = collect(ancestor, "all", read=read)
        assert [row["id"] for row in rows] == ["mine"]
        assert capsys.readouterr().err == (
            'lore: project "lore" is unreadable: No such file or directory; skipped\n'
        )

    def test_an_oserror_from_read_does_not_raise(self, tmp_path, capsys):
        # nested-projects-spec — N-7 / N-9
        from lore.projects import collect

        root = _make_project(tmp_path / "solo")

        def read(_root: Path) -> list[dict]:
            raise PermissionError("denied")

        assert collect(root, "self", read=read) == []
        assert 'lore: project "solo" is unreadable: denied; skipped\n' == (
            capsys.readouterr().err
        )

    def test_it_preserves_the_readers_own_order(self, tmp_path):
        # nested-projects-spec — D-16: `collect` imposes no sort of its own;
        # each entity module keeps its existing sort key and applies it to the
        # returned (qualified) id
        from lore.projects import collect

        ancestor = _make_project(tmp_path / "camelot", '[shared]\nexports = ["*"]\n')
        descendant = _make_project(ancestor / "lore")

        def read(root: Path) -> list[dict]:
            if root == descendant:
                return [{"id": "zulu", "group": ""}, {"id": "alpha", "group": ""}]
            return [{"id": "yankee", "group": ""}, {"id": "bravo", "group": ""}]

        rows = collect(descendant, "self", read=read)
        assert [row["id"] for row in rows] == [
            "zulu",
            "alpha",
            "camelot:yankee",
            "camelot:bravo",
        ]

    def test_it_does_not_mutate_the_readers_records(self, tmp_path):
        # nested-projects-spec — the reader owns its records; `collect` returns
        # tagged copies
        from lore.projects import collect

        root = _make_project(tmp_path / "solo")
        record = {"id": "a", "group": ""}
        collect(root, "self", read=lambda _root: [record])
        assert record == {"id": "a", "group": ""}


# ---------------------------------------------------------------------------
# D-1 — the dependency arrow points inward
# ---------------------------------------------------------------------------


def test_projects_imports_no_entity_module():
    """nested-projects-spec — D-1 / standards-dependency-inversion.

    ``projects.py`` sits above ``paths``/``config``/``root``/``validators`` and
    below every entity module, so nothing imports it upward and it imports no
    entity module downward. The merge reaches entity data through a callback
    (D-2), which is what keeps the arrow pointing one way.
    """
    import ast

    source = Path(__file__).resolve().parents[2] / "src" / "lore" / "projects.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    lore_imports = {name for name in imported if name.split(".")[0] == "lore"}
    assert lore_imports <= {"lore.paths", "lore.config", "lore.root", "lore.validators"}
