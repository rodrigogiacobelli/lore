"""Tests for lore.paths.entity_location (G15 — amendment Section C1).

Spec docs:
  lore codex show transient-public-api-facade-plan       (### G15)
  lore codex show transient-public-api-facade-create-stdz (Sections A3 + C1)

Signature under test:
    entity_location(
        project_root: Path,
        kind: str,
        name: str | None = None,
        *,
        group: str | None = None,
        suffix: str | None = None,
    ) -> Path

Supported kinds: "knight" | "doctrine" | "artifact" | "watcher" | "codex".
Behaviour:
  - name=None + suffix=None  -> the (group-scoped) directory only
  - name + suffix            -> base_dir / [group/] / f"{name}{suffix}"
  - unknown kind             -> raises ValueError
  - Does NOT mkdir anything
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Per-kind base subdirectory under .lore/
# ---------------------------------------------------------------------------

_BASE_FOR_KIND: dict[str, tuple[str, ...]] = {
    "knight": (".lore", "knights"),
    "doctrine": (".lore", "doctrines"),
    "artifact": (".lore", "artifacts"),
    "watcher": (".lore", "watchers"),
    "codex": (".lore", "codex"),
}


def _base_dir(root: Path, kind: str) -> Path:
    return root.joinpath(*_BASE_FOR_KIND[kind])


# ---------------------------------------------------------------------------
# Importability — fail fast if the helper does not exist yet.
# ---------------------------------------------------------------------------


class TestEntityLocationImportable:
    def test_entity_location_is_importable_from_lore_paths(self):
        from lore.paths import entity_location  # noqa: F401

    def test_entity_location_is_callable(self):
        from lore.paths import entity_location

        assert callable(entity_location)


# ---------------------------------------------------------------------------
# Group-scoped directory only (name=None, suffix=None)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(_BASE_FOR_KIND))
def test_entity_location_returns_base_dir_when_no_name_no_group_no_suffix(
    tmp_path: Path, kind: str
):
    """name=None, group=None, suffix=None -> base kind dir."""
    from lore.paths import entity_location

    result = entity_location(tmp_path, kind)
    assert result == _base_dir(tmp_path, kind)


@pytest.mark.parametrize("kind", sorted(_BASE_FOR_KIND))
def test_entity_location_returns_group_subdir_when_group_set_and_name_none(
    tmp_path: Path, kind: str
):
    """name=None + suffix=None + group='alpha' -> base / 'alpha'."""
    from lore.paths import entity_location

    result = entity_location(tmp_path, kind, group="alpha")
    assert result == _base_dir(tmp_path, kind) / "alpha"


@pytest.mark.parametrize("kind", sorted(_BASE_FOR_KIND))
def test_entity_location_returns_nested_group_subdir(tmp_path: Path, kind: str):
    """Multi-segment group preserved as nested path under base."""
    from lore.paths import entity_location

    result = entity_location(tmp_path, kind, group="alpha/beta")
    assert result == _base_dir(tmp_path, kind) / "alpha" / "beta"


# ---------------------------------------------------------------------------
# Full file path (name + suffix combinations)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,suffix",
    [
        ("knight", ".md"),
        ("doctrine", ".yaml"),
        ("doctrine", ".design.md"),
        ("artifact", ".md"),
        ("watcher", ".yaml"),
        ("codex", ".md"),
    ],
)
def test_entity_location_returns_file_path_when_name_and_suffix_given(
    tmp_path: Path, kind: str, suffix: str
):
    """name + suffix -> base / f'{name}{suffix}' (no group)."""
    from lore.paths import entity_location

    result = entity_location(tmp_path, kind, "my-thing", suffix=suffix)
    assert result == _base_dir(tmp_path, kind) / f"my-thing{suffix}"


@pytest.mark.parametrize(
    "kind,suffix",
    [
        ("knight", ".md"),
        ("doctrine", ".yaml"),
        ("artifact", ".md"),
        ("watcher", ".yaml"),
        ("codex", ".md"),
    ],
)
def test_entity_location_returns_grouped_file_path(
    tmp_path: Path, kind: str, suffix: str
):
    """name + suffix + group -> base / group / f'{name}{suffix}'."""
    from lore.paths import entity_location

    result = entity_location(
        tmp_path, kind, "my-thing", group="grp/sub", suffix=suffix
    )
    assert (
        result
        == _base_dir(tmp_path, kind) / "grp" / "sub" / f"my-thing{suffix}"
    )


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(_BASE_FOR_KIND))
def test_entity_location_returns_pathlib_path(tmp_path: Path, kind: str):
    from lore.paths import entity_location

    assert isinstance(entity_location(tmp_path, kind), Path)
    assert isinstance(
        entity_location(tmp_path, kind, "x", group="g", suffix=".md"), Path
    )


# ---------------------------------------------------------------------------
# Unknown kind -> ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_kind",
    [
        "quest",
        "mission",
        "knights",        # plural — not the supported singular
        "doctrines",
        "Knight",         # case-sensitive
        "",
        "unknown",
        "board",
    ],
)
def test_entity_location_raises_value_error_for_unknown_kind(
    tmp_path: Path, bad_kind: str
):
    from lore.paths import entity_location

    with pytest.raises(ValueError):
        entity_location(tmp_path, bad_kind)


def test_entity_location_value_error_mentions_kind(tmp_path: Path):
    """Error message should reference the offending kind for debuggability."""
    from lore.paths import entity_location

    with pytest.raises(ValueError) as excinfo:
        entity_location(tmp_path, "not-a-kind")
    assert "not-a-kind" in str(excinfo.value)


# ---------------------------------------------------------------------------
# No side effects — never mkdir
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(_BASE_FOR_KIND))
def test_entity_location_does_not_create_base_dir(tmp_path: Path, kind: str):
    from lore.paths import entity_location

    result = entity_location(tmp_path, kind)
    assert not result.exists(), (
        f"entity_location must not mkdir; {result} should not exist"
    )


@pytest.mark.parametrize("kind", sorted(_BASE_FOR_KIND))
def test_entity_location_does_not_create_group_dir(tmp_path: Path, kind: str):
    from lore.paths import entity_location

    result = entity_location(tmp_path, kind, group="a/b/c")
    assert not result.exists()
    # also assert parents not created
    assert not _base_dir(tmp_path, kind).exists()


@pytest.mark.parametrize("kind", sorted(_BASE_FOR_KIND))
def test_entity_location_does_not_create_file_or_parents(
    tmp_path: Path, kind: str
):
    from lore.paths import entity_location

    result = entity_location(tmp_path, kind, "thing", group="g", suffix=".md")
    assert not result.exists()
    assert not result.parent.exists()
    assert not _base_dir(tmp_path, kind).exists()


# ---------------------------------------------------------------------------
# Keyword-only arguments — `group` and `suffix` are kw-only per signature.
# ---------------------------------------------------------------------------


def test_entity_location_group_is_keyword_only(tmp_path: Path):
    from lore.paths import entity_location

    with pytest.raises(TypeError):
        # group passed positionally must fail (kw-only).
        entity_location(tmp_path, "knight", "name", "group-positional")  # type: ignore[misc]


def test_entity_location_suffix_is_keyword_only(tmp_path: Path):
    from lore.paths import entity_location

    with pytest.raises(TypeError):
        entity_location(tmp_path, "knight", "name", None, ".md")  # type: ignore[misc]
