"""Unit tests for lore.artifact.scan_artifacts with filter_groups parameter.

Spec: filter-list-subcommands-us-3 (lore codex show filter-list-subcommands-us-3)
Workflow: conceptual-workflows-filter-list
"""

from lore.artifact import scan_artifacts


# ---------------------------------------------------------------------------
# Fixtures — artifact file content
# ---------------------------------------------------------------------------

ROOT_ARTIFACT_MD = """\
---
id: root-artifact
title: Root Artifact
summary: A root-level artifact.
---

Root body.
"""

DEFAULT_ARTIFACT_MD = """\
---
id: some-artifact
title: Some Artifact
summary: An artifact in the default group.
---

Default body.
"""

CODEX_ARTIFACT_MD = """\
---
id: fi-user-story
title: FI User Story
summary: A user story artifact in the default/codex namespace.
---

Codex body.
"""

TRANSIENT_ARTIFACT_MD = """\
---
id: scratch
title: Scratch
summary: A transient artifact.
---

Transient body.
"""

INVALID_FRONTMATTER_MD = """\
---
title: Missing ID
summary: This file has no id field.
---

Invalid body.
"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _setup_artifacts(artifacts_dir):
    """Populate artifacts_dir with test fixtures covering root, default, default-codex, default-transient."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "root-artifact.md").write_text(ROOT_ARTIFACT_MD)
    (artifacts_dir / "default").mkdir()
    (artifacts_dir / "default" / "some-artifact.md").write_text(DEFAULT_ARTIFACT_MD)
    codex_dir = artifacts_dir / "default" / "codex"
    codex_dir.mkdir()
    (codex_dir / "fi-user-story.md").write_text(CODEX_ARTIFACT_MD)
    transient_dir = artifacts_dir / "default" / "transient"
    transient_dir.mkdir()
    (transient_dir / "scratch.md").write_text(TRANSIENT_ARTIFACT_MD)


# ---------------------------------------------------------------------------
# Unit — scan_artifacts filter_groups=["default-codex"] returns default-codex + root only
# Exercises: conceptual-workflows-filter-list step 3 (_apply_filter on artifact records)
# ---------------------------------------------------------------------------


def test_scan_artifacts_filter_returns_matched_group_and_root(tmp_path):
    """scan_artifacts with filter_groups=["default-codex"] returns default-codex and root-level artifacts only."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    _setup_artifacts(artifacts_dir)

    results = scan_artifacts(artifacts_dir, filter_groups=["default-codex"])

    ids = [r["id"] for r in results]
    assert "root-artifact" in ids
    assert "fi-user-story" in ids
    assert "some-artifact" not in ids
    assert "scratch" not in ids


# ---------------------------------------------------------------------------
# Unit — scan_artifacts filter — valid count reflects filtered set only (FR-12)
# Exercises: conceptual-workflows-filter-list step 4 (valid/invalid counts on filtered output)
# ---------------------------------------------------------------------------


def test_scan_artifacts_filter_valid_count_reflects_filtered_set(tmp_path):
    """scan_artifacts with filter returns fewer records than without filter."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    _setup_artifacts(artifacts_dir)

    all_results = scan_artifacts(artifacts_dir)
    filtered_results = scan_artifacts(artifacts_dir, filter_groups=["default-codex"])

    assert len(filtered_results) < len(all_results)
    assert len(filtered_results) == 2  # root-artifact + fi-user-story


# ---------------------------------------------------------------------------
# Unit — scan_artifacts filter — strict-skip of invalid frontmatter unaffected
# Exercises: conceptual-workflows-filter-list step 1 (discovery unchanged) + artifact-list step 3
# ---------------------------------------------------------------------------


def test_scan_artifacts_filter_invalid_frontmatter_skip_unaffected(tmp_path):
    """Invalid frontmatter files in other groups are still skipped when filter is applied."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    _setup_artifacts(artifacts_dir)
    # Add an invalid file in the "default" group — it should be skipped regardless of filter
    (artifacts_dir / "default" / "invalid-no-id.md").write_text(INVALID_FRONTMATTER_MD)

    results = scan_artifacts(artifacts_dir, filter_groups=["default-codex"])

    ids = [r["id"] for r in results]
    # Invalid file should not appear (skipped due to missing id)
    assert "invalid-no-id" not in ids
    # The filter still returns root + codex files
    assert "root-artifact" in ids
    assert "fi-user-story" in ids


# ---------------------------------------------------------------------------
# US-4: scan_artifacts filter_groups=None — backward compatibility (no regression)
# Spec: filter-list-subcommands-us-4 (lore codex show filter-list-subcommands-us-4)
# Exercises: conceptual-workflows-filter-list step 3 (filter_groups=None → return all)
# ---------------------------------------------------------------------------


# Unit — scan_artifacts filter_groups=None returns all artifacts (no regression)
# Exercises: conceptual-workflows-filter-list step 3 (filter_groups=None → return all)
def test_scan_artifacts_filter_none_no_regression(tmp_path):
    """scan_artifacts with filter_groups=None returns all artifacts across all groups — pre-filter behavior."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    _setup_artifacts(artifacts_dir)

    results = scan_artifacts(artifacts_dir, filter_groups=None)

    ids = [r["id"] for r in results]
    assert "root-artifact" in ids
    assert "some-artifact" in ids
    assert "fi-user-story" in ids
    assert "scratch" in ids


# Unit — scan_artifacts called without filter_groups returns all artifacts (backward compat)
# Exercises: backward compat — old callers that never passed filter_groups still work
def test_scan_artifacts_no_filter_argument_returns_all(tmp_path):
    """scan_artifacts called without filter_groups (default) returns all artifacts — backward compatible."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    _setup_artifacts(artifacts_dir)

    results = scan_artifacts(artifacts_dir)

    ids = [r["id"] for r in results]
    assert "root-artifact" in ids
    assert "some-artifact" in ids
    assert "fi-user-story" in ids
    assert "scratch" in ids
