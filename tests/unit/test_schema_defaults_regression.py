"""US-011 regression guards — default seed frontmatter invariants.

These tests pin the invariant that packaged default seed files under
``src/lore/defaults/`` MUST NOT carry forbidden frontmatter keys (stability,
group, status, type, persona, entities_involved, lens) and MUST validate
cleanly against the packaged JSON-schemas.

US-011 originally tracked a one-shot cleanup; the cleanup was absorbed into
US-004. These tests exist solely as regression guards so that a later
contributor cannot silently re-introduce forbidden keys into the defaults.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lore.schemas import validate_entity


FORBIDDEN_KEYS = {
    "stability",
    "group",
    "status",
    "type",
    "persona",
    "entities_involved",
    "lens",
}

ALLOWED_SIMPLE_KEYS = {"id", "title", "summary"}

DEFAULTS_ROOT = Path(__file__).resolve().parents[2] / "src" / "lore" / "defaults"


def _load_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{path} has no frontmatter block"
    parts = text.split("---", 2)
    assert len(parts) >= 3, f"{path} has malformed frontmatter block"
    data = yaml.safe_load(parts[1])
    assert isinstance(data, dict), f"{path} frontmatter is not a mapping"
    return data


def _default_artifact_files() -> list[Path]:
    return sorted((DEFAULTS_ROOT / "artifacts").rglob("*.md"))


def _default_knight_files() -> list[Path]:
    return sorted((DEFAULTS_ROOT / "knights").rglob("*.md"))


def _default_doctrine_design_files() -> list[Path]:
    return sorted((DEFAULTS_ROOT / "doctrines").rglob("*.design.md"))


# ---------------------------------------------------------------------------
# Forbidden-key guards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _default_artifact_files(), ids=lambda p: p.name)
def test_default_artifact_has_no_forbidden_keys(path: Path) -> None:
    # US-011 regression guard — default artifact seeds must not carry
    # stability/group/status/type/persona/entities_involved/lens keys.
    fm = _load_frontmatter(path)
    leaked = FORBIDDEN_KEYS & set(fm)
    assert not leaked, f"{path} leaks forbidden keys: {sorted(leaked)}"


@pytest.mark.parametrize("path", _default_knight_files(), ids=lambda p: p.name)
def test_default_knight_only_has_allowed_keys(path: Path) -> None:
    # US-011 regression guard — default knight seeds must only carry
    # id/title/summary frontmatter keys.
    fm = _load_frontmatter(path)
    extra = set(fm) - ALLOWED_SIMPLE_KEYS
    assert not extra, f"{path} has extra keys beyond id/title/summary: {sorted(extra)}"


@pytest.mark.parametrize(
    "path", _default_doctrine_design_files(), ids=lambda p: p.name
)
def test_default_doctrine_design_only_has_allowed_keys(path: Path) -> None:
    # US-011 regression guard — default doctrine design seeds must only
    # carry id/title/summary frontmatter keys.
    fm = _load_frontmatter(path)
    extra = set(fm) - ALLOWED_SIMPLE_KEYS
    assert not extra, f"{path} has extra keys beyond id/title/summary: {sorted(extra)}"


# ---------------------------------------------------------------------------
# Schema validation guards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _default_artifact_files(), ids=lambda p: p.name)
def test_default_artifact_validates_clean(path: Path) -> None:
    # US-011 regression guard — every default artifact frontmatter must
    # validate clean against the artifact-frontmatter schema.
    fm = _load_frontmatter(path)
    issues = validate_entity("artifact-frontmatter", fm)
    assert issues == [], f"{path} schema issues: {issues}"


@pytest.mark.parametrize("path", _default_knight_files(), ids=lambda p: p.name)
def test_default_knight_validates_clean(path: Path) -> None:
    # US-011 regression guard — every default knight frontmatter must
    # validate clean against the knight-frontmatter schema.
    fm = _load_frontmatter(path)
    issues = validate_entity("knight-frontmatter", fm)
    assert issues == [], f"{path} schema issues: {issues}"


@pytest.mark.parametrize(
    "path", _default_doctrine_design_files(), ids=lambda p: p.name
)
def test_default_doctrine_design_validates_clean(path: Path) -> None:
    # US-011 regression guard — every default doctrine design frontmatter
    # must validate clean against the doctrine-design-frontmatter schema.
    fm = _load_frontmatter(path)
    issues = validate_entity("doctrine-design-frontmatter", fm)
    assert issues == [], f"{path} schema issues: {issues}"


# ---------------------------------------------------------------------------
# Sanity: the scans actually discover files
# ---------------------------------------------------------------------------


def test_default_scans_discover_files() -> None:
    # US-011 regression guard — fail loud if the defaults tree layout
    # changes and the parametrised scans silently collect zero files.
    assert _default_artifact_files(), "no default artifacts discovered"
    assert _default_knight_files(), "no default knights discovered"
    assert _default_doctrine_design_files(), "no default doctrine designs discovered"
