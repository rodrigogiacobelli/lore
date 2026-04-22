"""E2E tests for `lore health` schema validation.

US-004 Red — schema-validation-us-004
Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)

Covers PRD Workflows 1, 2, 3, plus FR-1..FR-6 full-kind coverage, FR-9
multi-violation, and FR-25 previously-silent skip. Every test MUST fail
until US-004 Green lands.
"""

from __future__ import annotations

import json as _json
from pathlib import Path

import pytest
import yaml as _yaml

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _knight_path(project_dir: Path) -> Path:
    return (
        project_dir
        / ".lore"
        / "knights"
        / "default"
        / "feature-implementation"
        / "pm.md"
    )


def _doctrine_design_path(project_dir: Path) -> Path:
    return (
        project_dir
        / ".lore"
        / "doctrines"
        / "default"
        / "feature-implementation"
        / "feature-implementation.design.md"
    )


# ---------------------------------------------------------------------------
# Scenario 1: Green audit on a clean project (PRD Workflow 1)
# ---------------------------------------------------------------------------


def test_e2e_workflow_1_green_on_fresh_init(runner, project_dir):
    """conceptual-workflows-lore-init — W1 green audit on pristine init."""
    result = runner.invoke(main, ["health"])
    assert result.exit_code == 0, result.output
    assert "Schema validation: 0 errors" in result.output


# ---------------------------------------------------------------------------
# Scenario 2: Hallucinated knight field caught (PRD Workflow 2)
# ---------------------------------------------------------------------------


def test_e2e_workflow_2_hallucinated_knight_field(runner, project_dir):
    """conceptual-workflows-knight-list — W2 stability field on a knight."""
    _write(
        _knight_path(project_dir),
        "---\n"
        "id: pm\n"
        "title: Product Manager\n"
        "summary: Writes PRDs.\n"
        "stability: experimental\n"
        "---\n"
        "# Body\n",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert (
        "ERROR .lore/knights/default/feature-implementation/pm.md"
        in result.output
    )
    assert "  kind: knight" in result.output
    assert "  schema: lore://schemas/knight-frontmatter" in result.output
    assert "  rule: additionalProperties" in result.output
    assert "  path: /stability" in result.output
    assert "Schema validation: 1 error" in result.output


# ---------------------------------------------------------------------------
# Scenario 3: Missing required field on doctrine design (PRD Workflow 3)
# ---------------------------------------------------------------------------


def test_e2e_workflow_3_missing_required_doctrine_design(runner, project_dir):
    """conceptual-workflows-doctrine-show — W3 missing summary on design."""
    path = _doctrine_design_path(project_dir)
    text = path.read_text(encoding="utf-8")
    new_text = "\n".join(
        line for line in text.splitlines() if not line.startswith("summary:")
    ) + "\n"
    path.write_text(new_text, encoding="utf-8")

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "  kind: doctrine-design-frontmatter" in result.output
    assert "  schema: lore://schemas/doctrine-design-frontmatter" in result.output
    assert "  rule: required" in result.output
    assert "  path: /" in result.output
    assert "Schema validation: 1 error" in result.output


# ---------------------------------------------------------------------------
# Scenario 4: Every kind is covered (FR-1..FR-6)
# ---------------------------------------------------------------------------


def test_e2e_every_kind_covered(runner, project_dir):
    """conceptual-workflows-health — FR-1..FR-6 end-to-end, one bad per kind."""
    # Bad doctrine .yaml
    _write(
        project_dir
        / ".lore"
        / "doctrines"
        / "default"
        / "broken"
        / "broken.yaml",
        "id: broken\ntitle: Broken\nsummary: s\nbogus_top_level: nope\nsteps: []\n",
    )
    # Bad doctrine .design.md
    _write(
        project_dir
        / ".lore"
        / "doctrines"
        / "default"
        / "broken"
        / "broken.design.md",
        "---\nid: broken\ntitle: Broken\nbogus: yes\n---\nBody.\n",
    )
    # Bad knight
    _write(
        _knight_path(project_dir),
        "---\nid: pm\ntitle: Product Manager\nsummary: s\nstability: x\n---\n",
    )
    # Bad watcher
    _write(
        project_dir / ".lore" / "watchers" / "default" / "bad.yaml",
        "id: bad\ntitle: Bad\nevent: quest_close\naction: noop\nbogus: yes\n",
    )
    # Bad codex
    _write(
        project_dir / ".lore" / "codex" / "bad-doc.md",
        "---\nid: bad-doc\ntitle: Bad\nsummary: s\nbogus: yes\n---\nBody.\n",
    )
    # Bad artifact
    _write(
        project_dir / ".lore" / "artifacts" / "default" / "group" / "fi-bad.md",
        "---\nid: fi-bad\ntitle: Bad\nsummary: s\nbogus: yes\n---\nBody.\n",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "Schema validation: 6 errors" in result.output
    for label in (
        "kind: doctrine-yaml",
        "kind: doctrine-design-frontmatter",
        "kind: knight",
        "kind: watcher",
        "kind: codex",
        "kind: artifact",
    ):
        assert label in result.output, f"missing {label!r} in:\n{result.output}"


# ---------------------------------------------------------------------------
# Scenario 5: Multiple violations per file all reported (FR-9)
# ---------------------------------------------------------------------------


def test_e2e_multiple_violations_one_file(runner, project_dir):
    """conceptual-workflows-health — FR-9 no short-circuit; three distinct blocks."""
    _write(
        _knight_path(project_dir),
        "---\nid: pm\nstability: x\n---\n",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "Schema validation: 3 errors" in result.output
    # One additionalProperties + two required (title + summary)
    assert result.output.count("rule: additionalProperties") == 1
    assert result.output.count("rule: required") == 2


# ---------------------------------------------------------------------------
# Scenario 6: Previously silent skips are now loud (FR-25)
# ---------------------------------------------------------------------------


def test_e2e_previously_silent_skip_is_loud(runner, project_dir):
    """conceptual-workflows-artifact-new — FR-25 loud failure on no-frontmatter artifact."""
    _write(
        project_dir
        / ".lore"
        / "artifacts"
        / "default"
        / "group"
        / "broken.md",
        "No frontmatter at all.\n",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "rule: missing-frontmatter" in result.output
    assert (
        "ERROR .lore/artifacts/default/group/broken.md" in result.output
    )


# ---------------------------------------------------------------------------
# US-006 — unparseable YAML, missing frontmatter, read-failed
# schema-validation-us-006 / conceptual-workflows-health — FR-10, FR-11, FR-25
# ---------------------------------------------------------------------------


def _good_watcher_text() -> str:
    return (
        "id: good\n"
        "title: Good\n"
        "summary: ok\n"
        "watch_target:\n  - src/\n"
        "interval: on_merge\n"
        "action:\n  - doctrine: feature-implementation\n"
    )


def test_us006_e2e_unparseable_watcher_yaml_scan_continues(runner, project_dir):
    """Scenario 1: one broken watcher + one good watcher — exactly one yaml-parse
    ERROR block, scan did not abort, summary reads 'Schema validation: 1 error'."""
    _write(
        project_dir / ".lore" / "watchers" / "default" / "broken.yaml",
        "watch_target: : :",
    )
    _write(
        project_dir / ".lore" / "watchers" / "default" / "good.yaml",
        _good_watcher_text(),
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    # Exactly one yaml-parse rule line.
    assert result.output.count("rule: yaml-parse") == 1
    assert "  path: /" in result.output
    # Exactly one schema-block ERROR for the broken watcher — the good one is silent.
    schema_error_lines = [
        l for l in result.output.splitlines() if l.startswith("ERROR .lore/")
    ]
    assert len(schema_error_lines) == 1
    assert "broken.yaml" in schema_error_lines[0]
    assert "ERROR .lore/watchers/default/good.yaml" not in result.output
    # Summary line is exactly "Schema validation: 1 error".
    assert "Schema validation: 1 error\n" in result.output + "\n"
    assert "Schema validation: 1 errors" not in result.output


def test_us006_e2e_missing_frontmatter_exact_message(runner, project_dir):
    """Scenario 2: orphan.md with no frontmatter emits message line
    'message: File has no YAML frontmatter block' (no trailing period)."""
    _write(
        project_dir / ".lore" / "codex" / "notes" / "orphan.md",
        "just some notes\n",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "  rule: missing-frontmatter" in result.output
    assert "  path: /" in result.output
    # Exact message line — no trailing period.
    assert "  message: File has no YAML frontmatter block\n" in (result.output + "\n")
    assert "  message: File has no YAML frontmatter block." not in result.output
    assert "Schema validation: 1 error" in result.output


def test_us006_e2e_read_failed_permission_denied_on_locked_knight(
    runner, project_dir, monkeypatch
):
    """Scenario 3: permission-denied file becomes one read-failed ERROR block
    whose message contains 'Permission denied'."""
    p = (
        project_dir
        / ".lore"
        / "knights"
        / "default"
        / "locked"
        / "pm.md"
    )
    _write(p, "---\nid: pm\ntitle: PM\nsummary: s\n---\n")

    real_read_text = Path.read_text
    real_open = open

    def boom_rt(self, *a, **kw):
        if self == p:
            raise PermissionError("Permission denied")
        return real_read_text(self, *a, **kw)

    def boom_open(path, *a, **kw):
        if str(path) == str(p):
            raise PermissionError("Permission denied")
        return real_open(path, *a, **kw)

    monkeypatch.setattr(Path, "read_text", boom_rt)
    monkeypatch.setattr("builtins.open", boom_open)

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "  rule: read-failed" in result.output
    assert "Permission denied" in result.output
    # Exactly one read-failed block.
    assert result.output.count("rule: read-failed") == 1


def test_us006_e2e_yaml_parse_single_error_block_no_cascade(runner, project_dir):
    """Scenario 4: an unparseable doctrine yaml that would also fail schema
    validation if it parsed produces exactly one ERROR block (FR-10)."""
    _write(
        project_dir
        / ".lore"
        / "doctrines"
        / "default"
        / "broken"
        / "broken.yaml",
        # Both bad YAML and missing all required fields.
        "id: : :\nsteps: : : nope",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    error_lines = [l for l in result.output.splitlines() if l.startswith("ERROR ")]
    # Only one ERROR block for broken.yaml (may coexist with other kinds on a
    # pristine project — so filter).
    broken_errors = [l for l in error_lines if "broken.yaml" in l]
    assert len(broken_errors) == 1
    # And only one rule line for that file: yaml-parse. No cascading required
    # or additionalProperties rule lines from a second pass on the same file.
    assert result.output.count("rule: yaml-parse") == 1
    # The summary must count exactly one schema violation.
    assert "Schema validation: 1 error" in result.output


# ---------------------------------------------------------------------------
# G2 Red — Codex sources layer E2E (US-002, US-003, US-008)
# Exercises:
#   lore codex show codex-sources-us-002 codex-sources-us-003 codex-sources-us-008
# Anchors:
#   conceptual-workflows-health
#   decisions-006-no-seed-content-tests (structural assertions only)
# ---------------------------------------------------------------------------


def _fm_block(fields: dict) -> str:
    """Render a YAML frontmatter block with `Body.` content."""
    return "---\n" + _yaml.safe_dump(fields, sort_keys=False) + "---\nBody.\n"


def _write_canonical_e2e(project_dir: Path, doc_id: str, related=None) -> Path:
    """Write a canonical codex doc under .lore/codex/<doc_id>.md."""
    fields = {"id": doc_id, "title": doc_id, "summary": "s"}
    if related is not None:
        fields["related"] = list(related)
    path = project_dir / ".lore" / "codex" / f"{doc_id}.md"
    _write(path, _fm_block(fields))
    return path


def _write_source_e2e(
    project_dir: Path, system: str, src_id: str, related
) -> Path:
    """Write a source doc under .lore/codex/sources/<system>/<src_id>.md."""
    fields = {"id": src_id, "title": src_id, "summary": "s", "related": list(related)}
    path = (
        project_dir
        / ".lore"
        / "codex"
        / "sources"
        / system
        / f"{src_id}.md"
    )
    _write(path, _fm_block(fields))
    return path


# --- US-003 E2E -------------------------------------------------------------


def test_sources_never_emit_island_warnings(runner, project_dir):
    """codex-sources-us-003 — E2E Scenario 1: valid sources produce zero island nodes."""
    _write_canonical_e2e(project_dir, "conceptual-entities-foo")
    for system, src_id in [
        ("jira", "K-1"),
        ("jira", "K-2"),
        ("meetings", "2026-04-21"),
    ]:
        _write_source_e2e(
            project_dir, system, src_id, related=["conceptual-entities-foo"]
        )

    result = runner.invoke(main, ["health", "--scope", "codex", "--json"])

    payload = _json.loads(result.output)
    islanded_source_ids = [
        i for i in payload["issues"]
        if i["check"] == "island_node"
        and i["id"] in {"K-1", "K-2", "2026-04-21"}
    ]
    assert islanded_source_ids == []


def test_skip_scoped_to_island_pass_only(runner, project_dir):
    """codex-sources-us-003 — E2E Scenario 2: schema-bad source still errors, no island.

    The source with empty `related: []` must emit a schema error (per US-002)
    but no island_node issue for the same path.
    """
    _write(
        project_dir / ".lore" / "codex" / "sources" / "jira" / "K-3.md",
        _fm_block({"id": "K-3", "title": "T", "summary": "S", "related": []}),
    )

    result = runner.invoke(main, ["health", "--json"])

    assert result.exit_code != 0, result.output
    payload = _json.loads(result.output)
    for_k3 = [
        i for i in payload["issues"]
        if (i.get("id") or "").endswith("K-3.md") or i.get("id") == "K-3"
    ]
    assert any(i["check"] == "schema" for i in for_k3)
    assert not any(i["check"] == "island_node" for i in for_k3)


def test_canonical_island_detection_unchanged(runner, project_dir):
    """codex-sources-us-003 — E2E Scenario 3: canonical islands still flagged."""
    _write_canonical_e2e(project_dir, "conceptual-foo")  # zero in/out

    result = runner.invoke(main, ["health", "--json"])

    payload = _json.loads(result.output)
    assert any(
        i["check"] == "island_node" and i["id"] == "conceptual-foo"
        for i in payload["issues"]
    )


def test_absent_sources_dir_is_graceful(runner, project_dir):
    """codex-sources-us-003 — E2E Scenario 4: absent sources/ produces no errors."""
    # deliberately no .lore/codex/sources/ tree — just ensure codex/ exists
    (project_dir / ".lore" / "codex").mkdir(parents=True, exist_ok=True)

    result = runner.invoke(main, ["health", "--scope", "codex"])

    assert result.exit_code == 0, result.output
    # No complaint about a missing sources directory.
    assert "sources" not in result.output.lower() or (
        "Health check passed" in result.output
    )


def test_source_broken_outbound_related_fires(runner, project_dir):
    """codex-sources-us-003 — E2E Scenario 5: sources participate in broken-link pass."""
    _write_source_e2e(
        project_dir, "jira", "K-4", related=["nonexistent-canonical-id"]
    )

    result = runner.invoke(main, ["health", "--json"])

    assert result.exit_code != 0, result.output
    payload = _json.loads(result.output)
    hits = [
        i for i in payload["issues"]
        if i["check"] == "broken_related_link" and i["id"] == "K-4"
    ]
    assert len(hits) == 1


# --- US-002 E2E -------------------------------------------------------------


def test_source_file_empty_related_fails_schema(runner, project_dir):
    """codex-sources-us-002 — E2E Scenario 1: empty related fails with minItems."""
    _write(
        project_dir / ".lore" / "codex" / "sources" / "jira" / "KONE-23335.md",
        _fm_block({"id": "KONE-23335", "title": "T", "summary": "S", "related": []}),
    )

    result = runner.invoke(main, ["health", "--scope", "schemas", "--json"])

    assert result.exit_code != 0, result.output
    payload = _json.loads(result.output)
    hits = [i for i in payload["issues"] if (i.get("id") or "").endswith("KONE-23335.md")]
    assert len(hits) == 1
    assert hits[0]["severity"] == "error"
    assert hits[0]["check"] == "schema"
    assert hits[0]["entity_type"] == "codex-source"
    assert hits[0]["schema_id"] == "lore://schemas/codex-source-frontmatter"
    assert hits[0]["rule"] == "minItems"
    assert hits[0]["pointer"] == "/related"


def test_source_file_missing_related_fails_schema(runner, project_dir):
    """codex-sources-us-002 — E2E Scenario 1b: missing related fails with required."""
    _write(
        project_dir / ".lore" / "codex" / "sources" / "jira" / "KONE-23335.md",
        _fm_block({"id": "KONE-23335", "title": "T", "summary": "S"}),
    )

    result = runner.invoke(main, ["health", "--scope", "schemas", "--json"])

    assert result.exit_code != 0, result.output
    payload = _json.loads(result.output)
    hits = [
        i for i in payload["issues"]
        if (i.get("id") or "").endswith("KONE-23335.md")
        and i.get("rule") == "required"
    ]
    assert hits
    assert hits[0]["entity_type"] == "codex-source"
    assert "related" in (hits[0].get("detail") or "")


def test_valid_source_passes_schema(runner, project_dir):
    """codex-sources-us-002 — E2E Scenario 2: valid source passes schema scope."""
    _write_canonical_e2e(project_dir, "conceptual-entities-foo")
    _write(
        project_dir / ".lore" / "codex" / "sources" / "jira" / "KONE-23335.md",
        _fm_block(
            {
                "id": "KONE-23335",
                "title": "T",
                "summary": "S",
                "related": ["conceptual-entities-foo"],
            }
        ),
    )

    result = runner.invoke(main, ["health", "--scope", "schemas"])

    assert result.exit_code == 0, result.output
    assert "Health check passed" in result.output


def test_canonical_doc_uses_codex_frontmatter_not_source_schema(
    runner, project_dir
):
    """codex-sources-us-002 — E2E Scenario 3: dispatch is per-path.

    A canonical doc must never be validated against the source schema.
    """
    _write_canonical_e2e(
        project_dir,
        "conceptual-entities-foo",
        related=["conceptual-entities-bar"],
    )
    _write_canonical_e2e(project_dir, "conceptual-entities-bar")

    result = runner.invoke(main, ["health", "--scope", "schemas", "--json"])

    payload = _json.loads(result.output)
    offending = [
        i for i in payload["issues"]
        if i.get("schema_id") == "lore://schemas/codex-source-frontmatter"
        and "conceptual-entities-foo" in (i.get("id") or "")
    ]
    assert offending == []


def test_source_file_extra_field_fails_schema(runner, project_dir):
    """codex-sources-us-002 — E2E Scenario 4: extra field -> additionalProperties."""
    _write_canonical_e2e(project_dir, "conceptual-entities-foo")
    _write(
        project_dir
        / ".lore"
        / "codex"
        / "sources"
        / "meetings"
        / "2026-04-21.md",
        _fm_block(
            {
                "id": "kickoff",
                "title": "T",
                "summary": "S",
                "related": ["conceptual-entities-foo"],
                "priority": 3,
            }
        ),
    )

    result = runner.invoke(main, ["health", "--json"])

    assert result.exit_code != 0, result.output
    payload = _json.loads(result.output)
    hits = [i for i in payload["issues"] if (i.get("id") or "").endswith("2026-04-21.md")]
    assert any(
        i.get("entity_type") == "codex-source"
        and i.get("rule") == "additionalProperties"
        and i.get("pointer") == "/priority"
        for i in hits
    )


def test_source_file_missing_required_field_fails(runner, project_dir):
    """codex-sources-us-002 — E2E Scenario 5: missing required field names it in detail."""
    _write(
        project_dir / ".lore" / "codex" / "sources" / "jira" / "KONE-1.md",
        _fm_block({"id": "KONE-1", "title": "T"}),  # no summary, no related
    )

    result = runner.invoke(main, ["health", "--json"])

    assert result.exit_code != 0, result.output
    payload = _json.loads(result.output)
    hits = [
        i for i in payload["issues"]
        if (i.get("id") or "").endswith("KONE-1.md")
        and i.get("rule") == "required"
        and "summary" in (i.get("detail") or "")
    ]
    assert hits
    assert hits[0]["entity_type"] == "codex-source"


def test_source_missing_frontmatter_classified_as_schema(runner, project_dir):
    """codex-sources-us-002 — E2E Scenario 6: no frontmatter -> missing-frontmatter."""
    _write(
        project_dir / ".lore" / "codex" / "sources" / "jira" / "KONE-2.md",
        "# KONE-2\n",
    )

    result = runner.invoke(main, ["health", "--json"])

    assert result.exit_code != 0, result.output
    payload = _json.loads(result.output)
    hits = [i for i in payload["issues"] if (i.get("id") or "").endswith("KONE-2.md")]
    assert len(hits) == 1
    assert hits[0]["check"] == "schema"
    assert hits[0]["entity_type"] == "codex-source"
    assert hits[0]["rule"] == "missing-frontmatter"


# --- US-008 E2E -------------------------------------------------------------


def test_canonical_linking_to_source_fails_health(runner, project_dir):
    """codex-sources-us-008 — E2E Scenario 1: canonical back-link fails health."""
    _write_source_e2e(
        project_dir, "jira", "KONE-23335", related=["conceptual-entities-foo"]
    )
    _write_canonical_e2e(
        project_dir, "conceptual-entities-foo", related=["KONE-23335"]
    )

    result = runner.invoke(main, ["health", "--json"])

    assert result.exit_code != 0, result.output
    payload = _json.loads(result.output)
    hits = [
        i for i in payload["issues"]
        if i["check"] == "canonical_links_to_source"
    ]
    assert hits
    assert hits[0]["severity"] == "error"
    assert hits[0]["entity_type"] == "codex"
    assert hits[0]["id"] == "conceptual-entities-foo"
    assert "KONE-23335" in (hits[0].get("detail") or "")


def test_source_to_source_link_permitted(runner, project_dir):
    """codex-sources-us-008 — E2E Scenario 2: source-to-source linking is OK."""
    _write_canonical_e2e(project_dir, "conceptual-entities-foo")
    _write_source_e2e(
        project_dir, "jira", "A", related=["conceptual-entities-foo", "B"]
    )
    _write_source_e2e(
        project_dir, "jira", "B", related=["conceptual-entities-foo"]
    )

    result = runner.invoke(main, ["health", "--json"])

    payload = _json.loads(result.output)
    assert not any(
        i["check"] == "canonical_links_to_source" for i in payload["issues"]
    )


def test_canonical_to_nonexistent_id_stays_broken_related_link(
    runner, project_dir
):
    """codex-sources-us-008 — E2E Scenario 3: classification preserved."""
    _write_canonical_e2e(
        project_dir, "conceptual-entities-foo", related=["nonexistent-id"]
    )

    result = runner.invoke(main, ["health", "--json"])

    payload = _json.loads(result.output)
    assert any(
        i["check"] == "broken_related_link" for i in payload["issues"]
    )
    assert not any(
        i["check"] == "canonical_links_to_source" for i in payload["issues"]
    )


def test_clean_codex_emits_no_canonical_links_to_source(runner, project_dir):
    """codex-sources-us-008 — E2E Scenario 4: clean codex has zero violations."""
    _write_canonical_e2e(
        project_dir,
        "conceptual-entities-foo",
        related=["conceptual-entities-bar"],
    )
    _write_canonical_e2e(project_dir, "conceptual-entities-bar")
    _write_source_e2e(
        project_dir, "jira", "K-1", related=["conceptual-entities-foo"]
    )

    result = runner.invoke(main, ["health", "--json"])

    payload = _json.loads(result.output)
    assert not any(
        i["check"] == "canonical_links_to_source" for i in payload["issues"]
    )


def test_multiple_canonical_links_to_source_violations(runner, project_dir):
    """codex-sources-us-008 — E2E Scenario 5: one issue per offending canonical pair."""
    _write_source_e2e(
        project_dir, "jira", "K-1", related=["conceptual-entities-a"]
    )
    _write_source_e2e(
        project_dir, "jira", "K-2", related=["conceptual-entities-a"]
    )
    _write_canonical_e2e(
        project_dir, "conceptual-entities-a", related=["K-1"]
    )
    _write_canonical_e2e(
        project_dir, "conceptual-entities-b", related=["K-1"]
    )
    _write_canonical_e2e(
        project_dir, "conceptual-entities-c", related=["K-2"]
    )

    result = runner.invoke(main, ["health", "--json"])

    payload = _json.loads(result.output)
    hits = [
        i for i in payload["issues"]
        if i["check"] == "canonical_links_to_source"
    ]
    assert len(hits) == 3
    pairs = {(i["id"], i.get("detail") or "") for i in hits}
    for canonical in ("conceptual-entities-a", "conceptual-entities-b"):
        assert any(p[0] == canonical and "K-1" in p[1] for p in pairs)
    assert any(p[0] == "conceptual-entities-c" and "K-2" in p[1] for p in pairs)
