"""Oracle report generation — human-readable markdown reports."""

import re
import shutil
from pathlib import Path

from lore import paths


def slugify(title: str) -> str:
    """Convert a title into a URL-friendly slug.

    - Lowercase
    - Replace spaces and non-alphanumeric characters with hyphens
    - Collapse consecutive hyphens
    - Trim leading/trailing hyphens
    - Truncate to 40 characters at word boundary
    """
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    if len(slug) > 40:
        truncated = slug[:40]
        # Try to cut at a word boundary (hyphen)
        last_hyphen = truncated.rfind("-")
        if last_hyphen > 0:
            truncated = truncated[:last_hyphen]
        slug = truncated.rstrip("-")
    return slug


def make_entity_slug(entity_id: str, title: str) -> str:
    """Combine entity ID with slugified title: {id}-{slug}.

    The 40-char limit applies to the ENTIRE result (id + slug combined).
    """
    slug = slugify(title)
    combined = f"{entity_id}-{slug}"
    if len(combined) > 40:
        truncated = combined[:40]
        last_hyphen = truncated.rfind("-")
        if last_hyphen > len(entity_id):
            truncated = truncated[:last_hyphen]
        combined = truncated.rstrip("-")
    return combined


def generate_reports(project_root: Path) -> None:
    """Generate markdown reports in .lore/reports/."""
    from lore.db import (
        get_aggregate_stats,
        get_mission_blocks,
        get_mission_depends_on,
        get_missions_for_quest,
        list_missions,
        list_quests,
    )

    reports_dir = paths.reports_dir(project_root)

    # Delete and recreate reports directory
    if reports_dir.exists():
        shutil.rmtree(reports_dir)
    reports_dir.mkdir(parents=True)

    # Generate summary.md
    stats = get_aggregate_stats(project_root)
    _write_summary(reports_dir / "summary.md", stats)

    # Get all quests (including closed) and generate per-quest reports
    quests = list_quests(project_root, include_closed=True)

    for quest in quests:
        missions = get_missions_for_quest(project_root, quest["id"])
        if not missions:
            continue

        quests_dir = reports_dir / "quests"
        quests_dir.mkdir(exist_ok=True)

        quest_slug = make_entity_slug(quest["id"], quest["title"])
        quest_dir = quests_dir / quest_slug
        quest_dir.mkdir(parents=True, exist_ok=True)

        _write_quest_index(quest_dir / "index.md", quest, missions)

        for mission in missions:
            mission_id = mission["id"]
            m_part = mission_id.split("/")[-1]
            filename = make_entity_slug(m_part, mission["title"]) + ".md"
            depends_on = get_mission_depends_on(project_root, mission_id)
            blocks = get_mission_blocks(project_root, mission_id)
            _write_mission_file(quest_dir / filename, mission, depends_on, blocks)

    # Generate standalone mission reports (quest_id is None)
    grouped = list_missions(project_root, include_closed=True)
    standalone_missions = grouped.get(None, [])

    if standalone_missions:
        missions_dir = reports_dir / "missions"
        missions_dir.mkdir(exist_ok=True)

        for mission in standalone_missions:
            mission_id = mission["id"]
            filename = make_entity_slug(mission_id, mission["title"]) + ".md"
            depends_on = get_mission_depends_on(project_root, mission_id)
            blocks = get_mission_blocks(project_root, mission_id)
            _write_mission_file(missions_dir / filename, mission, depends_on, blocks)


def _write_summary(path: Path, stats: dict) -> None:
    """Write the summary.md report."""
    q = stats["quests"]
    m = stats["missions"]
    q_total = q["open"] + q["in_progress"] + q["closed"]
    m_total = m["open"] + m["in_progress"] + m["blocked"] + m["closed"]

    content = f"""# Project Summary

## Quests

| Status | Count |
|--------|-------|
| open | {q['open']} |
| in_progress | {q['in_progress']} |
| closed | {q['closed']} |
| **Total** | **{q_total}** |

## Missions

| Status | Count |
|--------|-------|
| open | {m['open']} |
| in_progress | {m['in_progress']} |
| blocked | {m['blocked']} |
| closed | {m['closed']} |
| **Total** | **{m_total}** |
"""
    path.write_text(content)


def _write_quest_index(path: Path, quest, missions) -> None:
    """Write a quest index.md report."""
    lines = [
        f"# {quest['title']}",
        "",
        f"**ID:** {quest['id']}",
        f"**Status:** {quest['status']}",
        f"**Priority:** {quest['priority']}",
        "",
        quest["description"] or "",
        "",
        "## Missions",
        "",
        "| ID | Title | Status | Priority | Type | Knight |",
        "|----|-------|--------|----------|------|--------|",
    ]

    for m in missions:
        knight = m["knight"] or "-"
        lines.append(f"| {m['id']} | {m['title']} | {m['status']} | {m['priority']} | {m['mission_type']} | {knight} |")

    lines.append("")
    path.write_text("\n".join(lines))


def _write_mission_file(path: Path, mission, depends_on: list, blocks: list) -> None:
    """Write an individual mission markdown file."""
    knight = mission["knight"] or "None"
    description = mission["description"] or "No description."
    needs_str = ", ".join(depends_on) if depends_on else "None"
    blocks_str = ", ".join(blocks) if blocks else "None"

    lines = [
        f"# {mission['title']}",
        "",
        f"**ID:** {mission['id']}",
        f"**Status:** {mission['status']}",
        f"**Priority:** {mission['priority']}",
        f"**Type:** {mission['mission_type']}",
        f"**Knight:** {knight}",
        "",
        "## Description",
        "",
        description,
        "",
        "## Dependencies",
        "",
        f"**Needs:** {needs_str}",
        f"**Blocks:** {blocks_str}",
    ]

    block_reason = mission["block_reason"]
    if block_reason:
        lines.extend([
            "",
            "## Block Reason",
            "",
            block_reason,
        ])

    lines.append("")
    path.write_text("\n".join(lines))
