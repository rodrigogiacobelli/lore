"""US-011 regression guard — fresh project has zero schema errors.

After ``lore init`` into an empty directory, ``health_check`` scoped to
``schemas`` must return zero errors. This guarantees the seeded defaults
that land in the new project cannot carry forbidden frontmatter keys.

The cleanup work originally planned under US-011 was absorbed into
US-004. These tests exist solely as regression guards to pin the
invariant permanently.
"""

from __future__ import annotations

from lore.health import health_check


def test_fresh_project_has_no_schema_errors(project_dir) -> None:
    # US-011 regression guard — lore init into a tmp project and then
    # running health_check(scope=["schemas"]) must surface zero errors.
    report = health_check(project_root=project_dir, scope=["schemas"])
    schema_errors = [i for i in report.errors if i.entity_type != "schemas"]
    assert list(report.errors) == [], (
        f"fresh project surfaced schema errors: {list(report.errors)}"
    )
    # Belt-and-braces: ensure the scan actually ran (didn't fail silently).
    assert schema_errors == []


def test_fresh_project_health_schemas_scope_no_scan_failure(project_dir) -> None:
    # US-011 regression guard — the schemas checker must not raise; a
    # scan_failed issue would indicate the defaults tree or schema loader
    # regressed.
    report = health_check(project_root=project_dir, scope=["schemas"])
    scan_failed = [i for i in report.errors if i.check == "scan_failed"]
    assert scan_failed == [], f"schemas scope scan failed: {scan_failed}"
