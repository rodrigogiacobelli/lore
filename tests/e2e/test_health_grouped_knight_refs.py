"""E2E cross-surface tests for grouped knight refs in ``lore health`` (RED).

ADR-011: a rule that holds on one surface and not the other is a bug. The
knights scope is reached through ``lore health --scope knights`` and through
``lore.api.health_check(scope=["knights"])``; both read the same mission
``knight`` field, so both must survive the group-qualified form a doctrine
writes (``tdd-feature/defaults-reviewer.md``) and both must report the same
issues.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from lore.cli import main

KNIGHT_MD = "---\nid: defaults-reviewer\ntitle: Reviewer\nsummary: s\n---\nBody.\n"


def _seed_grouped_knight(project_dir: Path) -> Path:
    target = project_dir / ".lore" / "knights" / "tdd-feature"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "defaults-reviewer.md"
    path.write_text(KNIGHT_MD)
    return path


def _seed_mission(project_dir: Path, knight: str) -> None:
    from tests.conftest import insert_mission, insert_quest

    insert_quest(project_dir, "q-h001", "Quest H")
    insert_mission(
        project_dir, "m-h001", "q-h001", "Mission H", knight=knight, mission_type="knight"
    )


def _cli_issues(runner) -> tuple[int, list[dict]]:
    result = runner.invoke(main, ["health", "--scope", "knights", "--json"])
    payload = json.loads(result.stdout)
    return result.exit_code, payload["issues"]


def _api_issues(project_dir: Path) -> list[dict]:
    from lore.api import health_check

    report = health_check(project_dir, scope=["knights"])
    return [dataclasses.asdict(i) for i in report.issues]


class TestGroupedKnightRefDoesNotKillTheScan:
    def test_cli_knights_scope_survives_a_grouped_ref(self, runner, project_dir):
        _seed_grouped_knight(project_dir)
        _seed_mission(project_dir, "tdd-feature/defaults-reviewer.md")

        exit_code, issues = _cli_issues(runner)

        assert exit_code == 0
        assert issues == []

    def test_api_knights_scope_survives_a_grouped_ref(self, runner, project_dir):
        _seed_grouped_knight(project_dir)
        _seed_mission(project_dir, "tdd-feature/defaults-reviewer.md")

        assert _api_issues(project_dir) == []

    def test_neither_surface_reports_scan_failed(self, runner, project_dir):
        _seed_grouped_knight(project_dir)
        _seed_mission(project_dir, "tdd-feature/defaults-reviewer.md")

        _, cli = _cli_issues(runner)
        api = _api_issues(project_dir)

        assert [i for i in cli if i["check"] == "scan_failed"] == []
        assert [i for i in api if i["check"] == "scan_failed"] == []


class TestUnresolvableGroupedRefIsAnOrdinaryFinding:
    def test_cli_reports_missing_file(self, runner, project_dir):
        _seed_mission(project_dir, "tdd-feature/nobody.md")

        exit_code, issues = _cli_issues(runner)

        assert exit_code == 1
        assert [i["check"] for i in issues] == ["missing_file"]
        assert issues[0]["id"] == "tdd-feature/nobody.md"

    def test_both_surfaces_report_the_same_issue(self, runner, project_dir):
        _seed_mission(project_dir, "tdd-feature/nobody.md")

        _, cli = _cli_issues(runner)
        api = _api_issues(project_dir)

        assert cli == api
