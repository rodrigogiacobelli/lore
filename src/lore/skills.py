"""The skill catalogue and the access-mode renderer.

Two things live here, both driven by shipped data:

* the catalogue (``src/lore/defaults/skills-catalogue.yaml``) — which skills a
  release ships, which family each belongs to, and where every retired skill
  went. A skill's description is authored once in its own ``SKILL.md``
  frontmatter and is deliberately not repeated in the catalogue.
* ``render`` — the access-mode block selector. Each skill is authored once with
  both command layers marked inline, and the project's chosen mode is injected
  at install time, so the two variants cannot drift apart.

Like ``lore.agents``, the catalogue is package data read through
``importlib.resources`` and cached for the process: ``lore init`` runs where no
``.lore/`` exists, and ``click.Choice`` needs the family token set at import
time. ``lore.schemas`` is imported inside the loader for the same reason, and
reaches for ``load_schema`` rather than an overlay-capable resolver because this
file ships inside the wheel (decisions-018-overlays-are-path-discovered-config).
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from importlib import resources
from typing import Any, Iterable

import jsonschema
import yaml

from lore.initplan import AccessMode, AgentTarget, DesiredFile

PACKAGED_CATALOGUE = "src/lore/defaults/skills-catalogue.yaml"
"""Where the catalogue is authored — quoted in the build-defect message."""

ALL_FAMILIES = "all"
NO_FAMILIES = "none"

LORE_SKILLS_ROOT = ".lore/skills"
"""Where skills land for an agent with no native skills directory, and for a
project that selected no agent at all. Repo-root-relative POSIX, because that
is the form the install manifest stores."""

OWNED_KIND = "owned"
"""Lore writes the whole file — the only kind a skill file is ever installed as."""

SKILL_FILE = "SKILL.md"
_REFERENCES_DIR = "references"

_RESOURCE_PACKAGE = "lore.defaults"
_RESOURCE_NAME = "skills-catalogue.yaml"
_SCHEMA_KIND = "skill-catalogue"


@dataclass(frozen=True)
class Retirement:
    """Where a retired skill went, and why."""

    into: str
    reason: str
    """Quoted verbatim in the removal report."""


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------


def _read_catalogue_payload() -> Any:
    """Parse the packaged catalogue file.

    The single read step, so a test can inject a payload without touching the
    shipped file.
    """
    text = resources.files(_RESOURCE_PACKAGE).joinpath(_RESOURCE_NAME).read_text(encoding="utf-8")
    return yaml.safe_load(text)


def _build_defect(reason: str) -> RuntimeError:
    """A shipped file that will not load is a build defect, never a user error."""
    return RuntimeError(f"{PACKAGED_CATALOGUE}: {reason}")


@functools.lru_cache(maxsize=1)
def load_catalogue() -> dict[str, Any]:
    """Return the parsed, schema-checked catalogue.

    Raises ``RuntimeError`` naming the packaged file when it does not parse or
    does not validate — a release that cannot say which skills it ships cannot
    install any of them.
    """
    # Imported here, not at module level, for the same reason as in lore.agents:
    # click.Choice needs the family token set at import time. ``load_schema``
    # rather than a resolver, so no project overlay reaches a file in the wheel.
    from lore.schemas import load_schema

    try:
        payload = _read_catalogue_payload()
    except yaml.YAMLError as exc:
        raise _build_defect(f"invalid YAML: {exc}") from exc

    if not isinstance(payload, dict):
        raise _build_defect("catalogue must be a mapping")

    validator = jsonschema.Draft202012Validator(load_schema(_SCHEMA_KIND))
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
    if errors:
        detail = "; ".join(
            f"/{'/'.join(str(part) for part in err.absolute_path)}: {err.message}"
            for err in errors
        )
        raise _build_defect(f"does not match the {_SCHEMA_KIND} schema — {detail}")

    return payload


@functools.lru_cache(maxsize=1)
def family_ids() -> tuple[str, ...]:
    """Return every family id, sorted. This is the concrete half of ``--skills``."""
    return tuple(sorted(load_catalogue()["families"]))


def _require_known_family(token: str, *, aggregates_ok: bool) -> None:
    """Raise ``ValueError`` naming *token* and the accepted set when it is unknown."""
    if token in family_ids():
        return
    if aggregates_ok and token in (ALL_FAMILIES, NO_FAMILIES):
        return
    accepted = list(family_ids())
    if aggregates_ok:
        accepted += [ALL_FAMILIES, NO_FAMILIES]
    raise ValueError(
        f"Unknown skill family: '{token}'. Accepted tokens: {', '.join(accepted)}."
    )


def resolve_families(tokens: Iterable[str]) -> tuple[str, ...]:
    """Expand ``--skills`` / ``skill_families`` tokens into concrete family ids.

    ``all`` expands to every family and ``none`` to no family at all; ``none``
    wins when both appear. Anything else is taken as a family id, and the result
    is sorted and deduplicated so two spellings of one selection produce one
    answer.

    The aggregates resolve here rather than in ``cli.py`` so that
    ``plan_init(skill_families=["all"])`` and ``--skills all`` are the same call
    (decisions-011-api-parity-with-cli).

    Raises ``ValueError`` naming the offending token and the accepted set.
    """
    requested = list(tokens)
    for token in requested:
        _require_known_family(token, aggregates_ok=True)

    if NO_FAMILIES in requested:
        return ()
    if ALL_FAMILIES in requested:
        return family_ids()
    return tuple(sorted(set(requested)))


def skills_in_families(families: Iterable[str]) -> tuple[str, ...]:
    """Return the catalogue's skill ids for *families*, in catalogue order.

    Takes concrete family ids — ``resolve_families`` has already expanded any
    aggregate. Raises ``ValueError`` naming the offending token when a family is
    unknown.
    """
    selected = set()
    for family in families:
        _require_known_family(family, aggregates_ok=False)
        selected.add(family)

    return tuple(
        entry["id"] for entry in load_catalogue()["skills"] if entry["family"] in selected
    )


def retirement_for(skill_id: str) -> Retirement | None:
    """Return where *skill_id* went, or None when it is current or unknown."""
    record = load_catalogue().get("retired", {}).get(skill_id)
    if record is None:
        return None
    return Retirement(into=record["into"], reason=record["reason"])


# ---------------------------------------------------------------------------
# The access-mode renderer
# ---------------------------------------------------------------------------


_MARKER_RE = re.compile(r"^<!--\s*lore:access\s+(\S+)\s*-->$")
_END = "end"
_MODE_TOKENS = frozenset(mode.value for mode in AccessMode)
_EXPECTED_TOKENS = ", ".join(f"'{mode.value}'" for mode in AccessMode) + f" or '{_END}'"


def render(text: str, mode: AccessMode, source: str | None = None) -> str:
    """Resolve the ``<!-- lore:access ... -->`` blocks in *text* for *mode*.

    Text outside every block is unconditional — which is where a command no file
    tool reproduces (``lore codex map``, ``lore codex chaos``, ``lore impacts``)
    is authored, so no third "both" token is needed. Text inside a block
    survives only when the block names the selected mode; a block that does not
    is dropped whole, its two marker lines included.

    Pure string in, string out: the caller reads the file and writes the result.
    *source* is used only in error messages — pass the path when there is one.

    Raises ``ValueError`` naming the source and the line for an unterminated
    block, an unknown mode token, an ``end`` with no opener, or a nested opener.
    """
    selected = AccessMode(mode).value
    where = source or "<text>"

    kept: list[str] = []
    open_token: str | None = None
    open_line = 0

    for lineno, line in enumerate(text.splitlines(keepends=True), start=1):
        match = _MARKER_RE.match(line.strip())

        if match is None:
            if open_token is None or open_token == selected:
                kept.append(line)
            continue

        token = match.group(1)

        if token == _END:
            if open_token is None:
                raise ValueError(
                    f"{where}:{lineno}: <!-- lore:access end --> with no open block"
                )
            open_token = None
            continue

        if token not in _MODE_TOKENS:
            raise ValueError(
                f"{where}:{lineno}: unknown access-mode token '{token}' — "
                f"expected {_EXPECTED_TOKENS}"
            )

        if open_token is not None:
            raise ValueError(
                f"{where}:{lineno}: nested <!-- lore:access {token} --> block; "
                "access blocks never nest"
            )

        open_token = token
        open_line = lineno

    if open_token is not None:
        raise ValueError(
            f"{where}:{open_line}: unterminated <!-- lore:access {open_token} --> block"
        )

    return "".join(kept)


# ---------------------------------------------------------------------------
# Where skills install, and what bytes land there
# ---------------------------------------------------------------------------


def install_roots(targets: Iterable[AgentTarget]) -> tuple[str, ...]:
    """Return the directories skills install into, deduplicated and sorted.

    Tech Spec §7.5 in four rows: an agent with a native skills directory
    receives them there; an agent without one, and a project that selected no
    agent at all, receives them in ``.lore/skills/``. A project using both kinds
    gets both directories, which costs duplicated bytes and buys a working setup
    for each — the manifest tracks the two copies independently, so deselecting
    one agent removes only its copy.
    """
    selected = tuple(targets)
    roots = {target.skills_dir for target in selected if target.skills_dir}
    if not selected or any(target.skills_dir is None for target in selected):
        roots.add(LORE_SKILLS_ROOT)
    return tuple(sorted(roots))


def skill_files(skill_id: str) -> tuple[str, ...]:
    """Return one skill's packaged files, as paths relative to its directory.

    ``SKILL.md`` always, plus whatever reference files the catalogue declares.
    """
    entry = next(
        (row for row in load_catalogue()["skills"] if row["id"] == skill_id), None
    )
    if entry is None:
        raise ValueError(f"Unknown skill: '{skill_id}'.")
    references = entry.get("references") or []
    return (SKILL_FILE, *(f"{_REFERENCES_DIR}/{name}" for name in references))


def _read_packaged(skill_id: str, relative: str) -> str:
    """Read one packaged skill file as text."""
    return (
        resources.files(_RESOURCE_PACKAGE)
        .joinpath(f"skills/{skill_id}/{relative}")
        .read_text(encoding="utf-8")
    )


def unresolved_marker(text: str) -> str | None:
    """The first access-block marker still standing in *text*, or ``None``.

    ``render`` consumes every one of these, so nothing it returns can carry one:
    this is the question "was this text rendered?" asked of output rather than
    of input. `lore health` uses it to tell a half-converted install from an
    ordinary edit, which a digest comparison reports identically.

    It lives beside ``render`` because the marker grammar has exactly one owner
    (``standards-single-source``) — a second regex elsewhere would be a second
    opinion about what a marker is.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if _MARKER_RE.match(stripped):
            return stripped
    return None


def rendered_bytes(skill_id: str, relative: str, access_mode: AccessMode) -> bytes:
    """The bytes an install of *skill_id*'s *relative* file would write in *access_mode*.

    The one place a packaged skill file becomes installed content. `lore init`
    reaches it through ``desired_files``; `lore health` reaches it directly, to
    ask whether a file on disk is this release's other mode — a question a
    digest comparison can only answer as "edited", and the mode is the thing the
    project most plausibly got wrong.

    Raises ``ValueError`` for an unknown skill or an unreadable packaged file,
    which for health is a broken install rather than a broken project.
    """
    source_path = f"skills/{skill_id}/{relative}"
    return render(
        _read_packaged(skill_id, relative), access_mode, source=source_path
    ).encode("utf-8")


def desired_files(
    *,
    targets: Iterable[AgentTarget],
    skill_families: Iterable[str],
    access_mode: AccessMode,
) -> dict[str, DesiredFile]:
    """Enumerate the skill files this release would write, keyed by path.

    Takes concrete family ids — ``resolve_families`` has already expanded any
    aggregate. Every packaged file goes through ``render`` exactly once, blocks
    or not, so one code path decides what an installed file says.

    Decides *what*, never *when*: nothing here touches the project, and the
    result is the ``desired`` half of the reconciliation comparison.
    """
    roots = install_roots(targets)
    selected = skills_in_families(skill_families)

    desired: dict[str, DesiredFile] = {}
    for skill_id in selected:
        for relative in skill_files(skill_id):
            content = rendered_bytes(skill_id, relative, access_mode)
            for root in roots:
                path = f"{root}/{skill_id}/{relative}"
                desired[path] = DesiredFile(
                    path=path,
                    kind=OWNED_KIND,
                    source=f"skill:{skill_id}",
                    content=content,
                )
    return desired
