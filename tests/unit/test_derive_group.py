"""Tests for lore.paths.derive_group — GROUP is derived consistently across
all entity types.

Acceptance criteria:
- The GROUP value for any entity is derived from its folder path relative
  to its base directory, using dashes as separators, excluding the filename
- Given files at identical relative paths under the artifacts, knights,
  and doctrines directories, the GROUP values produced are identical
- Entities stored directly in their base directory (no subfolder) show
  an empty group
"""

from pathlib import Path

import pytest

from lore.paths import derive_group


class TestDeriveGroupGroupFromFolderPathWithDashSeparators:
    """GROUP is derived from folder path relative to base dir, dashes as separators."""

    def test_single_subdirectory_produces_subdirectory_name_as_group(self):
        """A file one level deep returns its parent directory name."""
        filepath = Path("/base/sub1/file.md")
        base_dir = Path("/base")
        assert derive_group(filepath, base_dir) == "sub1"

    def test_two_subdirectory_levels_joined_with_dash(self):
        """A file two levels deep returns both directory names joined with a dash."""
        filepath = Path("/base/sub1/sub2/file.md")
        base_dir = Path("/base")
        assert derive_group(filepath, base_dir) == "sub1-sub2"

    def test_three_subdirectory_levels_joined_with_dashes(self):
        """A file three levels deep returns all three directory names joined with dashes."""
        filepath = Path("/base/a/b/c/file.md")
        base_dir = Path("/base")
        assert derive_group(filepath, base_dir) == "a-b-c"

    def test_deeply_nested_artifact_group_format(self, tmp_path):
        """Deep nesting produces group like 'codex-conceptual-entities'."""
        artifacts_dir = tmp_path / ".lore" / "artifacts"
        filepath = artifacts_dir / "codex" / "conceptual" / "entities" / "task.md"
        assert derive_group(filepath, artifacts_dir) == "codex-conceptual-entities"

    def test_filename_is_excluded_from_group(self):
        """The filename component must not appear in the group value."""
        filepath = Path("/base/sub1/my-entity.md")
        base_dir = Path("/base")
        result = derive_group(filepath, base_dir)
        assert "my-entity" not in result
        assert result == "sub1"

    def test_separator_is_dash_not_slash_or_underscore(self):
        """Directory components must be joined with dashes, not slashes or underscores."""
        filepath = Path("/base/alpha/beta/file.md")
        base_dir = Path("/base")
        result = derive_group(filepath, base_dir)
        assert "/" not in result
        assert "\\" not in result
        assert "_" not in result
        assert result == "alpha-beta"


class TestDeriveGroupIdenticalGroupsAcrossEntityTypes:
    """Identical relative paths under different base dirs produce identical GROUP values."""

    def test_knight_and_artifact_with_same_relative_path_produce_same_group(
        self, tmp_path
    ):
        """derive_group is base-dir-agnostic: same relative path always yields same group."""
        knights_dir = tmp_path / ".lore" / "knights"
        artifacts_dir = tmp_path / ".lore" / "artifacts"

        knight_file = knights_dir / "default" / "pm.md"
        artifact_file = artifacts_dir / "default" / "some-artifact.md"

        knight_group = derive_group(knight_file, knights_dir)
        artifact_group = derive_group(artifact_file, artifacts_dir)

        assert knight_group == artifact_group

    def test_knight_and_doctrine_with_same_relative_path_produce_same_group(
        self, tmp_path
    ):
        """Knights and doctrines at the same relative path share the same group."""
        knights_dir = tmp_path / ".lore" / "knights"
        doctrines_dir = tmp_path / ".lore" / "doctrines"

        knight_file = knights_dir / "workflow" / "feature" / "knight.md"
        doctrine_file = doctrines_dir / "workflow" / "feature" / "doctrine.yaml"

        knight_group = derive_group(knight_file, knights_dir)
        doctrine_group = derive_group(doctrine_file, doctrines_dir)

        assert knight_group == doctrine_group

    def test_artifact_and_doctrine_with_same_relative_path_produce_same_group(
        self, tmp_path
    ):
        """Artifacts and doctrines at the same relative path share the same group."""
        artifacts_dir = tmp_path / ".lore" / "artifacts"
        doctrines_dir = tmp_path / ".lore" / "doctrines"

        artifact_file = artifacts_dir / "codex" / "spec.md"
        doctrine_file = doctrines_dir / "codex" / "doctrine.yaml"

        artifact_group = derive_group(artifact_file, artifacts_dir)
        doctrine_group = derive_group(doctrine_file, doctrines_dir)

        assert artifact_group == doctrine_group

    def test_group_value_does_not_include_base_dir_name(self, tmp_path):
        """The base directory name itself must not appear in the returned group."""
        knights_dir = tmp_path / ".lore" / "knights"
        filepath = knights_dir / "sub" / "file.md"
        result = derive_group(filepath, knights_dir)
        # "knights" should not appear in result — only relative path components do
        assert "knights" not in result
        assert result == "sub"

    def test_all_three_entity_types_with_single_sub_dir_produce_identical_group(
        self, tmp_path
    ):
        """All three entity dirs produce the same group for files one level deep."""
        knights_dir = tmp_path / "knights"
        artifacts_dir = tmp_path / "artifacts"
        doctrines_dir = tmp_path / "doctrines"

        k_group = derive_group(knights_dir / "ops" / "sre.md", knights_dir)
        a_group = derive_group(artifacts_dir / "ops" / "template.md", artifacts_dir)
        d_group = derive_group(doctrines_dir / "ops" / "bugfix.yaml", doctrines_dir)

        assert k_group == a_group == d_group == "ops"


class TestDeriveGroupRootLevelEntityShowsEmptyGroup:
    """Entities stored directly in their base directory show an empty group."""

    def test_file_in_root_of_knights_dir_returns_empty_string(self, tmp_path):
        """A knight file directly in .lore/knights/ has group ''."""
        knights_dir = tmp_path / ".lore" / "knights"
        filepath = knights_dir / "developer.md"
        assert derive_group(filepath, knights_dir) == ""

    def test_file_in_root_of_artifacts_dir_returns_empty_string(self, tmp_path):
        """An artifact file directly in .lore/artifacts/ has group ''."""
        artifacts_dir = tmp_path / ".lore" / "artifacts"
        filepath = artifacts_dir / "my-template.md"
        assert derive_group(filepath, artifacts_dir) == ""

    def test_file_in_root_of_doctrines_dir_returns_empty_string(self, tmp_path):
        """A doctrine file directly in .lore/doctrines/ has group ''."""
        doctrines_dir = tmp_path / ".lore" / "doctrines"
        filepath = doctrines_dir / "feature-workflow.yaml"
        assert derive_group(filepath, doctrines_dir) == ""

    def test_root_level_group_is_empty_string_not_none_or_dot(self):
        """Empty group must be exactly '' — not None, '.', or any other sentinel."""
        filepath = Path("/base/file.md")
        base_dir = Path("/base")
        result = derive_group(filepath, base_dir)
        assert result == ""
        assert result is not None
        assert isinstance(result, str)

    def test_root_level_group_is_empty_string_regardless_of_absolute_path_depth(
        self,
    ):
        """Deeply nested absolute base dir doesn't affect root-level group derivation."""
        base_dir = Path("/very/deep/nested/path/.lore/knights")
        filepath = base_dir / "qa.md"
        assert derive_group(filepath, base_dir) == ""


class TestDeriveGroupEdgeCasesAndErrorHandling:
    """Edge cases documented in tech notes and spec."""

    def test_filepath_not_under_base_dir_raises_value_error(self):
        """ValueError propagates when filepath is not under base_dir (programming error)."""
        filepath = Path("/completely/different/path/file.md")
        base_dir = Path("/base/dir")
        with pytest.raises(ValueError):
            derive_group(filepath, base_dir)

    def test_non_md_file_extension_works_correctly(self, tmp_path):
        """File extension does not affect group derivation (yaml doctrines also work)."""
        doctrines_dir = tmp_path / "doctrines"
        filepath = doctrines_dir / "workflow" / "my-doctrine.yaml"
        assert derive_group(filepath, doctrines_dir) == "workflow"

    def test_group_result_is_stable_for_same_inputs(self):
        """Calling derive_group twice with the same args returns the same value (stable)."""
        filepath = Path("/base/sub1/sub2/file.md")
        base_dir = Path("/base")
        first = derive_group(filepath, base_dir)
        second = derive_group(filepath, base_dir)
        assert first == second

    def test_group_only_contains_directory_name_components_not_stem(self):
        """Group contains only directory names — never the file stem."""
        filepath = Path("/base/my-group/my-file.md")
        base_dir = Path("/base")
        result = derive_group(filepath, base_dir)
        assert result == "my-group"
        assert "my-file" not in result

    def test_exact_spec_example_knights_default_pm(self, tmp_path):
        """Spec example: derive_group(.lore/knights/default/pm.md, .lore/knights/) => 'default'."""
        lore_dir = tmp_path / ".lore"
        knights_dir = lore_dir / "knights"
        filepath = knights_dir / "default" / "pm.md"
        assert derive_group(filepath, knights_dir) == "default"

    def test_exact_spec_example_artifacts_deep_nesting(self, tmp_path):
        """Spec example: codex/conceptual/entities/task.md => 'codex-conceptual-entities'."""
        lore_dir = tmp_path / ".lore"
        artifacts_dir = lore_dir / "artifacts"
        filepath = artifacts_dir / "codex" / "conceptual" / "entities" / "task.md"
        assert derive_group(filepath, artifacts_dir) == "codex-conceptual-entities"

    def test_exact_spec_example_root_level_knight(self, tmp_path):
        """Spec example: .lore/knights/pm.md relative to .lore/knights/ => ''."""
        lore_dir = tmp_path / ".lore"
        knights_dir = lore_dir / "knights"
        filepath = knights_dir / "pm.md"
        assert derive_group(filepath, knights_dir) == ""
