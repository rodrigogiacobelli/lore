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

import re
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


# ---------------------------------------------------------------------------
# US-004 (codex-sources-us-004) — Default CODEX.md documents three content
# classes (Stable, In-Flight, Sources) and the sources-specific rules.
# Anchors:
#   conceptual-workflows-lore-init §Seed artifacts step — the shipped
#   CODEX.md is seeded verbatim and must validate against codex-frontmatter.
#   decisions-006-no-seed-content-tests — tests MUST assert structure only
#   (frontmatter validity, heading/table-row presence), never prose content.
# Red state (from mission brief): assertions are tight enough that the OLD
# pre-feature CODEX.md (single "## Stable vs In-Flight" heading, two-class
# table) would FAIL every US-004 test. A re-appearance of that retired
# heading MUST also fail the suite.
# ---------------------------------------------------------------------------


CODEX_MD_PATH = (
    DEFAULTS_ROOT / "artifacts" / "codex" / "CODEX.md"
)


def _extract_headings(body: str) -> list[str]:
    """Return the text of every '#', '##', '###', ... heading in the body."""
    return [
        line.lstrip("#").strip()
        for line in body.splitlines()
        if re.match(r"^#{1,6}\s+\S", line)
    ]


def _extract_tables(body: str) -> list[list[list[str]]]:
    """Return every markdown table as a list of row-cell lists.

    Each table is a list of rows; each row is a list of cell strings (stripped).
    The separator row (``|---|---|``) is dropped. Only pipe-style tables with
    a leading and trailing ``|`` are recognised — matches the CODEX.md style.
    """
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    sep = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and not sep.match(
            stripped
        ):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            current.append(cells)
        elif sep.match(stripped):
            # separator — skip, keep collecting rows
            continue
        else:
            if current:
                tables.append(current)
                current = []
    if current:
        tables.append(current)
    return tables


def _cells(table: list[list[str]]) -> set[str]:
    """Flatten every cell of every row into a single set of strings."""
    return {cell for row in table for cell in row}


def _extract_three_class_table(body: str) -> dict:
    """Locate the table containing Stable/In-Flight/Sources rows and return
    a dict with a ``rows`` list; each row is a dict with a ``deletion_test``
    key (the last cell of the data row)."""
    for table in _extract_tables(body):
        flat = _cells(table)
        if {"Stable", "In-Flight", "Sources"}.issubset(flat):
            # header row is row 0; data rows follow
            data_rows = []
            for row in table[1:]:
                if not row or not any(cell for cell in row):
                    continue
                label = row[0].strip()
                if label in {"Stable", "In-Flight", "Sources"}:
                    data_rows.append(
                        {"label": label, "deletion_test": row[-1].strip()}
                    )
            return {"rows": data_rows}
    return {"rows": []}


def test_updated_codex_md_passes_codex_frontmatter() -> None:
    # conceptual-workflows-lore-init — seeded CODEX.md must validate against
    # codex-frontmatter (AC Scenario 2). Pre-feature file already carried a
    # valid frontmatter block, so this assertion stays true across the edit —
    # but it pins the invariant against future schema-violating edits.
    fm = _load_frontmatter(CODEX_MD_PATH)
    issues = validate_entity("codex-frontmatter", fm)
    assert issues == [], f"CODEX.md frontmatter schema issues: {issues}"


def test_codex_md_declares_three_content_classes() -> None:
    # conceptual-workflows-lore-init + decisions-006-no-seed-content-tests —
    # AC Scenario 3: the three structural tokens Stable / In-Flight / Sources
    # must coexist inside a single markdown table. The OLD pre-feature file
    # had no 'Sources' row and therefore would fail this assertion.
    body = CODEX_MD_PATH.read_text(encoding="utf-8")
    for token in ("Stable", "In-Flight", "Sources"):
        assert token in body, f"missing structural token: {token}"
    tables = _extract_tables(body)
    assert any(
        {"Stable", "In-Flight", "Sources"}.issubset(_cells(table))
        for table in tables
    ), "no single table lists Stable, In-Flight, and Sources together"


def test_codex_md_names_required_source_rule_headings() -> None:
    # conceptual-workflows-lore-init + decisions-006-no-seed-content-tests —
    # AC Scenario 4: every required source-rule section must exist as a
    # markdown heading at any level. Heading-token presence only; no prose
    # assertion. The OLD pre-feature file had none of these and would fail.
    body = CODEX_MD_PATH.read_text(encoding="utf-8")
    headings = _extract_headings(body)
    required = {
        "Sources layout",
        "Sources frontmatter rule",
        "Verbatim rule",
        "One-way linking",
        "Refresh rule",
    }
    for token in required:
        assert any(token.lower() in h.lower() for h in headings), (
            f"Missing required source-rule heading: {token!r}"
        )


def test_codex_md_introduces_three_content_classes_section() -> None:
    # conceptual-workflows-lore-init + decisions-006-no-seed-content-tests —
    # AC Scenario 3 (section-level): the file must carry a heading that
    # introduces the three content classes (e.g. '## The Three Content
    # Classes'). The OLD pre-feature file used '## Stable vs In-Flight'
    # instead and would fail this assertion.
    body = CODEX_MD_PATH.read_text(encoding="utf-8")
    headings = _extract_headings(body)
    assert any(
        "three" in h.lower() and "content classes" in h.lower()
        for h in headings
    ), (
        "No heading introducing the three content classes — expected a "
        "heading like '## The Three Content Classes'."
    )


def test_codex_md_has_no_legacy_stable_vs_in_flight_heading() -> None:
    # decisions-006-no-seed-content-tests — structural regression guard:
    # the retired two-class heading 'Stable vs In-Flight' must never return.
    # Mission brief: "Tests must fail if that section ever returns."
    body = CODEX_MD_PATH.read_text(encoding="utf-8")
    headings = _extract_headings(body)
    for h in headings:
        assert "stable vs in-flight" not in h.lower(), (
            f"Legacy two-class heading resurfaced: {h!r}"
        )


def test_codex_md_has_non_empty_deletion_test_row_per_class() -> None:
    # conceptual-workflows-lore-init + decisions-006-no-seed-content-tests —
    # AC Scenario 3 (table-level): the three-content-classes table must hold
    # exactly three data rows (Stable, In-Flight, Sources) and each row's
    # deletion-test cell must be non-empty. Structural only — no prose
    # assertion. The OLD file had only two rows and would fail.
    body = CODEX_MD_PATH.read_text(encoding="utf-8")
    table = _extract_three_class_table(body)
    rows = [row for row in table["rows"] if row]
    assert len(rows) == 3, (
        f"three-class table must hold exactly 3 data rows, found {len(rows)}"
    )
    labels = sorted(row["label"] for row in rows)
    assert labels == sorted(["Stable", "In-Flight", "Sources"]), (
        f"row labels do not match expected three classes: {labels}"
    )
    for row in rows:
        assert row["deletion_test"] != "", (
            f"row for class {row['label']!r} has empty deletion-test cell"
        )


# ---------------------------------------------------------------------------
# US-005 / US-006 (codex-sources) — default ingest-source / refresh-source
# skill file structural regression guards.
# Anchors:
#   conceptual-workflows-lore-init §Step "seed skills" — skill files are
#   shipped under src/lore/defaults/skills/<name>/SKILL.md and copied verbatim
#   into .lore/skills/<name>/SKILL.md by lore init.
#   decisions-006-no-seed-content-tests — tests MUST assert structure only
#   (existence, frontmatter shape, bounded length, heading-token presence),
#   never prose content.
# Red state: the target skill files do not yet exist; every assertion below
# fails at the file-existence check. Green-cycle authoring of the SKILL.md
# bodies turns each assertion green without any production-code change.
# ---------------------------------------------------------------------------


INGEST_SOURCE_SKILL_PATH = (
    DEFAULTS_ROOT / "skills" / "ingest-source" / "SKILL.md"
)
REFRESH_SOURCE_SKILL_PATH = (
    DEFAULTS_ROOT / "skills" / "refresh-source" / "SKILL.md"
)

# US-005 Scenario 6 — heading token groups (case-insensitive substring).
INGEST_SOURCE_HEADING_TOKENS: list[tuple[str, ...]] = [
    ("question", "ask"),          # three-questions step
    ("target", "path"),           # resolve target path
    ("exist", "refuse"),          # refuse-if-exists
    ("canonical", "propose"),     # propose canonical updates
    ("related", "snapshot"),      # write snapshot with non-empty related
    ("verify", "health"),         # verify via lore health
]

# US-006 Scenario 5 — heading token groups (case-insensitive substring).
REFRESH_SOURCE_HEADING_TOKENS: list[tuple[str, ...]] = [
    ("question", "ask"),          # two-questions step
    ("target", "path"),           # resolve target path
    ("exist", "refuse"),          # refuse-if-absent
    ("diff",),                    # compute + present diff
    ("codex-worthy", "worthy"),   # ask what is codex-worthy
    ("related", "overwrite"),     # overwrite + rewrite related
    ("verify", "health"),         # verify via lore health
]


# ---- US-005 ---------------------------------------------------------------


def test_ingest_source_skill_file_exists() -> None:
    # codex-sources-us-005 Scenario 3 — shipped package default file must exist
    # and be non-empty at src/lore/defaults/skills/ingest-source/SKILL.md.
    assert INGEST_SOURCE_SKILL_PATH.is_file(), (
        f"missing skill file: {INGEST_SOURCE_SKILL_PATH}"
    )
    assert INGEST_SOURCE_SKILL_PATH.stat().st_size > 0, (
        f"skill file is empty: {INGEST_SOURCE_SKILL_PATH}"
    )


def test_ingest_source_skill_frontmatter_parses() -> None:
    # codex-sources-us-005 Scenario 2 — frontmatter parses as YAML dict with
    # name == 'ingest-source' and a non-empty string description.
    fm = _load_frontmatter(INGEST_SOURCE_SKILL_PATH)
    assert fm.get("name") == "ingest-source", (
        f"expected name 'ingest-source', got: {fm.get('name')!r}"
    )
    description = fm.get("description")
    assert isinstance(description, str) and description.strip(), (
        "description must be a non-empty string"
    )


def test_ingest_source_skill_length_bounded() -> None:
    # codex-sources-us-005 Scenario 4 — structural line-count bound 40..200
    # (FR-18 ~80-120 guideline with slack).
    lines = INGEST_SOURCE_SKILL_PATH.read_text(encoding="utf-8").splitlines()
    assert 40 <= len(lines) <= 200, (
        f"skill file line count {len(lines)} out of bounds [40, 200]"
    )


def test_ingest_source_skill_flow_headings_present() -> None:
    # codex-sources-us-005 Scenario 6 — each required flow step must surface
    # in at least one heading (case-insensitive substring match). No prose
    # assertion per decisions-006-no-seed-content-tests.
    body = INGEST_SOURCE_SKILL_PATH.read_text(encoding="utf-8")
    headings = [h.lower() for h in _extract_headings(body)]
    for token_group in INGEST_SOURCE_HEADING_TOKENS:
        assert any(
            any(tok in h for tok in token_group) for h in headings
        ), f"no heading matches any of tokens {token_group} (headings: {headings})"


# ---- US-006 ---------------------------------------------------------------


def test_refresh_source_skill_file_exists() -> None:
    # codex-sources-us-006 Scenario 3 — shipped package default file must exist
    # and be non-empty at src/lore/defaults/skills/refresh-source/SKILL.md.
    assert REFRESH_SOURCE_SKILL_PATH.is_file(), (
        f"missing skill file: {REFRESH_SOURCE_SKILL_PATH}"
    )
    assert REFRESH_SOURCE_SKILL_PATH.stat().st_size > 0, (
        f"skill file is empty: {REFRESH_SOURCE_SKILL_PATH}"
    )


def test_refresh_source_skill_frontmatter_parses() -> None:
    # codex-sources-us-006 Scenario 2 — frontmatter parses with
    # name == 'refresh-source' and non-empty string description.
    fm = _load_frontmatter(REFRESH_SOURCE_SKILL_PATH)
    assert fm.get("name") == "refresh-source", (
        f"expected name 'refresh-source', got: {fm.get('name')!r}"
    )
    description = fm.get("description")
    assert isinstance(description, str) and description.strip(), (
        "description must be a non-empty string"
    )


def test_refresh_source_skill_length_bounded() -> None:
    # codex-sources-us-006 Scenario 4 — structural line-count bound 40..200.
    lines = REFRESH_SOURCE_SKILL_PATH.read_text(encoding="utf-8").splitlines()
    assert 40 <= len(lines) <= 200, (
        f"skill file line count {len(lines)} out of bounds [40, 200]"
    )


def test_refresh_source_skill_flow_headings_present() -> None:
    # codex-sources-us-006 Scenario 5 — each required flow step must surface
    # in at least one heading (case-insensitive substring match). Structural
    # only per decisions-006-no-seed-content-tests.
    body = REFRESH_SOURCE_SKILL_PATH.read_text(encoding="utf-8")
    headings = [h.lower() for h in _extract_headings(body)]
    for token_group in REFRESH_SOURCE_HEADING_TOKENS:
        assert any(
            any(tok in h for tok in token_group) for h in headings
        ), f"no heading matches any of tokens {token_group} (headings: {headings})"


# ---------------------------------------------------------------------------
# US-007 (codex-sources-us-007) — conceptual-entities-artifact outbound
# related regression guard. The edit was pre-landed by codex-apply on the
# project codex file .lore/codex/conceptual/entities/artifact.md. This test
# pins the outbound invariant so a future reversion turns the suite red.
# Anchors:
#   codex-sources-us-007 AC Scenario 1 — the edited doc's frontmatter
#   contains the four canonical outbound IDs named in the Tech Spec.
#   decisions-006-no-seed-content-tests — structural assertion only; we
#   assert the four required IDs are present as a subset, without pinning
#   body prose or rejecting additional outbound edges the project may add.
# ---------------------------------------------------------------------------


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONCEPTUAL_ARTIFACT_MD = (
    PROJECT_ROOT
    / ".lore" / "codex" / "conceptual" / "entities" / "artifact.md"
)

REQUIRED_ARTIFACT_OUTBOUND_IDS = {
    "conceptual-entities-doctrine",
    "conceptual-entities-knight",
    "conceptual-workflows-lore-init",
    "tech-cli-commands",
}


def test_conceptual_entities_artifact_has_required_outbound_related() -> None:
    # codex-sources-us-007 AC Scenario 1 — the conceptual-entities-artifact
    # doc must expose at least the four canonical outbound IDs named in the
    # Tech Spec so `lore codex map --depth 1` is non-empty. Pre-landed by
    # codex-apply; this test fails loud if the edit is ever reverted.
    assert CONCEPTUAL_ARTIFACT_MD.is_file(), (
        f"missing canonical doc: {CONCEPTUAL_ARTIFACT_MD}"
    )
    fm = _load_frontmatter(CONCEPTUAL_ARTIFACT_MD)
    related = fm.get("related")
    assert isinstance(related, list) and related, (
        "conceptual-entities-artifact must declare a non-empty outbound "
        "'related' list — reversion would make it an outbound-orphan hub."
    )
    missing = REQUIRED_ARTIFACT_OUTBOUND_IDS - set(related)
    assert not missing, (
        f"conceptual-entities-artifact.related is missing required outbound "
        f"IDs: {sorted(missing)}"
    )
