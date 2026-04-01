"""Click command definitions for the Lore CLI."""

import json
from pathlib import Path

import yaml

import click

from lore import __version__
from lore import paths
from lore import validators
from lore import knight as knight_module
from lore import graph
from lore.root import find_project_root, ProjectNotFoundError


def _validate_mission_id(entity_id, ctx):
    """Validate a mission ID format. Returns True if valid, handles error if not."""
    json_mode = ctx.obj.get("json", False)
    err = validators.validate_mission_id(entity_id)
    if err:
        if json_mode:
            click.echo(json.dumps({"error": err}), err=True)
        else:
            click.echo(err, err=True)
        ctx.exit(1)
        return False
    return True


def _validate_entity_id(entity_id, ctx):
    """Validate an entity ID format (quest or mission). Returns True if valid."""
    json_mode = ctx.obj.get("json", False)
    err = validators.validate_entity_id(entity_id)
    if err:
        if json_mode:
            click.echo(json.dumps({"error": err}), err=True)
        else:
            click.echo(err, err=True)
        ctx.exit(1)
        return False
    return True


def _validate_sender_id(sender, ctx):
    """Validate a sender ID format (q-xxxx or q-xxxx/m-yyyy). Returns True if valid."""
    json_mode = ctx.obj.get("json", False)
    err = validators.validate_entity_id(sender)
    if err:
        if json_mode:
            click.echo(json.dumps({"error": err}), err=True)
        else:
            click.echo(err, err=True)
        ctx.exit(1)
        return False
    return True


def _validate_name(name, ctx):
    """Validate a knight or doctrine name. Returns True if valid, handles error if not."""
    json_mode = ctx.obj.get("json", False)
    err = validators.validate_name(name)
    if err:
        if json_mode:
            click.echo(json.dumps({"error": err}), err=True)
        else:
            click.echo(err, err=True)
        ctx.exit(1)
        return False
    return True


def _format_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Format a table with consistent column padding and spacing.

    Rules:
    - 2-space indent before first column
    - 2-space gap between columns
    - Each column is padded to the widest value (header or any row)
    - Last column is NOT right-padded
    - Returns a list of strings (header + one per row)
    """
    num_cols = len(headers)
    # Compute column widths as max of header width and all row values
    col_widths = []
    for i, h in enumerate(headers):
        w = len(h)
        for row in rows:
            if i < len(row):
                w = max(w, len(row[i]))
        col_widths.append(w)

    lines = []
    for row_data in [headers] + [list(r) for r in rows]:
        parts = []
        for i, col_w in enumerate(col_widths):
            val = row_data[i] if i < len(row_data) else ""
            if i == num_cols - 1:
                # Last column: no padding
                parts.append(val)
            else:
                parts.append(f"{val:<{col_w}}")
        lines.append("  " + "  ".join(parts))
    return lines


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="lore")
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.pass_context
def main(ctx, json_mode):
    """Lore — Agent Task Manager.

    Lore organises agent work into two core entity types:

    \b
    Quest   — a body of work (feature, fix, or refactor).
    Mission — a single executable task assigned to an agent.

    Supporting entities:

    \b
    Knight   — a reusable agent persona attached to missions.
    Doctrine — workflow templates that guide how missions are executed.
    Codex    — project documentation, searchable and graph-traversable.
    Artifact — reusable read-only template files referenced by stable ID.
    Watcher  — definitions for agents that monitor and react to project state.

    Run any command group with --help for details on that concept.
    """
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_mode

    # init and --help don't require a project root
    if ctx.invoked_subcommand in ("init",):
        return

    try:
        ctx.obj["project_root"] = find_project_root()
    except ProjectNotFoundError as e:
        if json_mode:
            click.echo(json.dumps({"error": str(e)}), err=True)
        else:
            click.echo(str(e), err=True)
        ctx.exit(1)
        return

    if ctx.invoked_subcommand is None:
        _show_dashboard(ctx)


def _show_dashboard(ctx):
    """Display the dashboard overview of active quests with mission progress."""
    from lore.db import get_dashboard_quests

    project_root = ctx.obj["project_root"]
    quests = get_dashboard_quests(project_root)
    json_mode = ctx.obj.get("json", False)

    if json_mode:
        data = {
            "quests": [
                {
                    "id": q["id"],
                    "title": q["title"],
                    "status": q["status"],
                    "priority": q["priority"],
                    "missions": q["missions"],
                }
                for q in quests
            ]
        }
        click.echo(json.dumps(data))
        return

    if not quests:
        click.echo('No quests yet. Run "lore new quest" to get started.')
        return

    for q in quests:
        m = q["missions"]
        click.echo(
            f"  {q['id']}  P{q['priority']}  [{q['status']}]  {q['title']}  "
            f"(open:{m['open']} in_progress:{m['in_progress']} blocked:{m['blocked']} closed:{m['closed']})"
        )


@main.command("stats")
@click.pass_context
def stats(ctx):
    """Show aggregate statistics across all quests and missions."""
    from lore.db import get_aggregate_stats

    project_root = ctx.obj["project_root"]
    data = get_aggregate_stats(project_root)

    if ctx.obj.get("json", False):
        click.echo(json.dumps(data))
        return

    q = data["quests"]
    click.echo("Quests:")
    click.echo(f"  open: {q['open']}")
    click.echo(f"  in_progress: {q['in_progress']}")
    click.echo(f"  closed: {q['closed']}")
    click.echo("")
    m = data["missions"]
    click.echo("Missions:")
    click.echo(f"  open: {m['open']}")
    click.echo(f"  in_progress: {m['in_progress']}")
    click.echo(f"  blocked: {m['blocked']}")
    click.echo(f"  closed: {m['closed']}")


@main.command("oracle")
@click.option(
    "--json", "json_flag", is_flag=True, hidden=True, help="Ignored for oracle."
)
@click.pass_context
def oracle(ctx, json_flag):
    """Generate human-readable markdown reports in .lore/reports/. Produces one file per quest and mission. Wipes and recreates the reports directory on every run — do not store custom files there. Intended for human stakeholders, not for agent consumption. JSON output is not supported for this command."""
    from lore.oracle import generate_reports

    project_root = ctx.obj["project_root"]
    generate_reports(project_root)
    click.echo("Reports generated in .lore/reports/")


@main.command()
@click.pass_context
def init(ctx):
    """Initialize a Lore project in the current directory."""
    from lore.init import run_init

    messages = run_init()
    click.echo("Initialized Lore project:")
    for msg in messages:
        click.echo(msg)


@main.group()
@click.pass_context
def new(ctx):
    """Create quests and missions.

    A Quest is a body of work (feature, bug fix, refactor). A Mission is a
    single executable task within a quest. Missions without a quest (-q) are
    standalone.

    Example sequence: lore new quest "My feature" then
    lore new mission -q <id> "Task one" to build a plan."""
    pass


@new.command("quest")
@click.argument("title")
@click.option("-d", "--description", default="", help="Quest description.")
@click.option("-p", "--priority", type=int, default=2, help="Priority 0-4.")
@click.option(
    "--auto-close",
    "auto_close",
    is_flag=True,
    default=False,
    help="Enable auto-close when all missions done.",
)
@click.option(
    "--no-auto-close", "no_auto_close", is_flag=True, default=False, hidden=True
)
@click.pass_context
def new_quest(ctx, title, description, priority, auto_close, no_auto_close):
    """Create a new quest."""
    err = validators.validate_priority(priority)
    if err:
        raise click.ClickException(err)

    from lore.db import create_quest

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    ac_value = 1 if auto_close else 0
    try:
        quest_id = create_quest(
            project_root, title, description, priority, auto_close=ac_value
        )
    except ValueError as e:
        raise click.ClickException(str(e))
    except RuntimeError:
        msg = "ID generation failed: collision after maximum length. Please retry."
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps({"id": quest_id}))
        return

    click.echo(f"Created quest {quest_id}")


@new.command("mission")
@click.argument("title")
@click.option("-q", "--quest", "quest_id", default=None, help="Parent quest ID.")
@click.option("-d", "--description", default="", help="Mission description.")
@click.option("-p", "--priority", type=int, default=2, help="Priority 0-4.")
@click.option("-k", "--knight", default=None, help="Knight filename.")
@click.option(
    "-T",
    "--type",
    "mission_type",
    type=str,
    default=None,
    help="Mission type.",
)
@click.pass_context
def new_mission(ctx, title, quest_id, description, priority, knight, mission_type):
    """Create a new mission."""
    json_mode = ctx.obj.get("json", False)

    err = validators.validate_priority(priority)
    if err:
        raise click.ClickException(err)

    from lore.db import create_mission, get_connection

    project_root = ctx.obj["project_root"]

    # Infer quest if not specified and exactly one non-closed quest exists
    if quest_id is None:
        conn = get_connection(project_root)
        try:
            cursor = conn.execute("SELECT id FROM quests WHERE status != 'closed'")
            active_quests = cursor.fetchall()
            if len(active_quests) == 1:
                quest_id = active_quests[0]["id"]
        finally:
            conn.close()

    try:
        mission_id = create_mission(
            project_root,
            title,
            quest_id=quest_id,
            description=description,
            priority=priority,
            knight=knight,
            mission_type=mission_type,
        )
    except RuntimeError:
        msg = "ID generation failed: collision after maximum length. Please retry."
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return
    except ValueError as e:
        if json_mode:
            click.echo(json.dumps({"error": str(e)}), err=True)
            ctx.exit(1)
            return
        click.echo(str(e), err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps({"id": mission_id}))
        return

    click.echo(f"Created mission {mission_id}")


@main.command("claim")
@click.argument("mission_ids", nargs=-1, required=True)
@click.pass_context
def claim(ctx, mission_ids):
    """Claim one or more missions (open -> in_progress)."""
    from lore.db import claim_mission

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    if json_mode:
        updated = []
        quest_status_changed = []
        errors = []

        for mid in mission_ids:
            mid_err = validators.validate_mission_id(mid)
            if mid_err:
                errors.append(mid_err)
                continue
            result = claim_mission(project_root, mid)
            if not result["ok"]:
                errors.append(result["error"])
            else:
                updated.append(mid)
                if result["quest_status_changed"]:
                    quest_status_changed.append({"id": result["quest_id"], "status": result["quest_status"]})

        click.echo(
            json.dumps(
                {
                    "updated": updated,
                    "quest_status_changed": quest_status_changed,
                    "errors": errors,
                }
            )
        )
        if errors:
            ctx.exit(1)
        return

    any_failed = False

    for mid in mission_ids:
        mid_err = validators.validate_mission_id(mid)
        if mid_err:
            click.echo(mid_err, err=True)
            any_failed = True
            continue
        result = claim_mission(project_root, mid)

        if not result["ok"]:
            click.echo(result["error"], err=True)
            any_failed = True
        else:
            click.echo(f"{mid}: {result['status']}")

    if any_failed:
        ctx.exit(1)


@main.command("done")
@click.argument("entity_ids", nargs=-1, required=True)
@click.pass_context
def done(ctx, entity_ids):
    """Close one or more missions or quests.

    For missions: transitions in_progress -> closed and unblocks any dependents.

    For quests: use only if auto_close is disabled; quests with auto_close
    enabled close automatically when all missions are done.
    """
    from lore.db import close_mission, close_quest

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    def _is_quest_id(eid):
        return eid.startswith("q-") and "/" not in eid

    if json_mode:
        updated = []
        quest_closed = []
        errors = []
        for eid in entity_ids:
            if _is_quest_id(eid):
                result = close_quest(project_root, eid)
                if not result["ok"]:
                    errors.append(result["error"])
                else:
                    updated.append(eid)
            else:
                eid_err = validators.validate_mission_id(eid)
                if eid_err:
                    errors.append(eid_err)
                    continue
                result = close_mission(project_root, eid)
                if not result["ok"]:
                    errors.append(result["error"])
                else:
                    updated.append(eid)
                    if result["quest_closed"]:
                        quest_closed.append(result["quest_id"])
        click.echo(
            json.dumps(
                {
                    "updated": updated,
                    "quest_closed": quest_closed,
                    "errors": errors,
                }
            )
        )
        if errors:
            ctx.exit(1)
        return

    any_failed = False

    for eid in entity_ids:
        if _is_quest_id(eid):
            result = close_quest(project_root, eid)
            if not result["ok"]:
                click.echo(result["error"], err=True)
                any_failed = True
            else:
                if result.get("already_closed"):
                    click.echo(f"{eid}: already closed")
                else:
                    click.echo(f"{eid}: closed (closed_at: {result['closed_at']})")
        else:
            eid_err = validators.validate_mission_id(eid)
            if eid_err:
                click.echo(eid_err, err=True)
                any_failed = True
                continue
            result = close_mission(project_root, eid)

            if not result["ok"]:
                click.echo(result["error"], err=True)
                any_failed = True
            else:
                if result["quest_closed"]:
                    click.echo(f"{eid}: closed (quest auto-closed)")
                else:
                    click.echo(f"{eid}: {result['status']}")

    if any_failed:
        ctx.exit(1)


@main.command("block")
@click.argument("mission_id")
@click.argument("reason")
@click.pass_context
def block(ctx, mission_id, reason):
    """Mark a mission as blocked with a reason."""
    from lore.db import block_mission

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    if not _validate_mission_id(mission_id, ctx):
        return

    result = block_mission(project_root, mission_id, reason)

    if json_mode:
        if not result["ok"]:
            click.echo(json.dumps({"error": result["error"]}), err=True)
            ctx.exit(1)
        else:
            click.echo(
                json.dumps(
                    {
                        "id": mission_id,
                        "status": "blocked",
                        "block_reason": reason,
                    }
                )
            )
        return

    if not result["ok"]:
        click.echo(result["error"], err=True)
        ctx.exit(1)
    else:
        click.echo(f"{mission_id}: {result['status']}")


@main.command("unblock")
@click.argument("mission_id")
@click.pass_context
def unblock(ctx, mission_id):
    """Unblock a blocked mission, returning it to open status."""
    from lore.db import unblock_mission

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    if not _validate_mission_id(mission_id, ctx):
        return

    result = unblock_mission(project_root, mission_id)

    if json_mode:
        if not result["ok"]:
            click.echo(json.dumps({"error": result["error"]}), err=True)
            ctx.exit(1)
        else:
            click.echo(
                json.dumps(
                    {
                        "id": mission_id,
                        "status": "open",
                    }
                )
            )
        return

    if not result["ok"]:
        click.echo(result["error"], err=True)
        ctx.exit(1)
    else:
        click.echo(f"{mission_id}: {result['status']}")


@main.command("ready")
@click.argument("count", type=int, default=1, required=False)
@click.pass_context
def ready(ctx, count):
    """Show the highest priority unblocked mission(s), sorted by priority.

    Blocked and closed missions are excluded.

    Optional COUNT returns multiple missions at once: 'lore ready 5'."""
    from lore.priority import get_ready_missions

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    missions = get_ready_missions(project_root, count=count)

    if json_mode:
        data = {
            "missions": [
                {
                    "id": m["id"],
                    "quest_id": m["quest_id"],
                    "title": m["title"],
                    "status": m["status"],
                    "priority": m["priority"],
                    "mission_type": m["mission_type"],
                    "knight": m["knight"],
                    "created_at": m["created_at"],
                }
                for m in missions
            ]
        }
        click.echo(json.dumps(data))
        return

    if not missions:
        click.echo("No missions are ready.")
        return

    for m in missions:
        knight_str = f"  [{m['knight']}]" if m["knight"] else ""
        type_str = f"  [{m['mission_type']}]" if m["mission_type"] else ""
        click.echo(
            f"  {m['id']}  P{m['priority']}  [{m['status']}]{type_str}  {m['title']}{knight_str}"
        )


@main.command("needs")
@click.argument("pairs", nargs=-1, required=True)
@click.pass_context
def needs(ctx, pairs):
    """Declare dependencies between missions using colon-pair syntax."""
    from lore.db import add_dependency

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    if json_mode:
        created = []
        existing = []
        errors = []
        for pair in pairs:
            parts = pair.split(":")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                errors.append(
                    f'Invalid dependency pair format: "{pair}". Expected "from:to".'
                )
                continue
            from_id, to_id = parts[0], parts[1]
            result = add_dependency(project_root, from_id, to_id)
            if not result["ok"]:
                errors.append(result["error"])
            elif result["duplicate"]:
                existing.append({"from": from_id, "to": to_id})
            else:
                created.append({"from": from_id, "to": to_id})
        click.echo(
            json.dumps(
                {
                    "created": created,
                    "existing": existing,
                    "errors": errors,
                }
            )
        )
        if errors:
            ctx.exit(1)
        return

    any_failed = False

    for pair in pairs:
        # Validate pair format: exactly one colon, non-empty sides
        parts = pair.split(":")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            click.echo(
                f'Invalid dependency pair format: "{pair}". Expected "from:to".',
                err=True,
            )
            any_failed = True
            continue

        from_id, to_id = parts[0], parts[1]
        result = add_dependency(project_root, from_id, to_id)

        if not result["ok"]:
            click.echo(result["error"], err=True)
            any_failed = True
        elif result["duplicate"]:
            click.echo(f"Dependency already exists: {from_id} -> {to_id}")
        else:
            click.echo(f"Dependency created: {from_id} -> {to_id}")
            if result["closed_target"]:
                click.echo(
                    f"Note: dependency target {to_id} is already closed. Mission {from_id} is not blocked."
                )

    if any_failed:
        ctx.exit(1)


@main.command("unneed")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.argument("pairs", nargs=-1, required=True)
@click.pass_context
def unneed(ctx, json_flag, pairs):
    """Remove dependencies between missions using colon-pair syntax."""
    from lore.db import remove_dependency

    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)

    removed_list = []
    not_found_list = []
    errors_list = []
    any_error = False

    for pair in pairs:
        parts = pair.split(":")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            errors_list.append(f'Invalid pair format: "{pair}"')
            any_error = True
            if not json_mode:
                click.echo(f'Invalid pair format: "{pair}"', err=True)
            continue

        from_id, to_id = parts

        # Validate mission ID format
        from_err = validators.validate_mission_id(from_id)
        to_err = validators.validate_mission_id(to_id)
        if from_err or to_err:
            msg = from_err if from_err else to_err
            errors_list.append(msg)
            any_error = True
            if not json_mode:
                click.echo(msg, err=True)
            continue

        result = remove_dependency(project_root, from_id, to_id)

        if result.get("removed", False):
            removed_list.append({"from": from_id, "to": to_id})
            if not json_mode:
                click.echo(f"Dependency removed: {from_id} -> {to_id}")
        else:
            not_found_list.append({"from": from_id, "to": to_id})
            if not json_mode:
                click.echo(f"Warning: no dependency found: {from_id} -> {to_id}")

    if json_mode:
        click.echo(
            json.dumps(
                {
                    "removed": removed_list,
                    "not_found": not_found_list,
                    "errors": errors_list,
                }
            )
        )

    if any_error:
        ctx.exit(1)


@main.command("list")
@click.option("--all", "show_all", is_flag=True, help="Include closed quests.")
@click.pass_context
def list_quests(ctx, show_all):
    """List quests."""
    from lore.db import list_quests as db_list_quests

    project_root = ctx.obj["project_root"]
    quests = db_list_quests(project_root, include_closed=show_all)

    if ctx.obj.get("json", False):
        data = {
            "quests": [
                {
                    "id": q["id"],
                    "title": q["title"],
                    "status": q["status"],
                    "priority": q["priority"],
                    "created_at": q["created_at"],
                }
                for q in quests
            ]
        }
        click.echo(json.dumps(data))
        return

    if not quests:
        click.echo("No quests found.")
        return

    for q in quests:
        click.echo(f"  {q['id']}  P{q['priority']}  [{q['status']}]  {q['title']}")


@main.command("missions")
@click.argument("quest_id", required=False, default=None)
@click.option("--all", "show_all", is_flag=True, help="Include all statuses.")
@click.pass_context
def missions(ctx, quest_id, show_all):
    """List missions across all quests, or scoped to one quest.

    Missions have four statuses: open, in_progress, blocked, closed.

    The mission_type field is free-form. Lore does not interpret it.

    Use 'lore ready' to find the next mission to dispatch.
    """
    from lore.db import get_deleted_at, get_quest, list_missions

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    # Validate quest exists if specified
    if quest_id is not None:
        quest = get_quest(project_root, quest_id)
        if quest is None:
            if json_mode:
                click.echo(
                    json.dumps({"error": f'Quest "{quest_id}" not found'}), err=True
                )
                ctx.exit(1)
                return
            click.echo(f'Quest "{quest_id}" not found', err=True)
            ctx.exit(1)
            return

    grouped = list_missions(project_root, quest_id=quest_id, include_closed=show_all)

    if json_mode:
        flat = []
        for qid, mission_list in grouped.items():
            for m in mission_list:
                flat.append(
                    {
                        "id": m["id"],
                        "quest_id": m["quest_id"],
                        "title": m["title"],
                        "status": m["status"],
                        "priority": m["priority"],
                        "mission_type": m["mission_type"],
                        "knight": m["knight"],
                        "created_at": m["created_at"],
                    }
                )
        click.echo(json.dumps({"missions": flat}))
        return

    if not grouped:
        click.echo("No missions found.")
        return

    # Display quest-bound missions first, then standalone
    quest_ids = sorted([k for k in grouped if k is not None])
    has_standalone = None in grouped

    def _format_mission_line(m):
        knight_str = f"  [{m['knight']}]" if m["knight"] else ""
        type_str = f"  [{m['mission_type']}]" if m["mission_type"] else ""
        return f"  {m['id']}  P{m['priority']}  [{m['status']}]{type_str}  {m['title']}{knight_str}"

    for qid in quest_ids:
        # Fetch quest title for display
        quest = get_quest(project_root, qid)
        if quest:
            quest_title = quest["title"]
            quest_deleted_annotation = ""
        else:
            # Quest may be soft-deleted
            deleted_at = get_deleted_at(project_root, qid)
            quest_title = qid
            quest_deleted_annotation = " (quest deleted)" if deleted_at else ""
        click.echo(f"Quest: {quest_title} ({qid}){quest_deleted_annotation}")
        for m in grouped[qid]:
            click.echo(_format_mission_line(m))
        click.echo("")

    if has_standalone:
        click.echo("Standalone:")
        for m in grouped[None]:
            click.echo(_format_mission_line(m))


@main.group()
@click.pass_context
def knight(ctx):
    """Manage knight personas — reusable markdown files that tell a worker agent how to approach work (style, constraints, authority). Assign a knight to a mission with 'lore new mission -k <name>.md'. When a worker runs 'lore show <mission-id>', the knight's content is included in the output. Knights encode the 'how'; mission descriptions encode the 'what'."""
    pass


@knight.command("list")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def knight_list(ctx, json_flag):
    """List available knights."""
    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)
    knights_dir = paths.knights_dir(project_root)

    records = knight_module.list_knights(knights_dir)

    if json_mode:
        filtered = [
            {"id": r["id"], "group": r["group"], "title": r["title"], "summary": r["summary"]}
            for r in records
        ]
        click.echo(json.dumps({"knights": filtered}))
        return

    if not records:
        click.echo("No knights found.")
        return

    rows = [[r["id"], r["group"], r["title"], r["summary"]] for r in records]
    for line in _format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows):
        click.echo(line)


@knight.command("show")
@click.argument("name")
@click.pass_context
def knight_show(ctx, name):
    """Show the contents of a knight file."""
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    knights_dir = paths.knights_dir(project_root)

    try:
        knight_path = knight_module.find_knight(knights_dir, name)
    except ValueError:
        knight_path = None

    if knight_path is None:
        if json_mode:
            click.echo(
                json.dumps(
                    {"error": f'Knight "{name}" not found in .lore/knights/'}
                ),
                err=True,
            )
            ctx.exit(1)
            return
        click.echo(f'Knight "{name}" not found in .lore/knights/', err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(
            json.dumps(
                {
                    "name": name,
                    "filename": f"{name}.md",
                    "contents": knight_path.read_text(),
                }
            )
        )
        return

    click.echo(knight_path.read_text())


@knight.command("new", context_settings={"ignore_unknown_options": True})
@click.argument("name")
@click.option(
    "--from", "-f", "from_file", default=None, help="Source file for knight content."
)
@click.pass_context
def knight_new(ctx, name, from_file):
    """Create a new knight."""
    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    knights_dir = paths.knights_dir(project_root)
    knight_path = knights_dir / f"{name}.md"

    # Check for duplicate (flat path or any subdirectory)
    if knight_path.exists() or (
        knights_dir.exists() and list(knights_dir.rglob(f"{name}.md"))
    ):
        msg = f'Knight "{name}" already exists.'
        if json_mode:
            click.echo(json.dumps({"error": msg}))
        else:
            click.echo(msg)
        ctx.exit(1)
        return

    if from_file is not None and from_file != "-":
        source = Path(from_file)
        if not source.exists():
            msg = f"File not found: {from_file}"
            if json_mode:
                click.echo(json.dumps({"error": msg}))
            else:
                click.echo(msg)
            ctx.exit(1)
            return
        content = source.read_text()
    else:
        content = click.get_text_stream("stdin").read()
        if not content.strip():
            msg = "No content provided on stdin."
            if json_mode:
                click.echo(json.dumps({"error": msg}))
            else:
                click.echo(msg)
            ctx.exit(1)
            return

    knights_dir.mkdir(parents=True, exist_ok=True)
    knight_path.write_text(content)

    if json_mode:
        click.echo(json.dumps({"name": name, "filename": f"{name}.md"}))
        return
    click.echo(f"Created knight {name}")


@knight.command("edit")
@click.argument("name")
@click.option(
    "--from", "-f", "from_file", default=None, help="Source file for knight content."
)
@click.pass_context
def knight_edit(ctx, name, from_file):
    """Edit an existing knight."""
    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    knight_path = paths.knights_dir(project_root) / f"{name}.md"

    if not knight_path.exists():
        msg = f'Knight "{name}" not found.'
        if json_mode:
            click.echo(json.dumps({"error": msg}))
        else:
            click.echo(msg)
        ctx.exit(1)
        return

    if from_file is not None and from_file != "-":
        source = Path(from_file)
        if not source.exists():
            msg = f"File not found: {from_file}"
            if json_mode:
                click.echo(json.dumps({"error": msg}))
            else:
                click.echo(msg)
            ctx.exit(1)
            return
        content = source.read_text()
    else:
        content = click.get_text_stream("stdin").read()
        if not content.strip():
            msg = "No content provided on stdin."
            if json_mode:
                click.echo(json.dumps({"error": msg}))
            else:
                click.echo(msg)
            ctx.exit(1)
            return

    knight_path.write_text(content)

    if json_mode:
        click.echo(json.dumps({"name": name, "filename": f"{name}.md"}))
        return
    click.echo(f"Updated knight {name}")


@knight.command("delete")
@click.argument("name")
@click.pass_context
def knight_delete(ctx, name):
    """Delete a knight."""
    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    knight_path = paths.knights_dir(project_root) / f"{name}.md"

    if not knight_path.exists():
        msg = f'Knight "{name}" not found in .lore/knights/'
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    knight_path.rename(knight_path.with_suffix(".md.deleted"))

    if json_mode:
        click.echo(json.dumps({"name": name, "deleted": True}))
        return
    click.echo(f"Deleted knight {name}")


@main.group()
@click.pass_context
def doctrine(ctx):
    """Manage doctrine templates — YAML files that describe the step sequence and suggested knights for a standard body of work (e.g. a feature or bugfix workflow). Doctrines have no execution engine; an orchestrator reads them with 'lore doctrine show <name>' and translates the steps into quests and missions as guidance. Doctrines are passive — they do not trigger actions."""
    pass


@doctrine.command("list")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def doctrine_list(ctx, json_flag):
    """List available doctrines."""
    from lore.doctrine import list_doctrines

    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)
    doctrines_dir = paths.doctrines_dir(project_root)

    doctrines = list_doctrines(doctrines_dir)

    if json_mode:
        data = {
            "doctrines": [
                {
                    "id": d.get("id", d["name"]),
                    "group": d.get("group", ""),
                    "title": d.get("title", d["name"]),
                    "summary": d.get("summary", ""),
                    "valid": d["valid"],
                }
                for d in doctrines
            ]
        }
        click.echo(json.dumps(data))
        return

    if not doctrines:
        click.echo("No doctrines found.")
        return

    rows = [
        [
            d.get("id", d["name"]),
            d.get("group", ""),
            d.get("title", d["name"]),
            (d.get("summary", d.get("description", "")) + (" [INVALID]" if not d.get("valid", True) else "")),
        ]
        for d in doctrines
    ]
    for line in _format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows):
        click.echo(line)


@doctrine.command("show")
@click.argument("name")
@click.pass_context
def doctrine_show(ctx, name):
    """Show and validate a doctrine."""
    from lore.doctrine import load_doctrine, DoctrineError

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    doctrines_dir = paths.doctrines_dir(project_root)

    if "/" in name or "\\" in name:
        if json_mode:
            click.echo(
                json.dumps(
                    {"error": f'Doctrine "{name}" not found in .lore/doctrines/'}
                ),
                err=True,
            )
            ctx.exit(1)
            return
        click.echo(f'Doctrine "{name}" not found in .lore/doctrines/', err=True)
        ctx.exit(1)
        return

    doctrine_path = doctrines_dir / f"{name}.yaml"

    if not doctrine_path.exists():
        # Search in subdirectories (e.g. default/)
        matches = (
            list(doctrines_dir.rglob(f"{name}.yaml")) if doctrines_dir.exists() else []
        )
        if matches:
            doctrine_path = matches[0]
        else:
            if json_mode:
                click.echo(
                    json.dumps(
                        {"error": f'Doctrine "{name}" not found in .lore/doctrines/'}
                    ),
                    err=True,
                )
                ctx.exit(1)
                return
            click.echo(f'Doctrine "{name}" not found in .lore/doctrines/', err=True)
            ctx.exit(1)
            return

    try:
        doctrine = load_doctrine(doctrine_path)
    except DoctrineError as e:
        if json_mode:
            click.echo(json.dumps({"error": str(e)}), err=True)
            ctx.exit(1)
            return
        click.echo(str(e), err=True)
        ctx.exit(1)
        return

    if json_mode:
        data = {
            "name": doctrine["name"],
            "description": doctrine["description"],
            "steps": doctrine["steps"],
        }
        click.echo(json.dumps(data))
        return

    click.echo(f"Doctrine: {doctrine['name']}")
    click.echo(f"Description: {doctrine['description']}")
    click.echo("")
    click.echo("Steps:")
    for step in doctrine["steps"]:
        click.echo(f"  [{step['id']}] {step['title']}")
        click.echo(f"    Priority: {step['priority']}")
        if step["type"]:
            click.echo(f"    Type: {step['type']}")
        if step["needs"]:
            click.echo(f"    Needs: {', '.join(step['needs'])}")
        if step["knight"]:
            click.echo(f"    Knight: {step['knight']}")
        if step["notes"]:
            click.echo(f"    Notes: {step['notes']}")


@doctrine.command("new", context_settings={"ignore_unknown_options": True})
@click.argument("name")
@click.option("--from", "-f", "from_file", default=None, help="Source file.")
@click.pass_context
def doctrine_new(ctx, name, from_file):
    """Create a new doctrine."""
    import sys
    from lore.doctrine import validate_doctrine_content, scaffold_doctrine, DoctrineError

    json_mode = ctx.obj.get("json", False)

    if not _validate_name(name, ctx):
        return

    project_root = ctx.obj["project_root"]
    doctrines_dir = paths.doctrines_dir(project_root)
    doctrine_path = doctrines_dir / f"{name}.yaml"

    # Check duplicate (flat path or any subdirectory)
    if doctrine_path.exists() or (
        doctrines_dir.exists() and list(doctrines_dir.rglob(f"{name}.yaml"))
    ):
        msg = f"Error: doctrine '{name}' already exists. Use 'lore doctrine edit {name}' to modify it."
        if json_mode:
            click.echo(json.dumps({"error": msg}))
        else:
            click.echo(msg)
        ctx.exit(1)
        return

    # Read content
    if from_file is not None and from_file != "-":
        source = Path(from_file)
        if not source.exists():
            msg = f"File not found: {from_file}"
            if json_mode:
                click.echo(json.dumps({"error": msg}))
            else:
                click.echo(msg)
            ctx.exit(1)
            return
        content = source.read_text()
        # Validate content (strict: requires name, description, steps)
        try:
            validate_doctrine_content(content, name)
        except DoctrineError as e:
            msg = str(e)
            if json_mode:
                click.echo(json.dumps({"error": msg}))
            else:
                click.echo(msg)
            ctx.exit(1)
            return
    else:
        # Scaffold path: TTY detected, or stdin is empty/whitespace
        content = click.get_text_stream("stdin").read() if not sys.stdin.isatty() else ""
        if not content or not content.strip():
            content = scaffold_doctrine(name)
            doctrines_dir.mkdir(parents=True, exist_ok=True)
            doctrine_path.write_text(content)
            if json_mode:
                click.echo(json.dumps({"name": name, "filename": f"{name}.yaml"}))
                return
            click.echo(f"Created doctrine {name}")
            return
        # Light validation for stdin: valid YAML + id-if-present must match
        import yaml as _yaml
        try:
            data = _yaml.safe_load(content)
        except _yaml.YAMLError as e:
            msg = str(e)
            if json_mode:
                click.echo(json.dumps({"error": msg}))
            else:
                click.echo(msg)
            ctx.exit(1)
            return
        if not isinstance(data, dict):
            msg = "Doctrine must be a YAML mapping"
            if json_mode:
                click.echo(json.dumps({"error": msg}))
            else:
                click.echo(msg)
            ctx.exit(1)
            return
        if "id" in data and str(data["id"]) != name:
            msg = f'Doctrine id "{data["id"]}" does not match command argument "{name}"'
            if json_mode:
                click.echo(json.dumps({"error": msg}))
            else:
                click.echo(msg)
            ctx.exit(1)
            return

    doctrines_dir.mkdir(parents=True, exist_ok=True)
    doctrine_path.write_text(content)

    if json_mode:
        click.echo(json.dumps({"name": name, "filename": f"{name}.yaml"}))
        return
    click.echo(f"Created doctrine {name}")


@doctrine.command("edit")
@click.argument("name")
@click.option("--from", "-f", "from_file", default=None, help="Source file.")
@click.pass_context
def doctrine_edit(ctx, name, from_file):
    """Edit an existing doctrine."""
    from lore.doctrine import validate_doctrine_content, DoctrineError

    json_mode = ctx.obj.get("json", False)

    if not _validate_name(name, ctx):
        return

    project_root = ctx.obj["project_root"]
    doctrine_path = paths.doctrines_dir(project_root) / f"{name}.yaml"

    # Check existence
    if not doctrine_path.exists():
        msg = f'Doctrine "{name}" not found.'
        if json_mode:
            click.echo(json.dumps({"error": msg}))
        else:
            click.echo(msg)
        ctx.exit(1)
        return

    # Read content
    if from_file is not None and from_file != "-":
        source = Path(from_file)
        if not source.exists():
            msg = f"File not found: {from_file}"
            if json_mode:
                click.echo(json.dumps({"error": msg}))
            else:
                click.echo(msg)
            ctx.exit(1)
            return
        content = source.read_text()
    else:
        content = click.get_text_stream("stdin").read()
        if not content or not content.strip():
            msg = "No content provided on stdin."
            if json_mode:
                click.echo(json.dumps({"error": msg}))
            else:
                click.echo(msg)
            ctx.exit(1)
            return

    # Validate content
    try:
        validate_doctrine_content(content, name)
    except DoctrineError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}))
        else:
            click.echo(msg)
        ctx.exit(1)
        return

    # Preserve existing frontmatter fields (id, title, summary) that the new
    # content may have omitted.
    try:
        existing_raw = yaml.safe_load(doctrine_path.read_text()) or {}
    except Exception:
        existing_raw = {}
    new_data = yaml.safe_load(content) or {}
    for field in ("id", "title", "summary"):
        if field in existing_raw and field not in new_data:
            new_data[field] = existing_raw[field]
    merged_content = yaml.dump(new_data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    doctrine_path.write_text(merged_content)

    if json_mode:
        click.echo(json.dumps({"name": name, "filename": f"{name}.yaml"}))
        return
    click.echo(f"Updated doctrine {name}")


@doctrine.command("delete")
@click.argument("name")
@click.pass_context
def doctrine_delete(ctx, name):
    """Delete a doctrine."""
    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    doctrine_path = paths.doctrines_dir(project_root) / f"{name}.yaml"

    if not doctrine_path.exists():
        msg = f'Doctrine "{name}" not found'
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    doctrine_path.rename(doctrine_path.with_suffix(".yaml.deleted"))

    if json_mode:
        click.echo(json.dumps({"name": name, "deleted": True}))
        return
    click.echo(f"Deleted doctrine {name}")


@main.command("edit")
@click.argument("entity_id")
@click.option("-t", "--title", default=None, help="New title.")
@click.option("-d", "--description", default=None, help="New description.")
@click.option("-p", "--priority", type=int, default=None, help="New priority 0-4.")
@click.option("-k", "--knight", default=None, help="Assign knight.")
@click.option(
    "--no-knight", is_flag=True, default=False, help="Remove knight assignment."
)
@click.option(
    "--auto-close", "auto_close", is_flag=True, default=False, help="Enable auto-close."
)
@click.option(
    "--no-auto-close",
    "no_auto_close",
    is_flag=True,
    default=False,
    help="Disable auto-close.",
)
@click.option(
    "-T",
    "--type",
    "mission_type",
    type=str,
    default=None,
    help="Mission type.",
)
@click.pass_context
def edit(
    ctx,
    entity_id,
    title,
    description,
    priority,
    knight,
    no_knight,
    auto_close,
    no_auto_close,
    mission_type,
):
    """Edit a quest or mission."""
    # Mutual exclusion check for --knight and --no-knight
    if knight is not None and no_knight:
        raise click.UsageError("--knight and --no-knight are mutually exclusive.")

    if auto_close and no_auto_close:
        raise click.UsageError(
            "--auto-close and --no-auto-close are mutually exclusive."
        )

    has_auto_close_flag = auto_close or no_auto_close

    if (
        title is None
        and description is None
        and priority is None
        and knight is None
        and not no_knight
        and not has_auto_close_flag
        and mission_type is None
    ):
        raise click.UsageError(
            "At least one of --title, --description, --priority, --knight, --no-knight, --auto-close, --no-auto-close, or --type is required."
        )

    if not _validate_entity_id(entity_id, ctx):
        return

    if entity_id.startswith("q-") and "/" not in entity_id:
        ac_value = None
        if auto_close:
            ac_value = 1
        elif no_auto_close:
            ac_value = 0
        _edit_quest(ctx, entity_id, title, description, priority, auto_close=ac_value)
    else:
        _edit_mission(
            ctx,
            entity_id,
            title,
            description,
            priority,
            knight,
            no_knight,
            mission_type=mission_type,
        )


def _edit_quest(ctx, quest_id, title, description, priority, auto_close=None):
    """Edit a quest's fields."""
    from lore.db import edit_quest, get_quest, get_missions_for_quest

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    result = edit_quest(
        project_root,
        quest_id,
        title=title,
        description=description,
        priority=priority,
        auto_close=auto_close,
    )

    if not result["ok"]:
        if json_mode:
            err_data = {"error": result["error"]}
            if "deleted_at" in result:
                err_data["deleted_at"] = result["deleted_at"]
            click.echo(json.dumps(err_data), err=True)
        else:
            click.echo(result["error"], err=True)
        ctx.exit(1)
        return

    if json_mode:
        quest = get_quest(project_root, quest_id)
        missions = get_missions_for_quest(project_root, quest_id)
        data = {
            "id": quest["id"],
            "title": quest["title"],
            "description": quest["description"],
            "status": quest["status"],
            "priority": quest["priority"],
            "created_at": quest["created_at"],
            "updated_at": quest["updated_at"],
            "closed_at": quest["closed_at"],
            "auto_close": bool(quest["auto_close"]),
            "missions": [
                {
                    "id": m["id"],
                    "title": m["title"],
                    "status": m["status"],
                    "priority": m["priority"],
                    "mission_type": m["mission_type"],
                    "knight": m["knight"],
                }
                for m in missions
            ],
        }
        click.echo(json.dumps(data))
        return

    click.echo(f"Updated quest {quest_id}")


def _edit_mission(
    ctx, mission_id, title, description, priority, knight, no_knight, mission_type=None
):
    """Edit a mission's fields."""
    from lore.db import (
        edit_mission,
        get_mission,
        get_mission_depends_on,
        get_mission_blocks,
    )

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    result = edit_mission(
        project_root,
        mission_id,
        title=title,
        description=description,
        priority=priority,
        knight=knight,
        remove_knight=no_knight,
        mission_type=mission_type,
    )

    if not result["ok"]:
        if json_mode:
            err_data = {"error": result["error"]}
            if "deleted_at" in result:
                err_data["deleted_at"] = result["deleted_at"]
            click.echo(json.dumps(err_data), err=True)
        else:
            click.echo(result["error"], err=True)
        ctx.exit(1)
        return

    if json_mode:
        mission = get_mission(project_root, mission_id)
        depends_on = get_mission_depends_on(project_root, mission_id)
        blocks = get_mission_blocks(project_root, mission_id)
        data = {
            "id": mission["id"],
            "quest_id": mission["quest_id"],
            "title": mission["title"],
            "description": mission["description"],
            "status": mission["status"],
            "priority": mission["priority"],
            "knight": mission["knight"],
            "mission_type": mission["mission_type"],
            "block_reason": mission["block_reason"],
            "created_at": mission["created_at"],
            "updated_at": mission["updated_at"],
            "closed_at": mission["closed_at"],
            "dependencies": {
                "needs": depends_on,
                "blocks": blocks,
            },
        }
        click.echo(json.dumps(data))
        return

    click.echo(f"Updated mission {mission_id}")


@main.command("delete")
@click.argument("entity_id")
@click.option(
    "--cascade",
    is_flag=True,
    default=False,
    help="Also delete all missions and dependencies.",
)
@click.pass_context
def delete(ctx, entity_id, cascade):
    """Delete a quest or mission."""
    json_mode = ctx.obj.get("json", False)

    if entity_id.startswith("q-") and "/" not in entity_id:
        # Use loose validation for delete (allows lookup of any quest-like ID)
        if validators.validate_quest_id_loose(entity_id) is not None:
            msg = f'Invalid quest ID format: "{entity_id}"'
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return
        _delete_quest(ctx, entity_id, cascade)
    elif "m-" in entity_id:
        if not _validate_mission_id(entity_id, ctx):
            return
        _delete_mission(ctx, entity_id)
    else:
        msg = f'Invalid ID format: "{entity_id}"'
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)


def _delete_quest(ctx, quest_id, cascade):
    """Soft-delete a quest."""
    from lore.db import delete_quest

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    result = delete_quest(project_root, quest_id, cascade=cascade)

    if not result["ok"]:
        if json_mode:
            click.echo(json.dumps({"error": result["error"]}), err=True)
        else:
            click.echo(result["error"], err=True)
        ctx.exit(1)
        return

    if result["already_deleted"]:
        if json_mode:
            click.echo(
                json.dumps(
                    {
                        "id": quest_id,
                        "deleted_at": result["deleted_at"],
                        "warning": "Quest already deleted",
                    }
                )
            )
        else:
            click.echo(
                f"Warning: Quest {quest_id} was already deleted on {result['deleted_at']}"
            )
        return

    if json_mode:
        data = {"id": quest_id, "deleted_at": result["deleted_at"]}
        if cascade:
            data["cascade"] = result["cascade"]
        click.echo(json.dumps(data))
        return

    click.echo(f"Deleted quest {quest_id}")
    if cascade and result["cascade"]:
        click.echo("Cascade deleted:")
        for mid in result["cascade"]:
            click.echo(f"  {mid}")


def _delete_mission(ctx, mission_id):
    """Soft-delete a mission."""
    from lore.db import delete_mission

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    result = delete_mission(project_root, mission_id)

    if not result["ok"]:
        if json_mode:
            click.echo(json.dumps({"error": result["error"]}), err=True)
        else:
            click.echo(result["error"], err=True)
        ctx.exit(1)
        return

    if result["already_deleted"]:
        if json_mode:
            click.echo(
                json.dumps(
                    {
                        "id": mission_id,
                        "deleted_at": result["deleted_at"],
                        "warning": "Mission already deleted",
                    }
                )
            )
        else:
            click.echo(
                f"Warning: Mission {mission_id} was already deleted on {result['deleted_at']}"
            )
        return

    if json_mode:
        click.echo(json.dumps({"id": mission_id, "deleted_at": result["deleted_at"]}))
        return

    click.echo(f"Deleted mission {mission_id}")


@main.command("show")
@click.argument("entity_id")
@click.option(
    "--no-knight", is_flag=True, default=False, help="Omit knight file contents."
)
@click.option(
    "--json",
    "json_flag",
    is_flag=True,
    default=False,
    hidden=True,
    help="Output as JSON.",
)
@click.pass_context
def show(ctx, entity_id, no_knight, json_flag):
    """Show details of a quest or mission."""
    json_mode = ctx.obj.get("json", False)
    if json_flag:
        ctx.obj["json"] = True
        json_mode = True
    if entity_id.startswith("q-") and "/" not in entity_id:
        # Use loose validation to allow test IDs inserted directly into the DB.
        # If loose validation fails, reject immediately with a format error.
        # If loose passes but strict fails, we still proceed to DB lookup;
        # the "not found" path handles missing quests gracefully.
        loose_err = validators.validate_quest_id_loose(entity_id)
        if loose_err:
            msg = f'Invalid quest ID format: "{entity_id}"'
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return
        # For IDs that pass loose but not strict validation, only proceed if
        # the quest actually exists in the DB; otherwise emit a format error.
        if validators.validate_entity_id(entity_id) is not None:
            from lore.db import get_quest as _gq

            if _gq(ctx.obj["project_root"], entity_id) is None:
                msg = f'Invalid quest ID format: "{entity_id}"'
                if json_mode:
                    click.echo(json.dumps({"error": msg}), err=True)
                else:
                    click.echo(msg, err=True)
                ctx.exit(1)
                return
        _show_quest(ctx, entity_id)
    elif "m-" in entity_id:
        if not _validate_mission_id(entity_id, ctx):
            return
        _show_mission(ctx, entity_id, no_knight)
    else:
        msg = f'Invalid ID format: "{entity_id}"'
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)


def _emit_not_found(ctx, entity_id, entity_type):
    """Emit a 'not found' error, annotating with deletion timestamp if soft-deleted."""
    from lore.db import get_deleted_at

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    deleted_at = get_deleted_at(project_root, entity_id)

    label = entity_type.capitalize()
    if deleted_at:
        msg = f'{label} "{entity_id}" not found (deleted on {deleted_at})'
        if json_mode:
            click.echo(json.dumps({"error": msg, "deleted_at": deleted_at}), err=True)
        else:
            click.echo(msg, err=True)
    else:
        msg = f'{label} "{entity_id}" not found'
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
    ctx.exit(1)


def _dep_status_symbol(status):
    """Return a circle symbol for the given status.

    ● closed  ◕ in_progress/blocked  ○ open or unknown
    """
    if status == "closed":
        return "\u25cf"  # ●
    if status in ("in_progress", "blocked"):
        return "\u25d5"  # ◕
    return "\u25cb"  # ○


def _dep_display_id(dep_id, current_quest_id):
    """Return short-form m-xxxx for intra-quest deps, fully-qualified otherwise."""
    if "/" in dep_id:
        parts = dep_id.split("/", 1)
        if parts[0] == current_quest_id:
            return parts[1]
    return dep_id


def _dep_to_rich(dep, current_quest_id):
    """Convert a dep dict to a (symbol, display_id, title) display tuple."""
    deleted = dep.get("deleted_at") is not None
    title = "[unknown]" if deleted else (dep.get("title") or "[unknown]")
    status = None if deleted else dep.get("status")
    symbol = _dep_status_symbol(status)
    display_id = _dep_display_id(dep["id"], current_quest_id)
    return symbol, display_id, title


def _show_mission(ctx, mission_id, no_knight):
    """Display mission detail with optional knight contents."""
    from lore.db import (
        get_mission,
        get_mission_depends_on_details,
        get_mission_blocks_details,
        get_deleted_at,
        get_board_messages,
    )

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    mission = get_mission(project_root, mission_id)

    if mission is None:
        _emit_not_found(ctx, mission_id, "mission")
        return

    # Check if parent quest is soft-deleted
    quest_deleted = False
    if mission["quest_id"]:
        quest_del_at = get_deleted_at(project_root, mission["quest_id"])
        if quest_del_at:
            quest_deleted = True

    depends_on_details = get_mission_depends_on_details(project_root, mission_id)
    blocks_details = get_mission_blocks_details(project_root, mission_id)
    board_messages = get_board_messages(project_root, mission_id)

    quest_id = mission["quest_id"] or ""

    if json_mode:
        knight_contents = None
        if mission["knight"] and not no_knight:
            _knights_dir = paths.knights_dir(project_root)
            knight_name = Path(mission["knight"]).stem
            knight_path = knight_module.find_knight(_knights_dir, knight_name)
            if knight_path is not None:
                knight_contents = knight_path.read_text()

        def _dep_to_json(dep):
            deleted = dep.get("deleted_at") is not None
            return {
                "id": dep["id"],
                "title": "[unknown]" if deleted else (dep.get("title") or "[unknown]"),
                "status": None if deleted else dep.get("status"),
            }

        data = {
            "id": mission["id"],
            "quest_id": mission["quest_id"],
            "title": mission["title"],
            "description": mission["description"],
            "status": mission["status"],
            "priority": mission["priority"],
            "mission_type": mission["mission_type"],
            "knight": mission["knight"],
            "knight_contents": knight_contents,
            "block_reason": mission["block_reason"],
            "created_at": mission["created_at"],
            "updated_at": mission["updated_at"],
            "closed_at": mission["closed_at"],
            "dependencies": {
                "needs": [_dep_to_json(d) for d in depends_on_details],
                "blocks": [_dep_to_json(d) for d in blocks_details],
            },
            "board": [
                {
                    "id": m["id"],
                    "sender": m["sender"],
                    "message": m["message"],
                    "created_at": m["created_at"],
                }
                for m in board_messages
            ],
        }
        click.echo(json.dumps(data))
        return

    quest_deleted_note = " (quest deleted)" if quest_deleted else ""
    click.echo(f"Mission: {mission['id']}{quest_deleted_note}")
    click.echo(f"Title: {mission['title']}")
    click.echo(f"Status: {mission['status']}")
    click.echo(f"Priority: {mission['priority']}")
    if mission["mission_type"]:
        click.echo(f"Type: {mission['mission_type']}")
    if mission["description"]:
        click.echo(f"Description: {mission['description']}")
    if mission["knight"]:
        click.echo(f"Knight: {mission['knight']}")
    if mission["block_reason"]:
        click.echo(f"Block Reason: {mission['block_reason']}")
    click.echo(f"Created: {mission['created_at']}")
    click.echo(f"Updated: {mission['updated_at']}")
    if mission["closed_at"]:
        click.echo(f"Closed: {mission['closed_at']}")

    # Dependencies: flat Needs / Blocks sections
    if depends_on_details or blocks_details:
        click.echo("")
        click.echo("Dependencies:")
        if depends_on_details:
            click.echo("  Needs:")
            for dep in depends_on_details:
                symbol, display_id, title = _dep_to_rich(dep, quest_id)
                click.echo(f"    {symbol} {display_id}  {title}")
        if blocks_details:
            click.echo("  Blocks:")
            for dep in blocks_details:
                symbol, display_id, title = _dep_to_rich(dep, quest_id)
                click.echo(f"    {symbol} {display_id}  {title}")

    if board_messages:
        click.echo("")
        click.echo("Board:")
        for msg in board_messages:
            if msg["sender"]:
                click.echo(
                    f"  [{msg['created_at']}] ({msg['sender']}) {msg['message']}"
                )
            else:
                click.echo(f"  [{msg['created_at']}] {msg['message']}")

    # Knight contents
    if mission["knight"] and not no_knight:
        _knights_dir = paths.knights_dir(project_root)
        knight_name = Path(mission["knight"]).stem
        knight_path = knight_module.find_knight(_knights_dir, knight_name)
        if knight_path is not None:
            click.echo("")
            click.echo("--- Knight Contents ---")
            click.echo(knight_path.read_text())
        else:
            click.echo("")
            click.echo(
                f'Warning: knight file "{mission["knight"]}" not found in .lore/knights/'
            )


def _show_quest(ctx, quest_id):
    """Display quest detail with missions."""
    json_mode = ctx.obj.get("json", False)

    from lore.db import (
        get_quest,
        get_missions_for_quest,
        get_board_messages,
        get_all_dependencies_for_quest,
        get_mission,
    )

    project_root = ctx.obj["project_root"]
    quest = get_quest(project_root, quest_id)

    if quest is None:
        _emit_not_found(ctx, quest_id, "quest")
        return

    missions = get_missions_for_quest(project_root, quest_id)
    board_messages = get_board_messages(project_root, quest_id)
    edges = get_all_dependencies_for_quest(project_root, quest_id)

    if json_mode:
        # Build per-mission dependency index
        # edges: from_id needs to_id; to_id blocks from_id
        mission_map = {m["id"]: m for m in missions}
        needs_map = {}  # mission_id -> list of to_id (what it needs)
        blocks_map = {}  # mission_id -> list of from_id (what it blocks)
        for edge in edges:
            needs_map.setdefault(edge["from_id"], []).append(edge["to_id"])
            blocks_map.setdefault(edge["to_id"], []).append(edge["from_id"])

        def _mission_ref(mid):
            m = mission_map.get(mid)
            if m is None:
                m = get_mission(project_root, mid)
            if m is None:
                return {"id": mid, "title": "[unknown]", "status": None}
            return {"id": mid, "title": m["title"], "status": m["status"]}

        missions_json = []
        for m in missions:
            mid = m["id"]
            needs_refs = [_mission_ref(tid) for tid in needs_map.get(mid, [])]
            blocks_refs = [_mission_ref(fid) for fid in blocks_map.get(mid, [])]
            missions_json.append(
                {
                    "id": mid,
                    "title": m["title"],
                    "status": m["status"],
                    "priority": m["priority"],
                    "mission_type": m["mission_type"],
                    "knight": m["knight"],
                    "dependencies": {
                        "needs": needs_refs,
                        "blocks": blocks_refs,
                    },
                }
            )

        data = {
            "id": quest["id"],
            "title": quest["title"],
            "description": quest["description"],
            "status": quest["status"],
            "priority": quest["priority"],
            "created_at": quest["created_at"],
            "updated_at": quest["updated_at"],
            "closed_at": quest["closed_at"],
            "auto_close": bool(quest["auto_close"]),
            "missions": missions_json,
            "board": [
                {
                    "id": msg["id"],
                    "sender": msg["sender"],
                    "message": msg["message"],
                    "created_at": msg["created_at"],
                }
                for msg in board_messages
            ],
        }
        click.echo(json.dumps(data))
        return

    click.echo(f"Quest: {quest['id']}")
    click.echo(f"Title: {quest['title']}")
    click.echo(f"Status: {quest['status']}")
    click.echo(f"Priority: {quest['priority']}")
    click.echo(f"Auto-Close: {'enabled' if quest['auto_close'] else 'disabled'}")
    if quest["description"]:
        click.echo(f"Description: {quest['description']}")
    click.echo(f"Created: {quest['created_at']}")
    click.echo(f"Updated: {quest['updated_at']}")
    if quest["closed_at"]:
        click.echo(f"Closed: {quest['closed_at']}")

    click.echo("")
    if not missions:
        click.echo("No missions.")
    else:
        click.echo("Missions:")
        mission_ids = {m["id"] for m in missions}

        # Filter edges to intra-quest pairs only before passing to graph module
        intra_quest_edges = [
            edge for edge in edges
            if edge["from_id"] in mission_ids and edge["to_id"] in mission_ids
        ]
        sorted_missions = graph.topological_sort_missions(missions, intra_quest_edges)

        # Build parents_map: child_id -> [display_id of each direct parent]
        parents_map = {}
        for edge in edges:
            child = edge["from_id"]
            parent = edge["to_id"]
            if child in mission_ids:
                pdisplay = _dep_display_id(parent, quest_id)
                parents_map.setdefault(child, []).append(pdisplay)

        # Build all base strings first, then measure max width for alignment
        lines_data = []
        for m in sorted_missions:
            symbol = _dep_status_symbol(m["status"])
            display_id = _dep_display_id(m["id"], quest_id)
            type_bracket = f" [{m['mission_type']}]" if m["mission_type"] else ""
            base = f"{symbol} {display_id}  {m['title']}{type_bracket}"
            parents = parents_map.get(m["id"], [])
            lines_data.append((base, parents))

        # Render lines with tab-aligned ← column
        has_any_parents = any(parents for _, parents in lines_data)
        if has_any_parents:
            col_width = max(len(base) for base, _ in lines_data)
            for base, parents in lines_data:
                if parents:
                    click.echo(f"{base:<{col_width}}  \u2190 {', '.join(parents)}")
                else:
                    click.echo(base)
        else:
            for base, _ in lines_data:
                click.echo(base)

    if board_messages:
        click.echo("")
        click.echo("Board:")
        for msg in board_messages:
            if msg["sender"]:
                click.echo(
                    f"  [{msg['created_at']}] ({msg['sender']}) {msg['message']}"
                )
            else:
                click.echo(f"  [{msg['created_at']}] {msg['message']}")


@main.group()
@click.pass_context
def codex(ctx):
    """Access project documentation — a set of typed markdown files maintained in .lore/codex/. Use 'lore codex list' to see all documents, 'lore codex search <keyword>' to narrow by keyword, and 'lore codex show <id>' to read one or more documents in full. Prefer 'lore codex show id1 id2' over multiple separate calls."""
    pass


@codex.command("list")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def codex_list(ctx, json_flag):
    """List all codex documents."""
    from lore.codex import scan_codex

    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)
    codex_dir = paths.codex_dir(project_root)

    documents = scan_codex(codex_dir)

    if json_mode:
        data = {
            "codex": [
                {
                    "id": d["id"],
                    "group": paths.derive_group(d["path"], codex_dir),
                    "title": d["title"],
                    "summary": d["summary"],
                }
                for d in documents
            ]
        }
        click.echo(json.dumps(data))
        return

    if not documents:
        click.echo("No codex documents found.")
        return

    rows = [
        [d["id"], paths.derive_group(d["path"], codex_dir), d["title"], d["summary"]]
        for d in documents
    ]
    for line in _format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows):
        click.echo(line)


@codex.command("search")
@click.argument("keyword")
@click.pass_context
def codex_search(ctx, keyword):
    """Search codex documents by keyword."""
    from lore.codex import search_documents

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    codex_dir = paths.codex_dir(project_root)

    documents = search_documents(codex_dir, keyword)

    if json_mode:
        data = {
            "documents": [
                {
                    "id": d["id"],
                    "title": d["title"],
                    "summary": d["summary"],
                }
                for d in documents
            ]
        }
        click.echo(json.dumps(data))
        return

    if not documents:
        click.echo(f'No documents matching "{keyword}".')
        return

    col_id = max(max(len(d["id"]) for d in documents), 2)
    col_title = max(max(len(d["title"]) for d in documents), 5)

    header = (
        f"  {'ID':<{col_id}}  {'TITLE':<{col_title}}  SUMMARY"
    )
    click.echo(header)
    for d in documents:
        click.echo(
            f"  {d['id']:<{col_id}}  {d['title']:<{col_title}}  {d['summary']}"
        )


@codex.command("show")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def codex_show(ctx, ids):
    """Show full content of one or more codex documents."""
    from lore.codex import read_document

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    codex_dir = paths.codex_dir(project_root)

    results = []
    for doc_id in dict.fromkeys(ids):
        doc = read_document(codex_dir, doc_id)
        if doc is None:
            if json_mode:
                click.echo(
                    json.dumps({"error": f'Document "{doc_id}" not found'}), err=True
                )
                ctx.exit(1)
                return
            click.echo(f'Document "{doc_id}" not found', err=True)
            ctx.exit(1)
            return
        results.append(doc)

    if json_mode:
        click.echo(json.dumps({"documents": results}))
        return

    for doc in results:
        click.echo(f"=== {doc['id']} ===")
        click.echo(doc["body"])


@codex.command("map")
@click.argument("doc_id")
@click.option(
    "--depth",
    type=click.IntRange(min=0),
    default=1,
    show_default=True,
    help="BFS traversal depth (0 = root only).",
)
@click.pass_context
def codex_map(ctx, doc_id, depth):
    """Map a codex document cluster via BFS traversal of 'related' links."""
    from lore.codex import map_documents

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    codex_dir = paths.codex_dir(project_root)

    documents = map_documents(codex_dir, doc_id, depth=depth)

    if documents is None:
        if json_mode:
            click.echo(
                json.dumps({"error": f'Document "{doc_id}" not found'}), err=True
            )
            ctx.exit(1)
            return
        click.echo(f'Document "{doc_id}" not found', err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps({"documents": documents}))
        return

    for doc in documents:
        click.echo(f"=== {doc['id']} ===")
        click.echo(doc["body"])


@codex.command("chaos")
@click.argument("doc_id")
@click.option(
    "--threshold",
    type=int,
    required=True,
    help="Walk termination threshold as an integer percentage (30–100).",
)
@click.option(
    "--json",
    "json_flag",
    is_flag=True,
    default=False,
    help="Output as JSON.",
)
@click.pass_context
def codex_chaos(ctx, doc_id, threshold, json_flag):
    """Random-walk traversal of connected codex documents from a seed ID."""
    from lore.codex import chaos_documents

    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)

    try:
        documents = chaos_documents(project_root, doc_id, threshold=threshold)
    except ValueError as exc:
        if json_mode:
            click.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            click.echo(str(exc), err=True)
        ctx.exit(1)
        return

    if documents is None:
        if json_mode:
            click.echo(
                json.dumps({"error": f'Document "{doc_id}" not found'}), err=True
            )
        else:
            click.echo(f'Document "{doc_id}" not found', err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps({"documents": documents}))
        return

    headers = ["ID", "TYPE", "TITLE", "SUMMARY"]
    rows = [
        [doc["id"], "", doc["title"], doc["summary"]]
        for doc in documents
    ]
    for line in _format_table(headers, rows):
        click.echo(line)


@main.group()
@click.pass_context
def artifact(ctx):
    """Access project artifacts — reusable template files stored in .lore/artifacts/ and accessed by stable ID. Use 'lore artifact list' to see available templates and 'lore artifact show <id>' to retrieve content. Always use these commands rather than reading .lore/artifacts/ files directly. Artifacts are read-only via the CLI; maintainers create and update them on disk."""
    pass


@artifact.command("list")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def artifact_list(ctx, json_flag):
    """List all artifacts."""
    from lore.artifact import scan_artifacts

    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)
    artifacts_dir = paths.artifacts_dir(project_root)

    artifacts = scan_artifacts(artifacts_dir)

    if json_mode:
        data = {
            "artifacts": [
                {
                    "id": a["id"],
                    "group": a["group"],
                    "title": a["title"],
                    "summary": a["summary"],
                }
                for a in artifacts
            ]
        }
        click.echo(json.dumps(data))
        return

    if not artifacts:
        click.echo("No artifacts found.")
        return

    rows = [[a["id"], a["group"], a["title"], a["summary"]] for a in artifacts]
    for line in _format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows):
        click.echo(line)


@artifact.command("show")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def artifact_show(ctx, ids):
    """Show full content of one or more artifacts."""
    from lore.artifact import read_artifact

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    artifacts_dir = paths.artifacts_dir(project_root)

    results = []
    for artifact_id in dict.fromkeys(ids):
        art = read_artifact(artifacts_dir, artifact_id)
        if art is None:
            if json_mode:
                click.echo(
                    json.dumps({"error": f'Artifact "{artifact_id}" not found'}),
                    err=True,
                )
                ctx.exit(1)
                return
            click.echo(f'Artifact "{artifact_id}" not found', err=True)
            ctx.exit(1)
            return
        results.append(art)

    if json_mode:
        click.echo(json.dumps({"artifacts": results}))
        return

    for art in results:
        click.echo(f"=== {art['id']} ===")
        click.echo(art["body"])


@main.group()
@click.pass_context
def board(ctx):
    """Manage board messages for quests and missions."""
    pass


@board.command("add")
@click.argument("entity_id")
@click.argument("message")
@click.option("--sender", "-s", default=None, help="Sender identifier.")
@click.pass_context
def board_add(ctx, entity_id, message, sender):
    """Post a message to a quest or mission board."""
    from lore.db import add_board_message

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    result = add_board_message(project_root, entity_id, message, sender)

    if not result.get("ok", False):
        error = result.get("error", "Unknown error")
        if json_mode:
            click.echo(json.dumps({"error": error}), err=True)
        else:
            click.echo(error, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(
            json.dumps(
                {
                    "id": result["id"],
                    "entity_id": result["entity_id"],
                    "sender": result["sender"],
                    "created_at": result["created_at"],
                }
            )
        )
        return

    click.echo(f"Board message posted (id: {result['id']}).")


@board.command("delete")
@click.argument("message_id", type=int)
@click.pass_context
def board_delete(ctx, message_id):
    """Delete a board message by its integer ID."""
    from lore.db import delete_board_message

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    result = delete_board_message(project_root, message_id)

    if not result.get("ok", False):
        error = result.get("error", "Unknown error")
        if json_mode:
            click.echo(json.dumps({"error": error}), err=True)
        else:
            click.echo(error, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps({"id": result["id"], "deleted_at": result["deleted_at"]}))
        return

    click.echo(f"Board message {message_id} deleted.")


# ---------------------------------------------------------------------------
# Watcher commands
# ---------------------------------------------------------------------------


@main.group()
@click.pass_context
def watcher(ctx):
    """Manage watcher definitions stored in .lore/watchers/."""
    pass


@watcher.command("list")
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.pass_context
def watcher_list(ctx, json_mode):
    """List all watcher definitions."""
    from lore import watcher as watcher_module

    project_root = ctx.obj["project_root"]
    # Honour both the local --json flag and the global --json flag
    json_mode = json_mode or ctx.obj.get("json", False)
    w_dir = paths.watchers_dir(project_root)

    watchers = watcher_module.list_watchers(w_dir)

    if json_mode:
        click.echo(json.dumps({"watchers": watchers}))
        return

    if not watchers:
        click.echo("No watchers found.")
        return

    headers = ["ID", "GROUP", "TITLE", "SUMMARY"]
    rows = [[w["id"], w["group"], w["title"], w["summary"]] for w in watchers]
    for line in _format_table(headers, rows):
        click.echo(line)


@watcher.command("show")
@click.argument("name")
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.pass_context
def watcher_show(ctx, name, json_mode):
    """Show the full definition of a watcher."""
    from lore import watcher as watcher_module

    project_root = ctx.obj["project_root"]
    json_mode = json_mode or ctx.obj.get("json", False)
    w_dir = paths.watchers_dir(project_root)

    try:
        filepath = watcher_module.find_watcher(w_dir, name)
    except ValueError as exc:
        if json_mode:
            click.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            click.echo(str(exc), err=True)
        ctx.exit(1)

    if filepath is None:
        msg = f'Watcher "{name}" not found.'
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)

    if json_mode:
        data = watcher_module.load_watcher(filepath)
        click.echo(json.dumps(data))
    else:
        click.echo(filepath.read_text(), nl=False)


@watcher.command("new")
@click.argument("name")
@click.option("--from", "from_file", default=None, help="Read content from file instead of stdin.")
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.pass_context
def watcher_new(ctx, name, from_file, json_mode):
    """Create a new watcher definition."""
    from lore import watcher as watcher_module

    project_root = ctx.obj["project_root"]
    json_mode = json_mode or ctx.obj.get("json", False)
    w_dir = paths.watchers_dir(project_root)

    # Read content
    if from_file is not None:
        src = Path(from_file)
        if not src.exists():
            click.echo(f"File not found: {from_file}", err=True)
            ctx.exit(1)
            return
        content = src.read_text()
    else:
        content = click.get_text_stream("stdin").read()

    if not content or not content.strip():
        click.echo("No content provided on stdin.", err=True)
        ctx.exit(1)
        return

    try:
        result = watcher_module.create_watcher(w_dir, name, content)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
    else:
        click.echo(f"Created watcher {name}")


@watcher.command("edit")
@click.argument("name")
@click.option("--from", "from_file", default=None, help="Read content from file instead of stdin.")
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.pass_context
def watcher_edit(ctx, name, from_file, json_mode):
    """Update an existing watcher definition in place."""
    from lore import watcher as watcher_module

    project_root = ctx.obj["project_root"]
    json_mode = json_mode or ctx.obj.get("json", False)
    w_dir = paths.watchers_dir(project_root)

    # Read content
    if from_file is not None:
        src = Path(from_file)
        if not src.exists():
            click.echo(f"File not found: {from_file}", err=True)
            ctx.exit(1)
            return
        content = src.read_text()
    else:
        content = click.get_text_stream("stdin").read()

    if not content or not content.strip():
        click.echo("No content provided on stdin.", err=True)
        ctx.exit(1)
        return

    try:
        result = watcher_module.update_watcher(w_dir, name, content)
    except ValueError as exc:
        if json_mode:
            click.echo(json.dumps({"error": str(exc)}))
        else:
            click.echo(str(exc), err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
    else:
        click.echo(f"Updated watcher {name}")


@watcher.command("delete")
@click.argument("name")
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.pass_context
def watcher_delete(ctx, name, json_mode):
    """Soft-delete a watcher definition (renames to .yaml.deleted)."""
    from lore import watcher as watcher_module

    project_root = ctx.obj["project_root"]
    json_mode = json_mode or ctx.obj.get("json", False)
    w_dir = paths.watchers_dir(project_root)

    try:
        result = watcher_module.delete_watcher(w_dir, name)
    except ValueError as exc:
        if json_mode:
            click.echo(json.dumps({"error": str(exc)}))
        else:
            click.echo(str(exc), err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
    else:
        click.echo(f"Deleted watcher {name}")
