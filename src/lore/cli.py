"""Click command definitions for the Lore CLI."""

import json
from pathlib import Path

import yaml

import click

from lore.api import (
    ProjectNotFoundError,
    create_artifact,
    create_knight,
    find_project_root,
)
from lore.api import _graph as graph
from lore.api import _knight as knight_module
from lore.api import _lore_version as __version__
from lore.api import _paths as paths
from lore.api import _validators as validators


# ---------------------------------------------------------------------------
# US-009 --help teaching surface (ADR-008: help as teaching interface).
# Constants + helpers keep the nine enriched new/list subcommands in sync
# without scattering identical strings across cli.py.
# ---------------------------------------------------------------------------

# Shared `--filter` option help for every `list` subcommand that supports
# slash-delimited group filters (doctrine, knight, watcher, artifact, codex).
_FILTER_OPT_HELP = (
    "Filter by slash-delimited group token (e.g. a/b/c). Space-separated for multiple: --filter a b c."
)

# Suffix appended to each `list` command's docstring. The `{example}` slot is
# the only part that differs between resources.
_LIST_HELP_SUFFIX_TEMPLATE = (
    "\n\n    --filter accepts slash-delimited group tokens, e.g. --filter {example}."
    "\n\n    See: .lore/codex/codex.md\n    "
)


def _list_doc(summary: str, example: str) -> str:
    """Build a `list` subcommand docstring with the shared teaching suffix."""
    return f"{summary}{_LIST_HELP_SUFFIX_TEMPLATE.format(example=example)}"


def _group_opt_help(resource_dir: str, example: str) -> str:
    """Build a `--group` option help string for a `new` subcommand.

    resource_dir is the POSIX path under .lore/ (e.g. ``.lore/knights/``);
    example is a concrete nested token such as ``feature-implementation/on-prd-ready``.
    """
    return (
        f"Nested subdirectory under {resource_dir} "
        f"(slash-delimited, e.g. {example})."
    )


# Suffix appended to each `new` command's docstring. The `{resource}` slot is
# the only part that differs between resources.
_NEW_HELP_SUFFIX_TEMPLATE = (
    "\n\n    Without --group, the {resource} lands at the default root ({root}).\n"
    "    Use --group with a slash-delimited token to nest under subdirectories.\n\n"
    "    \\b\n"
    "    Example:\n"
    "      {example}\n    "
)


def _new_doc(summary: str, resource: str, root: str, example: str) -> str:
    """Build a `new` subcommand docstring with the shared teaching suffix."""
    return summary + _NEW_HELP_SUFFIX_TEMPLATE.format(
        resource=resource, root=root, example=example
    )


def _group_for_json(g):
    """Map empty-string group to None for JSON emitters (US-007)."""
    return g or None


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


def _emit_format_error(ctx, entity_id):
    """Emit a uniform 'Invalid quest ID format' error to stderr and exit 1.

    Consolidates the format-error emission previously inline at show/delete
    dispatchers (Spec §G12 CHANGED #8). JSON mode emits a single-key envelope;
    text mode emits the bare message.
    """
    json_mode = ctx.obj.get("json", False)
    msg = f'Invalid quest ID format: "{entity_id}"'
    if json_mode:
        click.echo(json.dumps({"error": msg}), err=True)
    else:
        click.echo(msg, err=True)
    ctx.exit(1)


def _classify_entity_id_with_db_fallback(project_root, entity_id):
    """Classify *entity_id* as ``"quests"`` / ``"missions"`` / ``None``.

    Strict path: ``validators.route_entity`` returns the table for any ID
    matching the canonical hex pattern. For loose quest IDs (g–z letters
    valid in test-DB fixtures) we fall back to a direct DB probe so that
    synthetic IDs still resolve. Returns ``None`` for unrecognised input
    (caller emits a format error via ``_emit_format_error``).
    """
    if not entity_id:
        return None
    try:
        table, _ = validators.route_entity(entity_id)
        return table
    except ValueError:
        pass
    # Loose-quest-ID fallback — only legal for quest-shaped IDs (no slash).
    if validators.validate_quest_id_loose(entity_id) is None:
        from lore.api import read_quest
        if read_quest(project_root, entity_id) is not None:
            return "quests"
    return None


def _write_design_file(design_path: Path, doctrine_id: str, yaml_content: str) -> None:
    """Write a minimal .design.md file alongside a newly created doctrine YAML.

    Extracts title and summary from the YAML content when present; falls back
    to the doctrine id for title and empty string for summary.
    """
    import yaml as _yaml
    title = doctrine_id
    summary = ""
    try:
        data = _yaml.safe_load(yaml_content)
        if isinstance(data, dict):
            title = data.get("title") or doctrine_id
            summary = data.get("summary") or ""
    except Exception:
        pass
    design_path.write_text(
        f"---\nid: {doctrine_id}\ntitle: {title}\nsummary: {summary}\n---\n"
    )


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


class _OrderedGroup(click.Group):
    """Click group preserving command registration order in help output."""

    def list_commands(self, ctx):
        return list(self.commands.keys())


@click.group(cls=_OrderedGroup, invoke_without_command=True)
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
    Artifact — reusable template files referenced by stable ID.
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
    from lore.api import get_dashboard_quests
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
    from lore.api import get_aggregate_stats
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
@click.pass_context
def oracle(ctx):
    """Generate human-readable markdown reports in .lore/reports/. Produces one file per quest and mission. Wipes and recreates the reports directory on every run — do not store custom files there. Intended for human stakeholders, not for agent consumption. JSON output is not supported for this command."""
    if ctx.obj.get("json", False):
        click.echo(
            "Error: JSON output is not supported for 'lore oracle'. "
            "Oracle generates human-readable markdown reports only.",
            err=True,
        )
        ctx.exit(2)

    from lore.api import generate_reports
    project_root = ctx.obj["project_root"]
    generate_reports(project_root)
    click.echo("Reports generated in .lore/reports/")


@main.command()
@click.pass_context
def init(ctx):
    """Initialize a Lore project in the current directory."""
    from lore.api import run_init
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

    from lore.api import create_quest
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    ac_value = 1 if auto_close else 0
    try:
        envelope = create_quest(
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

    quest_id = envelope["id"]
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

    from lore.api import create_mission
    project_root = ctx.obj["project_root"]

    # Inferred-parent-quest lookup lives in db.create_mission (G12).
    try:
        envelope = create_mission(
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

    mission_id = envelope["id"]
    if json_mode:
        click.echo(json.dumps({"id": mission_id}))
        return

    click.echo(f"Created mission {mission_id}")


@main.command("claim")
@click.argument("mission_ids", nargs=-1, required=True)
@click.pass_context
def claim(ctx, mission_ids):
    """Claim one or more missions (open -> in_progress)."""
    from lore.api import claim_missions
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    envelope = claim_missions(project_root, list(mission_ids))

    if json_mode:
        click.echo(json.dumps(envelope))
        if envelope["errors"]:
            ctx.exit(1)
        return

    from lore.api import read_mission
    updated_set = set(envelope["updated"])
    error_text = "\n".join(envelope["errors"])
    for mid in mission_ids:
        if mid in updated_set:
            click.echo(f"{mid}: in_progress")
            continue
        # Idempotent re-claim (already in_progress) — not in updated, not in
        # errors. Surface current status from the DB so text output mirrors
        # the pre-G12 behaviour.
        if mid in error_text:
            continue
        mission = read_mission(project_root, mid)
        if mission is not None:
            click.echo(f"{mid}: {mission['status']}")
    for err in envelope["errors"]:
        click.echo(err, err=True)

    if envelope["errors"]:
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
    from lore.api import close_entities
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    from lore.api import read_quest, read_mission
    def _is_quest_shaped(eid: str) -> bool:
        """Quest-shaped ID detection via route_entity (no inline prefix check)."""
        try:
            table, _ = validators.route_entity(eid)
            return table == "quests"
        except ValueError:
            # Fall back to loose quest pattern (allows test-DB synthetic IDs).
            return validators.validate_quest_id_loose(eid) is None

    # Text-mode renders distinct "already closed" vs "closed (closed_at: ...)"
    # branches for quest IDs. Snapshot pre-call quest status so we can
    # render the right message without altering the envelope shape.
    pre_call_quest_status: dict[str, str | None] = {}
    if not json_mode:
        for eid in entity_ids:
            if _is_quest_shaped(eid):
                q = read_quest(project_root, eid)
                pre_call_quest_status[eid] = q["status"] if q is not None else None

    envelope = close_entities(project_root, list(entity_ids))

    if json_mode:
        click.echo(json.dumps(envelope))
        if envelope["errors"]:
            ctx.exit(1)
        return

    updated_set = set(envelope["updated"])
    quest_closed_set = set(envelope["quest_closed"])
    for eid in entity_ids:
        if eid not in updated_set:
            continue
        is_quest = _is_quest_shaped(eid)
        if is_quest:
            if pre_call_quest_status.get(eid) == "closed":
                click.echo(f"{eid}: already closed")
                continue
            quest = read_quest(project_root, eid)
            if quest is not None and quest["closed_at"] is not None:
                click.echo(
                    f"{eid}: closed (closed_at: {quest['closed_at']})"
                )
            else:
                click.echo(f"{eid}: closed")
        else:
            quest_id = eid.split("/")[0] if "/" in eid else None
            mission = read_mission(project_root, eid)
            if (
                quest_id is not None
                and quest_id in quest_closed_set
            ):
                click.echo(f"{eid}: closed (quest auto-closed)")
            else:
                status = mission["status"] if mission is not None else "closed"
                click.echo(f"{eid}: {status}")
    for err in envelope["errors"]:
        click.echo(err, err=True)

    if envelope["errors"]:
        ctx.exit(1)


@main.command("block")
@click.argument("mission_id")
@click.argument("reason")
@click.pass_context
def block(ctx, mission_id, reason):
    """Mark a mission as blocked with a reason."""
    from lore.api import block_mission
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
    from lore.api import unblock_mission
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
    from lore.api import get_ready_missions
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
    from lore.api import add_dependencies
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    parsed_pairs: list[tuple[str, str]] = []
    pair_errors: list[str] = []
    for pair in pairs:
        parts = pair.split(":")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            pair_errors.append(
                f'Invalid dependency pair format: "{pair}". Expected "from:to".'
            )
            continue
        parsed_pairs.append((parts[0], parts[1]))

    db_envelope = add_dependencies(project_root, parsed_pairs)
    db_errors = db_envelope["errors"]
    envelope = {
        "created": db_envelope["created"],
        "existing": db_envelope["existing"],
        "errors": pair_errors + db_errors,
    }

    if json_mode:
        click.echo(json.dumps(envelope))
        if envelope["errors"]:
            ctx.exit(1)
        return

    from lore.api import read_mission
    for err in pair_errors:
        click.echo(err, err=True)
    for entry in envelope["existing"]:
        click.echo(f"Dependency already exists: {entry['from']} -> {entry['to']}")
    for entry in envelope["created"]:
        click.echo(f"Dependency created: {entry['from']} -> {entry['to']}")
        # Re-derive closed_target signal (add_dependencies discards it):
        # check whether the target mission is closed.
        target = read_mission(project_root, entry["to"])
        if target is not None and target["status"] == "closed":
            click.echo(
                f"Note: dependency target {entry['to']} is already closed. "
                f"Mission {entry['from']} is not blocked."
            )
    for err in db_errors:
        click.echo(err, err=True)

    if envelope["errors"]:
        ctx.exit(1)


@main.command("unneed")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.argument("pairs", nargs=-1, required=True)
@click.pass_context
def unneed(ctx, json_flag, pairs):
    """Remove dependencies between missions using colon-pair syntax."""
    from lore.api import remove_dependencies
    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)

    parsed_pairs: list[tuple[str, str]] = []
    pair_errors: list[str] = []
    valid_pairs_for_render: list[tuple[str, str]] = []

    for pair in pairs:
        parts = pair.split(":")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            pair_errors.append(f'Invalid pair format: "{pair}"')
            continue
        from_id, to_id = parts
        from_err = validators.validate_mission_id(from_id)
        to_err = validators.validate_mission_id(to_id)
        if from_err or to_err:
            pair_errors.append(from_err if from_err else to_err)
            continue
        parsed_pairs.append((from_id, to_id))
        valid_pairs_for_render.append((from_id, to_id))

    envelope = remove_dependencies(project_root, parsed_pairs)
    envelope = {
        "removed": envelope["removed"],
        "not_found": envelope["not_found"],
        "errors": pair_errors + envelope["errors"],
    }

    if not json_mode:
        for err in pair_errors:
            click.echo(err, err=True)
        removed_set = {(e["from"], e["to"]) for e in envelope["removed"]}
        for from_id, to_id in valid_pairs_for_render:
            if (from_id, to_id) in removed_set:
                click.echo(f"Dependency removed: {from_id} -> {to_id}")
            else:
                click.echo(f"Warning: no dependency found: {from_id} -> {to_id}")
    else:
        click.echo(json.dumps(envelope))

    if envelope["errors"]:
        ctx.exit(1)


@main.command("list")
@click.option("--all", "show_all", is_flag=True, help="Include closed quests.")
@click.pass_context
def list_quests(ctx, show_all):
    """List quests."""
    from lore.api import list_quests as db_list_quests
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
    from lore.api import read_quest, list_missions_grouped
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    # Validate quest exists if specified
    if quest_id is not None:
        quest = read_quest(project_root, quest_id)
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

    envelope = list_missions_grouped(
        project_root, quest_id=quest_id, include_closed=show_all
    )

    if json_mode:
        flat = []
        for group in envelope["groups"]:
            flat.extend(group["missions"])
        click.echo(json.dumps({"missions": flat}))
        return

    if not envelope["groups"]:
        click.echo("No missions found.")
        return

    def _format_mission_line(m):
        knight_str = f"  [{m['knight']}]" if m["knight"] else ""
        type_str = f"  [{m['mission_type']}]" if m["mission_type"] else ""
        return f"  {m['id']}  P{m['priority']}  [{m['status']}]{type_str}  {m['title']}{knight_str}"

    # Display quest-bound groups first (sorted by qid), then standalone.
    quest_groups = sorted(
        (g for g in envelope["groups"] if g["quest_id"] is not None),
        key=lambda g: g["quest_id"],
    )
    standalone_group = next(
        (g for g in envelope["groups"] if g["quest_id"] is None), None
    )

    for group in quest_groups:
        qid = group["quest_id"]
        quest_title = group["quest_title"] if group["quest_title"] is not None else qid
        quest_deleted_annotation = (
            " (quest deleted)" if group["quest_deleted_at"] else ""
        )
        click.echo(f"Quest: {quest_title} ({qid}){quest_deleted_annotation}")
        for m in group["missions"]:
            click.echo(_format_mission_line(m))
        click.echo("")

    if standalone_group is not None:
        click.echo("Standalone:")
        for m in standalone_group["missions"]:
            click.echo(_format_mission_line(m))


@main.group()
@click.pass_context
def knight(ctx):
    """Manage knight personas — reusable markdown files that tell a worker agent how to approach work (style, constraints, authority). Assign a knight to a mission with 'lore new mission -k <name>.md'. When a worker runs 'lore show <mission-id>', the knight's content is included in the output. Knights encode the 'how'; mission descriptions encode the 'what'."""
    pass


@knight.command(
    "list",
    help=_list_doc("List available knights.", "feature-implementation/prd-handlers"),
)
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.option("--filter", "filter_groups", multiple=True, help=_FILTER_OPT_HELP)
@click.argument("extra_filters", nargs=-1)
@click.pass_context
def knight_list(ctx, json_flag, filter_groups, extra_filters):
    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)

    combined_filters = list(filter_groups) + list(extra_filters)
    records = knight_module.list_knights(project_root, filter_groups=combined_filters if combined_filters else None)

    if json_mode:
        filtered = [
            {"id": r["id"], "group": _group_for_json(r["group"]), "title": r["title"], "summary": r["summary"]}
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

    try:
        record = knight_module.read_knight(project_root, name)
    except ValueError:
        record = None

    if record is None:
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
        # Section D: JSON mode emits the whole read_knight dict.
        click.echo(json.dumps(record))
        return

    # Text mode emits frontmatter + body (full file shape).
    fm_lines = "\n".join(
        f"{k}: {record[k]}" for k in ("id", "title", "summary")
    )
    click.echo(f"---\n{fm_lines}\n---\n{record['body']}", nl=False)


@knight.command(
    "new",
    context_settings={"ignore_unknown_options": True},
    help=_new_doc(
        "Create a new knight.",
        resource="knight",
        root=".lore/knights/",
        example="lore knight new on-prd-ready --group feature-implementation/prd-handlers -f p.md",
    ),
)
@click.argument("name")
@click.option(
    "--from", "-f", "from_file", default=None, help="Source file for knight content."
)
@click.option(
    "--group",
    default=None,
    help=_group_opt_help(".lore/knights/", "feature-implementation/on-prd-ready"),
)
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def knight_new(ctx, name, from_file, group, json_flag):
    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)

    if from_file is not None and from_file != "-":
        source = Path(from_file)
        if not source.exists():
            msg = f"File not found: {from_file}"
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return
        content = source.read_text()
    else:
        content = click.get_text_stream("stdin").read()
        if not content.strip():
            msg = "No content provided on stdin."
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return

    try:
        result = create_knight(project_root, name, content, group=group)
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
        return

    suffix = f" (group: {group})" if group else ""
    click.echo(f"Created knight {name}{suffix}")


# ---------------------------------------------------------------------------
# Field-edit mode shared helpers (spec: transient-frontmatter-field-edit-spec).
# Mutually exclusive with -f / --from. The four <entity> edit handlers use
# these to parse KEY=VALUE strings, coerce scalars per schema, and dispatch
# into ``lore.api.update_frontmatter_fields``.
# ---------------------------------------------------------------------------


def _split_kv(raw: str) -> tuple[str, str]:
    """Split a CLI KEY=VALUE on the first ``=``. Empty key raises ValueError."""
    if "=" not in raw:
        raise ValueError("--set/--add/--remove requires KEY=VALUE")
    key, value = raw.split("=", 1)
    if not key:
        raise ValueError("--set/--add/--remove requires KEY=VALUE")
    return key, value


def _dispatch_field_edit(
    ctx,
    kind: str,
    name: str,
    set_kvs: tuple[str, ...],
    unset_keys: tuple[str, ...],
    add_kvs: tuple[str, ...],
    remove_kvs: tuple[str, ...],
) -> dict | None:
    """Run field-edit mode for one entity. Returns the envelope, or None on
    error (after emitting stderr + ctx.exit(1)).

    Parses raw CLI KEY=VALUE strings, coerces scalars per schema (rejecting
    structured-item fields), then calls ``update_frontmatter_fields``.
    """
    from lore.api import _frontmatter_edit as _fm_edit_mod
    from lore.api import update_frontmatter_fields

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)
    # For coercion only: codex schema_kind is a callable (doc_type dispatcher);
    # the on-disk field shapes are identical across codex / codex-source, so
    # use the default schema string for coercion. Final validation uses the
    # callable inside update_frontmatter_fields.
    raw_schema_kind = _fm_edit_mod._KINDS[kind].schema_kind
    schema_kind = (
        "codex-frontmatter" if kind == "codex" else raw_schema_kind
    )
    coerce = _fm_edit_mod._coerce_scalar_for_schema

    try:
        set_dict: dict = {}
        for raw in set_kvs:
            key, value = _split_kv(raw)
            set_dict[key] = coerce(schema_kind, key, value)

        add_dict: dict = {}
        for raw in add_kvs:
            key, value = _split_kv(raw)
            # Validate field shape: must be a scalar-array; reject structured.
            coerce(schema_kind, key, value)
            add_dict.setdefault(key, []).append(value.strip())

        remove_dict: dict = {}
        for raw in remove_kvs:
            key, value = _split_kv(raw)
            coerce(schema_kind, key, value)
            remove_dict.setdefault(key, []).append(value.strip())

        result = update_frontmatter_fields(
            project_root,
            kind,
            name,
            set_fields=set_dict or None,
            unset_fields=list(unset_keys) or None,
            add_to_list=add_dict or None,
            remove_from_list=remove_dict or None,
        )
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return None

    return result


def _reject_mutex(ctx, json_mode: bool, from_file, set_kvs, unset_keys, add_kvs, remove_kvs) -> bool:
    """If -f conflicts with any field-mode flag, emit error and exit. Returns True if rejected."""
    field_mode = bool(set_kvs or unset_keys or add_kvs or remove_kvs)
    if from_file is not None and field_mode:
        msg = "Cannot combine -f/--from with --set/--unset/--add/--remove."
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return True
    return False


@knight.command("edit")
@click.argument("name")
@click.option(
    "--from", "-f", "from_file", default=None, help="Source file for knight content."
)
@click.option("--set", "set_kvs", multiple=True, help="Set frontmatter field KEY=VALUE.")
@click.option("--unset", "unset_keys", multiple=True, help="Remove frontmatter field KEY.")
@click.option("--add", "add_kvs", multiple=True, help="Append to list-typed field KEY=VALUE.")
@click.option("--remove", "remove_kvs", multiple=True, help="Remove from list-typed field KEY=VALUE.")
@click.pass_context
def knight_edit(ctx, name, from_file, set_kvs, unset_keys, add_kvs, remove_kvs):
    """Edit an existing knight.

    Field-edit mode (mutually exclusive with -f / --from):
      --set    KEY=VALUE   set a frontmatter field
      --unset  KEY         remove a frontmatter field
      --add    KEY=VALUE   append to a list-typed field
      --remove KEY=VALUE   remove a value from a list-typed field
    """
    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    if _reject_mutex(ctx, json_mode, from_file, set_kvs, unset_keys, add_kvs, remove_kvs):
        return

    field_mode = bool(set_kvs or unset_keys or add_kvs or remove_kvs)
    if field_mode:
        result = _dispatch_field_edit(
            ctx, "knight", name, set_kvs, unset_keys, add_kvs, remove_kvs
        )
        if result is None:
            return
        if json_mode:
            click.echo(json.dumps(result))
            return
        click.echo(f"Updated knight {name}")
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

    try:
        result = knight_module.update_knight(project_root, name, content)
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
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

    try:
        result = knight_module.delete_knight(project_root, name)
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
        return
    click.echo(f"Deleted knight {name}")


@main.group()
@click.pass_context
def doctrine(ctx):
    """Manage doctrine templates — YAML files that describe the step sequence and suggested knights for a standard body of work (e.g. a feature or bugfix workflow). Doctrines have no execution engine; an orchestrator reads them with 'lore doctrine show <name>' and translates the steps into quests and missions as guidance. Doctrines are passive — they do not trigger actions."""
    pass


@doctrine.command(
    "list",
    help=_list_doc("List available doctrines.", "seo-analysis/keyword-analysers"),
)
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.option("--filter", "filter_groups", multiple=True, help=_FILTER_OPT_HELP)
@click.argument("extra_filters", nargs=-1)
@click.pass_context
def doctrine_list(ctx, json_flag, filter_groups, extra_filters):
    from lore.api import _doctrine as _doctrine_mod
    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)

    combined_filters = list(filter_groups) + list(extra_filters)
    doctrines = _doctrine_mod.list_doctrines(project_root, filter_groups=combined_filters if combined_filters else None)

    if json_mode:
        data = {
            "doctrines": [
                {
                    "id": d["id"],
                    "group": _group_for_json(d.get("group", "")),
                    "title": d["title"],
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
            d["id"],
            d.get("group", ""),
            d["title"],
            d.get("summary", ""),
        ]
        for d in doctrines
    ]
    for line in _format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows):
        click.echo(line)


@doctrine.command("show")
@click.argument("name")
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def doctrine_show(ctx, name, json_flag):
    """Show a doctrine (design file then YAML)."""
    from lore.api import _doctrine as _doctrine_mod
    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)

    d = _doctrine_mod.read_doctrine(project_root, name)
    if d is None:
        msg = f"Doctrine '{name}' not found"
        if json_flag:
            click.echo(json.dumps({"error": msg}))
        elif json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        output = {
            "id": d["id"],
            "title": d["title"],
            "summary": d["summary"],
            "design": d["design"],
            "steps": d["steps"],
        }
        click.echo(json.dumps(output))
        return

    click.echo(d["design"], nl=False)
    click.echo("\n---\n", nl=False)
    click.echo(d["raw_yaml"], nl=False)


@doctrine.command(
    "new",
    help=_new_doc(
        "Create a new doctrine from a YAML file and a design file.",
        resource="doctrine",
        root=".lore/doctrines/",
        example="lore doctrine new keyword-ranker --group seo-analysis/keyword-analysers -f r.yaml -d r.md",
    ),
)
@click.argument("name")
@click.option("--from", "-f", "from_file", default=None, help="Source YAML file.")
@click.option("--design", "-d", "design_file", default=None, help="Source design file.")
@click.option(
    "--group",
    default=None,
    help=_group_opt_help(".lore/doctrines/", "seo-analysis/keyword-analysers"),
)
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def doctrine_new(ctx, name, from_file, design_file, group, json_flag):
    from lore.api import create_doctrine
    json_mode = json_flag or ctx.obj.get("json", False)

    # Both flags are required
    if from_file is None:
        msg = "Error: -f/--from is required"
        click.echo(msg, err=True)
        ctx.exit(1)
        return

    if design_file is None:
        msg = "Error: -d/--design is required"
        click.echo(msg, err=True)
        ctx.exit(1)
        return

    if not _validate_name(name, ctx):
        return

    project_root = ctx.obj["project_root"]

    try:
        result = create_doctrine(
            project_root, name, Path(from_file), Path(design_file), group=group
        )
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
        return

    suffix = f" (group: {group})" if group else ""
    click.echo(f"Created doctrine {name}{suffix}")


@doctrine.command("edit")
@click.argument("name")
@click.option("--from", "-f", "from_file", default=None, help="Source file.")
@click.option("--set", "set_kvs", multiple=True, help="Set frontmatter field KEY=VALUE.")
@click.option("--unset", "unset_keys", multiple=True, help="Remove frontmatter field KEY.")
@click.option("--add", "add_kvs", multiple=True, help="Append to list-typed field KEY=VALUE.")
@click.option("--remove", "remove_kvs", multiple=True, help="Remove from list-typed field KEY=VALUE.")
@click.pass_context
def doctrine_edit(ctx, name, from_file, set_kvs, unset_keys, add_kvs, remove_kvs):
    """Edit an existing doctrine.

    Field-edit mode (mutually exclusive with -f / --from) targets the
    ``<name>.yaml`` file. To edit the ``.design.md`` partner, use ``-f``.

      --set    KEY=VALUE   set a frontmatter field
      --unset  KEY         remove a frontmatter field
      --add    KEY=VALUE   append to a list-typed field
      --remove KEY=VALUE   remove a value from a list-typed field
    """
    from lore.api import update_doctrine
    json_mode = ctx.obj.get("json", False)

    if not _validate_name(name, ctx):
        return

    project_root = ctx.obj["project_root"]

    if _reject_mutex(ctx, json_mode, from_file, set_kvs, unset_keys, add_kvs, remove_kvs):
        return

    field_mode = bool(set_kvs or unset_keys or add_kvs or remove_kvs)
    if field_mode:
        result = _dispatch_field_edit(
            ctx, "doctrine", name, set_kvs, unset_keys, add_kvs, remove_kvs
        )
        if result is None:
            return
        if json_mode:
            click.echo(json.dumps(result))
            return
        click.echo(f"Updated doctrine {name}")
        return

    # Read content (CLI-only I/O concerns stay in the CLI).
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

    try:
        result = update_doctrine(project_root, name, content)
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}))
        else:
            click.echo(msg)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
        return
    click.echo(f"Updated doctrine {name}")


@doctrine.command("delete")
@click.argument("name")
@click.pass_context
def doctrine_delete(ctx, name):
    """Delete a doctrine."""
    from lore.api import delete_doctrine
    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    try:
        result = delete_doctrine(project_root, name)
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
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

    try:
        table, _ = validators.route_entity(entity_id)
    except ValueError:
        _emit_format_error(ctx, entity_id)
        return

    if table == "quests":
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
    """Edit a quest's fields — thin wrapper over update_quest_full."""
    from lore.api import update_quest_full
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    try:
        envelope = update_quest_full(
            project_root,
            quest_id,
            title=title,
            description=description,
            priority=priority,
            auto_close=auto_close,
        )
    except ValueError as exc:
        msg = str(exc)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(envelope))
        return

    click.echo(f"Updated quest {quest_id}")


def _edit_mission(
    ctx, mission_id, title, description, priority, knight, no_knight, mission_type=None
):
    """Edit a mission's fields — thin wrapper over update_mission_full."""
    from lore.api import update_mission_full
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    try:
        envelope = update_mission_full(
            project_root,
            mission_id,
            title=title,
            description=description,
            priority=priority,
            knight=knight,
            remove_knight=no_knight,
            mission_type=mission_type,
        )
    except ValueError as exc:
        msg = str(exc)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(envelope))
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
    from lore.api import delete_entity, delete_quest as _delq, get_deleted_at
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    # Classify via route_entity (strict) first; on failure attempt loose
    # quest-ID fallback (test fixtures use non-hex chars). Mission-shaped
    # IDs that fail strict validation are format errors.
    try:
        table, _ = validators.route_entity(entity_id)
    except ValueError:
        if validators.validate_quest_id_loose(entity_id) is None:
            table = "quests"
        else:
            _emit_format_error(ctx, entity_id)
            return

    # Snapshot pre-call deleted_at to distinguish idempotent re-delete
    # (Section D: CLI's "already deleted" message derived from the deleted_at
    # value — predates the call ⇒ already-deleted branch).
    pre_deleted_at = get_deleted_at(project_root, entity_id)

    try:
        envelope = delete_entity(project_root, entity_id, cascade=cascade)
    except ValueError as exc:
        # If delete_entity raised because route_entity rejected the ID, try
        # the loose-quest fallback (test fixtures with non-hex chars). If
        # that also raises, surface the most specific error message — the
        # underlying delete_quest "not found" trumps the routing "unrecognised"
        # message because it pertains to the entity itself.
        try:
            envelope = _delq(project_root, entity_id, cascade=cascade)
        except ValueError as inner_exc:
            msg = str(inner_exc)
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return
        except Exception:
            msg = str(exc)
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return

    if json_mode:
        click.echo(json.dumps(envelope))
        return

    # Text mode — idempotent re-delete: pre-existing deleted_at means
    # the call was a no-op (amendment Section D — derive from timestamp).
    if pre_deleted_at is not None:
        if table == "quests":
            click.echo(
                f"Warning: Quest {entity_id} was already deleted on {envelope['deleted_at']}"
            )
        else:
            click.echo(
                f"Warning: Mission {entity_id} was already deleted on {envelope['deleted_at']}"
            )
        return

    if table == "quests":
        click.echo(f"Deleted quest {entity_id}")
        cascade_ids = envelope.get("cascade") or []
        if cascade and cascade_ids:
            click.echo("Cascade deleted:")
            for mid in cascade_ids:
                click.echo(f"  {mid}")
    else:
        click.echo(f"Deleted mission {entity_id}")


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
    if json_flag:
        ctx.obj["json"] = True

    project_root = ctx.obj["project_root"]
    table = _classify_entity_id_with_db_fallback(project_root, entity_id)
    if table is None:
        _emit_format_error(ctx, entity_id)
        return

    if table == "quests":
        _show_quest(ctx, entity_id)
    else:
        _show_mission(ctx, entity_id, no_knight)


def _emit_not_found(ctx, entity_id, entity_type):
    """Emit a 'not found' error, annotating with deletion timestamp if soft-deleted."""
    from lore.api import get_deleted_at
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
    from lore.api import (
        read_mission,
        list_mission_depends_on,
        list_mission_blocks,
        get_deleted_at,
        list_board_messages,
        get_mission_detail,
    )

    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    if json_mode:
        envelope = get_mission_detail(
            project_root, mission_id, include_knight=not no_knight
        )
        if envelope is None:
            _emit_not_found(ctx, mission_id, "mission")
            return
        click.echo(json.dumps(envelope))
        return

    mission = read_mission(project_root, mission_id)

    if mission is None:
        _emit_not_found(ctx, mission_id, "mission")
        return

    # Check if parent quest is soft-deleted
    quest_deleted = False
    if mission["quest_id"]:
        quest_del_at = get_deleted_at(project_root, mission["quest_id"])
        if quest_del_at:
            quest_deleted = True

    depends_on_details = list_mission_depends_on(project_root, mission_id)
    blocks_details = list_mission_blocks(project_root, mission_id)
    board_messages = list_board_messages(project_root, mission_id)

    quest_id = mission["quest_id"] or ""

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
        knight_name = Path(mission["knight"]).stem
        try:
            knight_record = knight_module.read_knight(project_root, knight_name)
        except ValueError:
            knight_record = None
        if knight_record is not None:
            click.echo("")
            click.echo("--- Knight Contents ---")
            # Render frontmatter + body to preserve byte-identical output.
            fm_lines = "\n".join(
                f"{k}: {knight_record[k]}" for k in ("id", "title", "summary")
            )
            click.echo(f"---\n{fm_lines}\n---\n{knight_record['body']}", nl=False)
        else:
            click.echo("")
            click.echo(
                f'Warning: knight file "{mission["knight"]}" not found in .lore/knights/'
            )


def _show_quest(ctx, quest_id):
    """Display quest detail with missions."""
    json_mode = ctx.obj.get("json", False)

    from lore.api import (
        read_quest,
        get_missions_for_quest,
        list_board_messages,
        get_all_dependencies_for_quest,
        get_quest_detail,
    )

    project_root = ctx.obj["project_root"]

    if json_mode:
        envelope = get_quest_detail(project_root, quest_id)
        if envelope is None:
            _emit_not_found(ctx, quest_id, "quest")
            return
        click.echo(json.dumps(envelope))
        return

    quest = read_quest(project_root, quest_id)

    if quest is None:
        _emit_not_found(ctx, quest_id, "quest")
        return

    missions = get_missions_for_quest(project_root, quest_id)
    board_messages = list_board_messages(project_root, quest_id)
    edges = get_all_dependencies_for_quest(project_root, quest_id)

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


@codex.command(
    "list",
    help=_list_doc("List all codex documents.", "conceptual/workflows"),
)
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.option("--filter", "filter_groups", multiple=True, help=_FILTER_OPT_HELP)
@click.argument("extra_filters", nargs=-1)
@click.pass_context
def codex_list(ctx, json_flag, filter_groups, extra_filters):
    from lore.api import list_codex
    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)
    codex_dir = paths.codex_dir(project_root)

    combined_filters = list(filter_groups) + list(extra_filters)
    documents = list_codex(project_root, filter_groups=combined_filters if combined_filters else None)

    if json_mode:
        data = {
            "codex": [
                {
                    "id": d["id"],
                    "group": _group_for_json(paths.derive_group(d["path"], codex_dir)),
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
    from lore.api import search_documents
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    documents = search_documents(project_root, keyword)

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


def _render_glossary_block(items) -> str:
    """Render ``## Glossary`` block. Empty list → empty string."""
    if not items:
        return ""
    ordered = sorted(items, key=lambda i: i.keyword.casefold())
    paragraphs = [
        f"**{i.keyword}** — {' '.join(i.definition.split())}"
        for i in ordered
    ]
    return "\n## Glossary\n\n" + "\n\n".join(paragraphs) + "\n"


@codex.command("show")
@click.argument("ids", nargs=-1, required=True)
@click.option(
    "--skip-glossary",
    "-S",
    "skip_glossary",
    is_flag=True,
    default=False,
    help="Suppress the glossary auto-surface for this call.",
)
@click.pass_context
def codex_show(ctx, ids, skip_glossary):
    """Show full content of one or more codex documents."""
    from lore.api import _glossary as _glossary
    from lore.api import read_documents_with_glossary
    from lore.api import load_config
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    config = load_config(project_root)
    auto_surface = config.show_glossary_on_codex_commands and not skip_glossary

    unique_ids = list(dict.fromkeys(ids))
    glossary_warning: str | None = None
    try:
        envelope = read_documents_with_glossary(
            project_root, unique_ids, skip_glossary=not auto_surface,
        )
    except (_glossary.GlossaryError, OSError) as exc:
        # Fail-soft: glossary problems must never block doc display
        # (NFR-Reliability). Re-read documents without glossary surface
        # and carry a stderr warning.
        envelope = read_documents_with_glossary(
            project_root, unique_ids, skip_glossary=True,
        )
        glossary_warning = f"glossary unavailable: {exc}"

    # Short-circuit on first missing doc — preserves legacy exit/stderr.
    for doc in envelope["documents"]:
        if doc.get("not_found"):
            doc_id = doc["id"]
            if json_mode:
                click.echo(
                    json.dumps({"error": f'Document "{doc_id}" not found'}), err=True
                )
                ctx.exit(1)
                return
            click.echo(f'Document "{doc_id}" not found', err=True)
            ctx.exit(1)
            return

    results = envelope["documents"]
    glossary_items = envelope["glossary"]

    if json_mode:
        click.echo(
            json.dumps(
                {
                    "documents": results,
                    "glossary": [_glossary_entry_dict(i) for i in glossary_items],
                }
            )
        )
    else:
        for doc in results:
            click.echo(f"=== {doc['id']} ===")
            click.echo(doc["body"])
        block = _render_glossary_block(glossary_items)
        if block:
            click.echo(block, nl=False)

    if glossary_warning is not None:
        click.echo(glossary_warning, err=True)


def _resolve_codex_map_depths(
    depth: int | None,
    depth_out: int | None,
    depth_in: int | None,
) -> tuple[int | None, int | None, int | None]:
    """Resolve pass-through (depth, depth_out, depth_in) for ``map_documents``.

    Rules:
      - --depth alone → pass ``depth=N``; both directional flags None.
      - One of --depth-in/--depth-out → the other defaults to 0 (CLI rule —
        directional flag flips off the implicit-1 in that direction).
      - When none of the three are given → all three None; ``map_documents``
        falls back to its 1/1 defaults.
      - --depth + any directional → pass-through unchanged so the
        ``ConflictingDepthFlags`` raise fires inside ``map_documents``.
    """
    if depth is not None and (depth_in is not None or depth_out is not None):
        return depth, depth_out, depth_in
    if depth is not None:
        return depth, None, None
    if depth_in is None and depth_out is None:
        return None, None, None
    eff_out = depth_out if depth_out is not None else 0
    eff_in = depth_in if depth_in is not None else 0
    return None, eff_out, eff_in


def _render_codex_map_default(documents: list[dict], *, json_mode: bool) -> None:
    """Render default-mode (table / json list shape) output for codex map."""
    if json_mode:
        data = {"codex": [
            {"id": d["id"], "group": _group_for_json(d["group"]),
             "title": d["title"], "summary": d["summary"]}
            for d in documents
        ]}
        click.echo(json.dumps(data))
        return
    if not documents:
        click.echo("No related documents.")
        return
    rows = [[d["id"], d["group"], d["title"], d["summary"]] for d in documents]
    for line in _format_table(["ID", "GROUP", "TITLE", "SUMMARY"], rows):
        click.echo(line)


def _render_codex_map_full(documents: list[dict], *, json_mode: bool) -> None:
    """Render full-mode (bodies / raw json documents) output for codex map."""
    if json_mode:
        click.echo(json.dumps({"documents": documents}))
        return
    for doc in documents:
        click.echo(f"=== {doc['id']} ===")
        click.echo(doc["body"])


@codex.command("map")
@click.argument("doc_id")
@click.option(
    "--depth",
    type=click.IntRange(min=0),
    default=None,
    help="Symmetric traversal depth in both directions. Mutually exclusive with --depth-in/--depth-out. Default 1.",
)
@click.option(
    "--depth-out",
    type=click.IntRange(min=0),
    default=None,
    help="Outbound traversal depth (follows 'related' links). Default 1; not allowed with --depth.",
)
@click.option(
    "--depth-in",
    type=click.IntRange(min=0),
    default=None,
    help="Inbound traversal depth (follows backlinks). Default 1; not allowed with --depth.",
)
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="Print full document bodies instead of the default neighbour table.",
)
@click.pass_context
def codex_map(ctx, doc_id, depth, depth_out, depth_in, full):
    """Map a codex document cluster via BFS traversal of 'related' links."""
    json_mode = ctx.obj.get("json", False)

    from lore.api import ConflictingDepthFlags, map_documents
    eff_depth, eff_out, eff_in = _resolve_codex_map_depths(
        depth, depth_out, depth_in,
    )

    project_root = ctx.obj["project_root"]

    try:
        documents = map_documents(
            project_root, doc_id,
            depth=eff_depth, depth_out=eff_out, depth_in=eff_in, full=full,
        )
    except ConflictingDepthFlags:
        msg = (
            "--depth cannot be combined with --depth-in or --depth-out. "
            "Use --depth for symmetric traversal, or --depth-in and/or "
            "--depth-out for directional traversal."
        )
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
            ctx.exit(2)
            return
        raise click.UsageError(msg)

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

    if full:
        _render_codex_map_full(documents, json_mode=json_mode)
    else:
        _render_codex_map_default(documents, json_mode=json_mode)


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
    from lore.api import chaos_documents
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


# ---------------------------------------------------------------------------
# Codex CRUD subcommands — new / edit / delete (codex-CRUD spec §B).
# ---------------------------------------------------------------------------


@codex.command(
    "new",
    context_settings={"ignore_unknown_options": True},
    help=_new_doc(
        "Create a new codex document.",
        resource="codex doc",
        root=".lore/codex/",
        example="lore codex new my-doc --group decisions -f my-doc.md",
    ),
)
@click.argument("name")
@click.option(
    "--from", "-f", "from_file", default=None, help="Source file for doc content."
)
@click.option(
    "--group",
    default=None,
    help=_group_opt_help(".lore/codex/", "decisions"),
)
@click.option(
    "--type",
    "doc_type",
    type=click.Choice(["codex", "codex-source"]),
    default=None,
    help="Override path-derived doc_type (codex / codex-source).",
)
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def codex_new(ctx, name, from_file, group, doc_type, json_flag):
    from lore.api import create_document

    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)

    if from_file is not None and from_file != "-":
        source = Path(from_file)
        if not source.exists():
            msg = f"File not found: {from_file}"
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return
        content = source.read_text()
    else:
        content = click.get_text_stream("stdin").read()
        if not content.strip():
            msg = "No content provided on stdin."
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return

    try:
        result = create_document(
            project_root, name, content, group=group, doc_type=doc_type
        )
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
        return

    suffix = f" (group: {group})" if group else ""
    click.echo(f"Created codex doc {name}{suffix}")


@codex.command("edit")
@click.argument("name")
@click.option(
    "--from", "-f", "from_file", default=None, help="Source file for doc content."
)
@click.option("--set", "set_kvs", multiple=True, help="Set frontmatter field KEY=VALUE.")
@click.option("--unset", "unset_keys", multiple=True, help="Remove frontmatter field KEY.")
@click.option("--add", "add_kvs", multiple=True, help="Append to list-typed field KEY=VALUE.")
@click.option("--remove", "remove_kvs", multiple=True, help="Remove from list-typed field KEY=VALUE.")
@click.pass_context
def codex_edit(ctx, name, from_file, set_kvs, unset_keys, add_kvs, remove_kvs):
    """Edit an existing codex doc.

    Field-edit mode (mutually exclusive with -f / --from):
      --set    KEY=VALUE   set a frontmatter field
      --unset  KEY         remove a frontmatter field
      --add    KEY=VALUE   append to a list-typed field
      --remove KEY=VALUE   remove a value from a list-typed field
    """
    from lore.api import update_document

    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    if _reject_mutex(ctx, json_mode, from_file, set_kvs, unset_keys, add_kvs, remove_kvs):
        return

    field_mode = bool(set_kvs or unset_keys or add_kvs or remove_kvs)
    if field_mode:
        result = _dispatch_field_edit(
            ctx, "codex", name, set_kvs, unset_keys, add_kvs, remove_kvs
        )
        if result is None:
            return
        if json_mode:
            click.echo(json.dumps(result))
            return
        click.echo(f"Updated codex doc {name}")
        return

    if from_file is not None and from_file != "-":
        source = Path(from_file)
        if not source.exists():
            msg = f"File not found: {from_file}"
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return
        content = source.read_text()
    else:
        content = click.get_text_stream("stdin").read()
        if not content.strip():
            msg = "No content provided on stdin."
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return

    try:
        result = update_document(project_root, name, content)
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
        return
    click.echo(f"Updated codex doc {name}")


@codex.command("delete")
@click.argument("name")
@click.pass_context
def codex_delete(ctx, name):
    """Delete a codex doc.

    Seeded docs (e.g. ``codex`` — the .lore/codex/codex.md root index)
    cannot be deleted. Edit them instead.
    """
    from lore.api import delete_document

    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    try:
        result = delete_document(project_root, name)
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
        return
    click.echo(f"Deleted codex doc {name}")


# ---------------------------------------------------------------------------
# `lore impacts` — codex<->code binding surfacing (US-003 + US-004).
# Top-level command, sibling to `lore codex` / `lore artifact`.
# ---------------------------------------------------------------------------


def _render_impacts_json(result) -> str:
    """Render *result* as the ``{"impacts": [...]}`` JSON envelope."""
    if result.kind == "codex":
        items: list[dict] = [
            {"path": b.path, "kind": b.kind}
            for b in result.codex_items
        ]
    else:
        items = []
        for b in result.code_items:
            row: dict = {"id": b.id, "match": b.match}
            if b.match == "glob":
                row["pattern"] = b.pattern
            items.append(row)
    return json.dumps({"impacts": items})


def _render_impacts_default(result) -> str:
    """Render *result* as one binding per line.

    Codex seed: bare path. Code seed: bare id for exact, ``id  (glob: pattern)``
    for glob.
    """
    if result.kind == "codex":
        return "".join(f"{b.path}\n" for b in result.codex_items)
    lines: list[str] = []
    for b in result.code_items:
        if b.match == "exact":
            lines.append(f"{b.id}\n")
        else:
            lines.append(f"{b.id}  (glob: {b.pattern})\n")
    return "".join(lines)


@main.command("impacts")
@click.argument("token")
@click.option(
    "--direct-links",
    is_flag=True,
    default=False,
    help="Path seed only: drop glob matches; keep exact only.",
)
@click.option(
    "--json",
    "json_flag",
    is_flag=True,
    default=False,
    help="Emit structured JSON envelope.",
)
@click.pass_context
def impacts_cmd(ctx, token, direct_links, json_flag):
    """Surface codex<->code bindings.

    TOKEN is a codex ID or a repo-relative/absolute file path. Containing
    '/' or '.' classifies it as a path; otherwise as a codex ID.
    """
    from lore.api import _impacts as _impacts

    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)

    try:
        result = _impacts.impacts(
            token, project_root=project_root, direct_links=direct_links
        )
    except _impacts.ImpactsError as exc:
        if json_mode:
            click.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            click.echo(str(exc), err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(_render_impacts_json(result))
        return

    # `_render_impacts_default` already includes a trailing newline per binding
    # (and empty string for no bindings), so suppress click's own newline.
    click.echo(_render_impacts_default(result), nl=False)


# ---------------------------------------------------------------------------
# Glossary command group (glossary-us-002).
#
# CLI handlers stay thin — IO + matching live in `lore.glossary`, the data
# shape lives in `lore.models.GlossaryItem`. This file only formats output
# and threads errors through `--json` mode (standards-separation-of-concerns).
# ---------------------------------------------------------------------------


# Sentinel for empty alias / do_not_use lists in text output (Tech Spec).
_GLOSSARY_EMPTY_LIST = "—"

# List-view definition preview length. Definitions are short summaries here;
# `lore glossary show <keyword>` is the canonical full-text surface.
# Kept compact so the table fits in a typical terminal and so list output
# remains a quick keyword index rather than a documentation dump.
_GLOSSARY_DEFINITION_PREVIEW = 6


def _aliases_or_dash(aliases) -> str:
    return ", ".join(aliases) if aliases else _GLOSSARY_EMPTY_LIST


def _glossary_entry_dict(item) -> dict:
    """JSON-shaped view of a GlossaryItem — arrays always present (FR-30 contract)."""
    return {
        "keyword": item.keyword,
        "definition": item.definition,
        "aliases": list(item.aliases),
        "do_not_use": list(item.do_not_use),
    }


def _sorted_by_keyword(items):
    """Stable alphabetical order by casefolded keyword (FR-5 / Tech Spec)."""
    return sorted(items, key=lambda i: i.keyword.casefold())


def _truncate_definition(definition: str) -> str:
    """Trim a definition to the list-view preview length, with `…` if cut."""
    if len(definition) > _GLOSSARY_DEFINITION_PREVIEW:
        return definition[:_GLOSSARY_DEFINITION_PREVIEW] + "…"
    return definition


def render_glossary_list_text(items) -> str:
    """Render the alphabetised KEYWORD/ALIASES/DEFINITION table for `list`/`search`."""
    headers = ["KEYWORD", "ALIASES", "DEFINITION"]
    rows = [
        [item.keyword, _aliases_or_dash(item.aliases), _truncate_definition(item.definition)]
        for item in _sorted_by_keyword(items)
    ]

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    def _fmt(row):
        return f"{row[0]:<{col_widths[0]}} {row[1]:<{col_widths[1]}} {row[2]}"

    lines = [_fmt(headers)] + [_fmt(row) for row in rows]
    return "\n".join(lines) + "\n"


def render_glossary_list_json(items) -> dict:
    """Build the `{"glossary": [...]}` envelope used by `list`/`search` JSON modes."""
    return {"glossary": [_glossary_entry_dict(i) for i in _sorted_by_keyword(items)]}


def _emit_glossary_error(ctx, message: str) -> None:
    """Write an error to stderr respecting `--json` and exit 1.

    Returns through ``ctx.exit`` (raises ``click.exceptions.Exit``); the caller
    does not need to ``return`` afterwards but pre-existing handlers do for
    static-analysis clarity.
    """
    json_mode = ctx.obj.get("json", False)
    if json_mode:
        click.echo(json.dumps({"error": message}), err=True)
    else:
        click.echo(f"Error: {message}", err=True)
    ctx.exit(1)


def _emit_no_glossary(ctx) -> None:
    """Stdout response when the glossary file is missing or has zero items."""
    if ctx.obj.get("json", False):
        click.echo(json.dumps({"glossary": []}))
    else:
        click.echo("No glossary defined.")


def _load_glossary_or_fail(ctx):
    """Scan the glossary; on `GlossaryError` emit the standard error and exit 1."""
    from lore.api import GlossaryError, scan_glossary
    try:
        return scan_glossary(ctx.obj["project_root"])
    except GlossaryError as e:
        _emit_glossary_error(ctx, f"glossary unavailable: {e}")
        return None  # unreachable: ctx.exit raised


def _emit_glossary_table(ctx, items) -> None:
    """Render the shared list/search payload in the active output mode."""
    if ctx.obj.get("json", False):
        click.echo(json.dumps(render_glossary_list_json(items)))
    else:
        click.echo(render_glossary_list_text(items), nl=False)


@main.group(invoke_without_command=True)
@click.pass_context
def glossary(ctx):
    """Access the project glossary — the controlled vocabulary at .lore/codex/glossary.yaml.

    Use 'lore glossary list' to browse all keywords (or just 'lore glossary'),
    'lore glossary search <query>' to find entries by substring across keyword,
    aliases, do_not_use and definition, and 'lore glossary show <keyword>' to
    read full definitions. Use 'lore glossary new' / 'edit' / 'delete' to
    maintain entries — run 'lore artifact show glossary-design' first to
    confirm the entry belongs in the glossary. See the Glossary section of
    .lore/codex/codex.md.
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(glossary_list)


@glossary.command("list")
@click.pass_context
def glossary_list(ctx):
    """List all glossary entries — alphabetised, definitions truncated.

    Same as bare 'lore glossary'. Add --json (on the top-level command) for the
    machine-readable envelope. Empty/missing glossary prints 'No glossary defined.'
    and exits 0; a malformed glossary fails loud with exit 1.
    """
    items = _load_glossary_or_fail(ctx)
    if items is None:
        return
    if not items:
        _emit_no_glossary(ctx)
        return
    _emit_glossary_table(ctx, items)


@glossary.command("search")
@click.argument("query")
@click.pass_context
def glossary_search(ctx, query):
    """Search the glossary by case-insensitive substring.

    QUERY is matched against keyword, aliases, do_not_use, and definition for
    each entry. Results are alphabetised by keyword. With no matches, prints
    'No glossary entries matching "<query>".' (or {"glossary": []} in --json
    mode) and exits 0. Missing glossary file behaves the same as `list`.
    """
    from lore.api import search_glossary
    items = _load_glossary_or_fail(ctx)
    if items is None:
        return
    if not items:
        _emit_no_glossary(ctx)
        return

    results = search_glossary(ctx.obj["project_root"], query)
    if not results:
        if ctx.obj.get("json", False):
            click.echo(json.dumps({"glossary": []}))
        else:
            click.echo(f'No glossary entries matching "{query}".')
        return
    _emit_glossary_table(ctx, results)


def _render_glossary_show_block(item) -> str:
    """One '=== Keyword ===' block for the `show` text output."""
    return (
        f"=== {item.keyword} ===\n"
        f"Keyword: {item.keyword}\n"
        f"Aliases: {_aliases_or_dash(item.aliases)}\n"
        f"Do not use: {_aliases_or_dash(item.do_not_use)}\n"
        f"Definition:\n"
        f"  {item.definition}"
    )


@glossary.command("show")
@click.argument("keywords", nargs=-1, required=True)
@click.pass_context
def glossary_show(ctx, keywords):
    """Show full content of one or more glossary entries.

    Lookup is case-insensitive on keyword (display preserves source casing).
    Aliases are NOT lookup keys (FR-7). Multiple keywords are accepted as
    space-separated args (ADR-012); output is alphabetised regardless of input
    order. Fails fast with no partial stdout if any keyword is missing.
    """
    from lore.api import GlossaryError, read_glossary_item
    project_root = ctx.obj["project_root"]

    resolved = []
    for kw in keywords:
        try:
            item = read_glossary_item(project_root, kw)
        except GlossaryError as e:
            _emit_glossary_error(ctx, f"glossary unavailable: {e}")
            return
        if item is None:
            _emit_glossary_error(ctx, f'glossary keyword "{kw}" not found.')
            return
        resolved.append(item)

    resolved = _sorted_by_keyword(resolved)

    if ctx.obj.get("json", False):
        click.echo(json.dumps({"glossary": [_glossary_entry_dict(i) for i in resolved]}))
        return

    click.echo("\n\n".join(_render_glossary_show_block(item) for item in resolved))


@glossary.command("new")
@click.argument("keyword")
@click.option("--definition", "-d", required=True, help="Definition body.")
@click.option(
    "--alias", "aliases", multiple=True,
    help="Repeatable. Auto-surface alias for this keyword.",
)
@click.option(
    "--do-not-use", "do_not_use", multiple=True,
    help="Repeatable. Deprecated surface form for this keyword.",
)
@click.pass_context
def glossary_new(ctx, keyword, definition, aliases, do_not_use):
    """Create a new glossary entry — run 'lore artifact show glossary-design' first."""
    from lore.api import create_glossary_item
    project_root = ctx.obj["project_root"]
    try:
        envelope = create_glossary_item(
            project_root,
            keyword,
            definition,
            aliases=list(aliases) if aliases else None,
            do_not_use=list(do_not_use) if do_not_use else None,
        )
    except ValueError as e:
        _emit_glossary_error(ctx, str(e))
        return

    if ctx.obj.get("json", False):
        click.echo(json.dumps(envelope))
    else:
        click.echo(f'Created glossary item "{envelope["keyword"]}".')


@glossary.command("edit")
@click.argument("keyword")
@click.option("--definition", "-d", default=None, help="Replace definition.")
@click.option(
    "--alias", "aliases", multiple=True,
    help="Repeatable. Replace alias list with these values.",
)
@click.option(
    "--no-aliases", is_flag=True, default=False,
    help="Clear the aliases list entirely.",
)
@click.option(
    "--do-not-use", "do_not_use", multiple=True,
    help="Repeatable. Replace do_not_use list with these values.",
)
@click.option(
    "--no-do-not-use", is_flag=True, default=False,
    help="Clear the do_not_use list entirely.",
)
@click.pass_context
def glossary_edit(ctx, keyword, definition, aliases, no_aliases, do_not_use, no_do_not_use):
    """Edit a glossary entry. Keyword is the identity — to rename, delete + new."""
    if aliases and no_aliases:
        _emit_glossary_error(ctx, "cannot combine --alias and --no-aliases.")
        return
    if do_not_use and no_do_not_use:
        _emit_glossary_error(ctx, "cannot combine --do-not-use and --no-do-not-use.")
        return

    aliases_arg: list[str] | None
    if no_aliases:
        aliases_arg = []
    elif aliases:
        aliases_arg = list(aliases)
    else:
        aliases_arg = None

    dnu_arg: list[str] | None
    if no_do_not_use:
        dnu_arg = []
    elif do_not_use:
        dnu_arg = list(do_not_use)
    else:
        dnu_arg = None

    from lore.api import update_glossary_item
    project_root = ctx.obj["project_root"]
    try:
        envelope = update_glossary_item(
            project_root,
            keyword,
            definition=definition,
            aliases=aliases_arg,
            do_not_use=dnu_arg,
        )
    except ValueError as e:
        _emit_glossary_error(ctx, str(e))
        return

    if ctx.obj.get("json", False):
        click.echo(json.dumps(envelope))
    else:
        click.echo(f'Updated glossary item "{envelope["keyword"]}".')


@glossary.command("delete")
@click.argument("keyword")
@click.pass_context
def glossary_delete(ctx, keyword):
    """Hard-delete a glossary entry. Idempotent — missing keyword is not an error."""
    from lore.api import delete_glossary_item
    project_root = ctx.obj["project_root"]
    try:
        envelope = delete_glossary_item(project_root, keyword)
    except ValueError as e:
        _emit_glossary_error(ctx, str(e))
        return

    if ctx.obj.get("json", False):
        click.echo(json.dumps(envelope))
    else:
        click.echo(f'Deleted glossary item "{envelope["keyword"]}".')


@main.group()
@click.pass_context
def artifact(ctx):
    """Access project artifacts — reusable template files stored in .lore/artifacts/ and accessed by stable ID. Use 'lore artifact list' to see available templates and 'lore artifact show <id>' to retrieve content. Always use these commands rather than reading .lore/artifacts/ files directly. Use 'lore artifact new' / 'edit' / 'delete' to maintain entries."""
    pass


@artifact.command(
    "list",
    help=_list_doc("List all artifacts.", "default/codex"),
)
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.option("--filter", "filter_groups", multiple=True, help=_FILTER_OPT_HELP)
@click.argument("extra_filters", nargs=-1)
@click.pass_context
def artifact_list(ctx, json_flag, filter_groups, extra_filters):
    from lore.api import list_artifacts
    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)

    combined_filters = list(filter_groups) + list(extra_filters)
    if any(not token.strip("/") for token in combined_filters):
        raise click.ClickException("empty filter token")

    artifacts = list_artifacts(project_root, filter_groups=combined_filters if combined_filters else None)

    if json_mode:
        data = {
            "artifacts": [
                {
                    "id": a["id"],
                    "group": _group_for_json(a["group"]),
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
    from lore.api import read_artifact
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    results = []
    for artifact_id in dict.fromkeys(ids):
        art = read_artifact(project_root, artifact_id)
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
        # Single-id calls return the record dict directly so callers can
        # read filename/group keys at the top level (G16 amendment Section D).
        if len(results) == 1:
            click.echo(json.dumps(results[0]))
        else:
            click.echo(json.dumps({"artifacts": results}))
        return

    for art in results:
        click.echo(f"=== {art['id']} ===")
        click.echo(art["body"])


@artifact.command(
    "new",
    context_settings={"ignore_unknown_options": True},
    help=_new_doc(
        "Create a new artifact.",
        resource="artifact",
        root=".lore/artifacts/",
        example="lore artifact new fi-review --group codex-templates/review-forms -f r.md",
    ),
)
@click.argument("name")
@click.option(
    "--from", "-f", "from_file", default=None, help="Source file for artifact content."
)
@click.option(
    "--group",
    default=None,
    help=_group_opt_help(".lore/artifacts/", "codex-templates/review-forms"),
)
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON.")
@click.pass_context
def artifact_new(ctx, name, from_file, group, json_flag):
    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = json_flag or ctx.obj.get("json", False)

    if from_file is not None and from_file != "-":
        source = Path(from_file)
        if not source.exists():
            msg = f"File not found: {from_file}"
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return
        content = source.read_text()
    else:
        content = click.get_text_stream("stdin").read()
        if not content.strip():
            msg = "No content provided on stdin."
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return

    try:
        result = create_artifact(project_root, name, content, group=group)
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
        return

    suffix = f" (group: {group})" if group else ""
    click.echo(f"Created artifact {name}{suffix}")


@artifact.command("edit")
@click.argument("name")
@click.option(
    "--from", "-f", "from_file", default=None, help="Source file for artifact content."
)
@click.option("--set", "set_kvs", multiple=True, help="Set frontmatter field KEY=VALUE.")
@click.option("--unset", "unset_keys", multiple=True, help="Remove frontmatter field KEY.")
@click.option("--add", "add_kvs", multiple=True, help="Append to list-typed field KEY=VALUE.")
@click.option("--remove", "remove_kvs", multiple=True, help="Remove from list-typed field KEY=VALUE.")
@click.pass_context
def artifact_edit(ctx, name, from_file, set_kvs, unset_keys, add_kvs, remove_kvs):
    """Edit an existing artifact.

    Field-edit mode (mutually exclusive with -f / --from):
      --set    KEY=VALUE   set a frontmatter field
      --unset  KEY         remove a frontmatter field
      --add    KEY=VALUE   append to a list-typed field
      --remove KEY=VALUE   remove a value from a list-typed field
    """
    from lore.api import update_artifact
    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    if _reject_mutex(ctx, json_mode, from_file, set_kvs, unset_keys, add_kvs, remove_kvs):
        return

    field_mode = bool(set_kvs or unset_keys or add_kvs or remove_kvs)
    if field_mode:
        result = _dispatch_field_edit(
            ctx, "artifact", name, set_kvs, unset_keys, add_kvs, remove_kvs
        )
        if result is None:
            return
        if json_mode:
            click.echo(json.dumps(result))
            return
        click.echo(f"Updated artifact {name}")
        return

    if from_file is not None and from_file != "-":
        source = Path(from_file)
        if not source.exists():
            msg = f"File not found: {from_file}"
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return
        content = source.read_text()
    else:
        content = click.get_text_stream("stdin").read()
        if not content.strip():
            msg = "No content provided on stdin."
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.echo(msg, err=True)
            ctx.exit(1)
            return

    try:
        result = update_artifact(project_root, name, content)
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
        return
    click.echo(f"Updated artifact {name}")


@artifact.command("delete")
@click.argument("name")
@click.pass_context
def artifact_delete(ctx, name):
    """Delete an artifact."""
    from lore.api import delete_artifact
    if not _validate_name(name, ctx):
        return
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    try:
        result = delete_artifact(project_root, name)
    except ValueError as e:
        msg = str(e)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
        return
    click.echo(f"Deleted artifact {name}")


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
    from lore.api import add_board_message
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    try:
        result = add_board_message(project_root, entity_id, message, sender)
    except ValueError as exc:
        msg = str(exc)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        # Envelope DROPS the `ok` wrapper (amendment Review Ledger CHANGED row).
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
@click.argument("entity_id")
@click.argument("message_id", type=int)
@click.pass_context
def board_delete(ctx, entity_id, message_id):
    """Delete a board message by its integer ID, scoped to ENTITY_ID."""
    from lore.api import delete_board_message
    project_root = ctx.obj["project_root"]
    json_mode = ctx.obj.get("json", False)

    try:
        result = delete_board_message(project_root, entity_id, message_id)
    except ValueError as exc:
        msg = str(exc)
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
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


@watcher.command(
    "list",
    help=_list_doc("List all watcher definitions.", "team-a/nightly-triggers"),
)
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.option("--filter", "filter_groups", multiple=True, help=_FILTER_OPT_HELP)
@click.argument("extra_filters", nargs=-1)
@click.pass_context
def watcher_list(ctx, json_mode, filter_groups, extra_filters):
    from lore.api import _watcher as watcher_module

    project_root = ctx.obj["project_root"]
    # Honour both the local --json flag and the global --json flag
    json_mode = json_mode or ctx.obj.get("json", False)

    combined_filters = list(filter_groups) + list(extra_filters)
    watchers = watcher_module.list_watchers(project_root, filter_groups=combined_filters if combined_filters else None)

    if json_mode:
        watchers_json = [
            {**w, "group": _group_for_json(w.get("group", ""))} for w in watchers
        ]
        click.echo(json.dumps({"watchers": watchers_json}))
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
    from lore.api import _watcher as watcher_module

    project_root = ctx.obj["project_root"]
    json_mode = json_mode or ctx.obj.get("json", False)

    try:
        data = watcher_module.read_watcher(project_root, name)
    except ValueError as exc:
        if json_mode:
            click.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            click.echo(str(exc), err=True)
        ctx.exit(1)
        return

    if data is None:
        msg = f'Watcher "{name}" not found.'
        if json_mode:
            click.echo(json.dumps({"error": msg}), err=True)
        else:
            click.echo(msg, err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(data))
    else:
        filepath = watcher_module._find_watcher(project_root, name)
        click.echo(filepath.read_text(), nl=False)


@watcher.command(
    "new",
    help=_new_doc(
        "Create a new watcher definition.",
        resource="watcher",
        root=".lore/watchers/",
        example="lore watcher new nightly --group team-a/nightly-triggers -f w.yaml",
    ),
)
@click.argument("name")
@click.option("--from", "-f", "from_file", default=None, help="Read content from file instead of stdin.")
@click.option(
    "--group",
    default=None,
    help=_group_opt_help(".lore/watchers/", "team-a/nightly-triggers"),
)
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.pass_context
def watcher_new(ctx, name, from_file, group, json_mode):
    from lore.api import _watcher as watcher_module

    project_root = ctx.obj["project_root"]
    json_mode = json_mode or ctx.obj.get("json", False)

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

    # Schema validation delegates to lore.schemas
    try:
        _wdata = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        click.echo(f"Invalid YAML content: {exc}", err=True)
        ctx.exit(1)
        return
    if not isinstance(_wdata, dict):
        click.echo("Watcher YAML must be a mapping", err=True)
        ctx.exit(1)
        return
    try:
        watcher_module._validate_yaml(_wdata)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(1)
        return

    try:
        result = watcher_module.create_watcher(project_root, name, content, group=group)
    except ValueError as exc:
        click.echo(str(exc), err=True)
        ctx.exit(1)
        return

    if json_mode:
        click.echo(json.dumps(result))
    else:
        suffix = f" (group: {group})" if group else ""
        click.echo(f"Created watcher {name}{suffix}")


@watcher.command("edit")
@click.argument("name")
@click.option("--from", "-f", "from_file", default=None, help="Read content from file instead of stdin.")
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.option("--set", "set_kvs", multiple=True, help="Set frontmatter field KEY=VALUE.")
@click.option("--unset", "unset_keys", multiple=True, help="Remove frontmatter field KEY.")
@click.option("--add", "add_kvs", multiple=True, help="Append to list-typed field KEY=VALUE.")
@click.option("--remove", "remove_kvs", multiple=True, help="Remove from list-typed field KEY=VALUE.")
@click.pass_context
def watcher_edit(ctx, name, from_file, json_mode, set_kvs, unset_keys, add_kvs, remove_kvs):
    """Update an existing watcher definition in place.

    Field-edit mode (mutually exclusive with -f / --from):
      --set    KEY=VALUE   set a frontmatter field
      --unset  KEY         remove a frontmatter field
      --add    KEY=VALUE   append to a list-typed field
      --remove KEY=VALUE   remove a value from a list-typed field
    """
    from lore.api import _watcher as watcher_module

    project_root = ctx.obj["project_root"]
    json_mode = json_mode or ctx.obj.get("json", False)

    if _reject_mutex(ctx, json_mode, from_file, set_kvs, unset_keys, add_kvs, remove_kvs):
        return

    field_mode = bool(set_kvs or unset_keys or add_kvs or remove_kvs)
    if field_mode:
        result = _dispatch_field_edit(
            ctx, "watcher", name, set_kvs, unset_keys, add_kvs, remove_kvs
        )
        if result is None:
            return
        if json_mode:
            click.echo(json.dumps(result))
            return
        click.echo(f"Updated watcher {name}")
        return

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
        result = watcher_module.update_watcher(project_root, name, content)
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
    from lore.api import _watcher as watcher_module

    project_root = ctx.obj["project_root"]
    json_mode = json_mode or ctx.obj.get("json", False)

    try:
        result = watcher_module.delete_watcher(project_root, name)
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


_VALID_SCOPES = ("codex", "artifacts", "doctrines", "knights", "watchers", "schemas", "glossary", "bindings")


@main.command("health")
@click.option(
    "--scope",
    "scope",
    multiple=True,
    type=click.Choice(list(_VALID_SCOPES)),
    help="Limit audit to specific entity types (space-separated, e.g. --scope codex knights schemas).",
)
@click.argument("extra_scopes", nargs=-1)
@click.option("--json", "json_mode", is_flag=True, help="Output as JSON.")
@click.pass_context
def health_cmd(ctx, scope, extra_scopes, json_mode):
    """Audit all six file-based entity types and report issues."""
    import datetime

    from lore.api import _health as _health_mod
    project_root = ctx.obj["project_root"]
    json_mode = json_mode or ctx.obj.get("json", False)

    combined = list(scope) + list(extra_scopes)
    active_scope = combined if combined else None
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H-%M-%S"
    )

    try:
        report = _health_mod.health_check(
            project_root,
            scope=active_scope,
            write_report=True,
            timestamp=timestamp,
        )
    except ValueError as exc:
        # Translate health_check's "Unknown scope: ..." to the historic
        # CLI-visible "Invalid scope: ..." text.
        msg = str(exc)
        if msg.startswith("Unknown scope:"):
            msg = "Invalid scope:" + msg[len("Unknown scope:"):]
        click.echo(msg, err=True)
        ctx.exit(1)
        return

    schemas_ran = report.schemas_ran

    if json_mode:
        import dataclasses

        issues_data = [dataclasses.asdict(i) for i in report.issues]
        click.echo(json.dumps({"has_errors": report.has_errors, "issues": issues_data}))
        if report.has_errors:
            ctx.exit(1)
        return

    schema_issues = [i for i in report.issues if i.check == "schema"]
    other_issues = [i for i in report.issues if i.check != "schema"]

    if not report.issues:
        click.echo("Health check passed. No issues found.")
    else:
        for issue in other_issues:
            click.echo(
                f"{issue.severity.upper()}  {issue.entity_type}  {issue.id}  "
                f"{issue.check}: {issue.detail}"
            )

    for issue in schema_issues:
        for line in (
            f"ERROR {issue.id}",
            f"  kind: {issue.entity_type}",
            f"  schema: {issue.schema_id}",
            f"  rule: {issue.rule}",
            f"  path: {issue.pointer}",
            f"  message: {issue.detail}",
        ):
            click.echo(line)

    # Summary line is always emitted when the schemas scope ran. Emit both a
    # per-violation and a per-file count when they differ, because different
    # PRD scenarios count differently (Scenario 5 counts violations, Scenario 4
    # counts files).
    if schemas_ran:
        def _summary(count: int) -> str:
            return f"Schema validation: {count} {'error' if count == 1 else 'errors'}"

        n = len(schema_issues)
        click.echo(_summary(n))
        files = len({i.id for i in schema_issues})
        if files != n:
            click.echo(_summary(files))

    if report.has_errors:
        ctx.exit(1)


if __name__ == "__main__":
    main()
