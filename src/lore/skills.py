"""The skill catalogue and the skill renderer.

Everything here is driven by shipped data:

* the catalogue (``src/lore/defaults/skills-catalogue.yaml``, version 3) — which
  skills a release ships, which blocks each skill file and each instruction
  document is assembled from, the explicit line-cap exceptions, the retired
  family table the deprecated ``--skills`` alias reads, and where every retired
  skill went. A skill's description is authored once, in its head block.
* the profile renderer — :func:`installed_skills`, :func:`render_skill_file`,
  :func:`render_document` and :func:`desired_files` assemble skills and
  instruction text from tagged blocks (``lore.blocks``) for a
  :class:`~lore.initplan.Profile`. A skill with no surviving body block is
  never written, and nothing refers to it.

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
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from importlib import resources
from typing import Any, overload

import jsonschema
import yaml

import lore.blocks as blocks_module
from lore.initplan import (
    QUESTIONS,
    AgentTarget,
    DesiredFile,
    Profile,
    Route,
    question_kwarg,
)

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


def _require_skill_bodies_gated(
    catalogue: dict[str, Any], known: Mapping[str, blocks_module.Block]
) -> None:
    """A skill whose ``SKILL.md`` body holds only ``core`` blocks is a build defect.

    ``core`` survives every profile, so such a skill would install in a project
    that uses none of Lore. Checked where the blocks are first needed rather
    than in :func:`load_catalogue`, which ``click.Choice`` reaches at import
    time and must not pay for parsing every block. Block ids the shipped tree
    does not carry are left to ``lore.blocklint`` (L3): this judges only what it
    can see.
    """
    for entry in catalogue["skills"]:
        listed = [known[b] for b in entry["files"][0]["blocks"] if b in known]
        if listed and all(block.feature == "core" for block in listed):
            raise _build_defect(
                f"skill '{entry['id']}': its SKILL.md holds only core blocks, which "
                "survive every profile; gate at least one on a feature"
            )


@functools.lru_cache(maxsize=1)
def family_ids() -> tuple[str, ...]:
    """Return every legacy family id, sorted. This is the concrete half of ``--skills``."""
    return tuple(sorted(load_catalogue()["legacy_families"]))


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


def retirement_for(skill_id: str) -> Retirement | None:
    """Return where *skill_id* went, or None when it is current or unknown."""
    record = load_catalogue().get("retired", {}).get(skill_id)
    if record is None:
        return None
    return Retirement(into=record["into"], reason=record["reason"])


# ---------------------------------------------------------------------------
# Markers that can never survive assembly
# ---------------------------------------------------------------------------


_ACCESS_MARKER_RE = re.compile(r"^<!--\s*lore:access\s+(\S+)\s*-->$")
"""The marker grammar of the earlier access-mode renderer, which is gone. An
installed file carrying one is output nothing here can produce."""
_BLOCK_MARKER_PREFIXES = ("<!-- lore:block", "<!-- lore:skills-table")


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


def _skill_entry(skill_id: str) -> dict[str, Any]:
    entry = next((row for row in load_catalogue()["skills"] if row["id"] == skill_id), None)
    if entry is None:
        raise ValueError(f"Unknown skill: '{skill_id}'.")
    return entry


def _block_table() -> Mapping[str, blocks_module.Block]:
    """The shipped blocks, after the catalogue's skills have been judged against them."""
    table = blocks_module.load_blocks()
    _require_skill_bodies_gated(load_catalogue(), table)
    return table


def _surviving(
    block_ids: Sequence[str], profile: Profile, *, skills_installed: bool = False
) -> list[blocks_module.Block]:
    return blocks_module.assemble(
        block_ids, profile, blocks=_block_table(), skills_installed=skills_installed
    )


def _is_installed(entry: dict[str, Any], profile: Profile) -> bool:
    """A skill is installed when at least one body block of its SKILL.md survives."""
    return bool(_surviving(entry["files"][0]["blocks"], profile))


def installed_skills(profile: Profile) -> tuple[str, ...]:
    """The skill ids *profile* installs, in catalogue order.

    A skill is installed when at least one body block of its ``SKILL.md``
    survives. The head block never counts.
    """
    return tuple(
        entry["id"] for entry in load_catalogue()["skills"] if _is_installed(entry, profile)
    )


def skill_description(skill_id: str) -> str:
    """The one-line description in *skill_id*'s head block."""
    head = _block_table()[_skill_entry(skill_id)["head"]]
    lines = head.body.splitlines()
    fence = [i for i, line in enumerate(lines) if line.strip() == "---"]
    meta = yaml.safe_load("\n".join(lines[fence[0] + 1 : fence[1]])) if len(fence) >= 2 else None
    description = meta.get("description") if isinstance(meta, dict) else None
    if not isinstance(description, str) or not description.strip():
        raise _build_defect(f"head block '{head.id}' of skill '{skill_id}' has no description")
    return description


@overload
def skill_files(skill_id: str) -> tuple[str, ...]: ...
@overload
def skill_files(skill_id: str, profile: Profile) -> tuple[str, ...]: ...
def skill_files(skill_id: str, profile: Profile | None = None) -> tuple[str, ...]:
    """Return one skill's files, as paths relative to its directory.

    Without a profile, every file the catalogue declares (``SKILL.md`` first).
    With one, only the files that materialise: none at all when the skill is not
    installed, and a reference file only when one of its blocks survives.
    """
    entry = _skill_entry(skill_id)
    declared = tuple(row["path"] for row in entry["files"])
    if profile is None:
        return declared
    if not _is_installed(entry, profile):
        return ()
    return tuple(
        row["path"] for row in entry["files"] if _surviving(row["blocks"], profile)
    )


def render_skill_file(skill_id: str, relative: str, profile: Profile) -> str | None:
    """The text of one skill file for *profile*, or ``None`` when it is not written.

    ``SKILL.md`` is the head block, one blank line, then the joined body; a
    reference file is its joined blocks alone. ``None`` for a skill that is not
    installed and for a reference file none of whose blocks survive.
    """
    entry = _skill_entry(skill_id)
    row = next((r for r in entry["files"] if r["path"] == relative), None)
    if row is None:
        raise ValueError(f"Unknown file '{relative}' for skill '{skill_id}'.")
    if not _is_installed(entry, profile):
        return None
    survivors = _surviving(row["blocks"], profile)
    if not survivors:
        return None
    body = blocks_module.join(survivors)
    if relative != SKILL_FILE:
        return body
    return f"{_block_table()[entry['head']].body}\n\n{body}"


def render_document(name: str, profile: Profile) -> str | None:
    """The instruction document *name* (``lore-agent`` or ``getting-started``).

    ``None`` when no block survives.
    """
    documents = load_catalogue()["documents"]
    if name not in documents:
        raise ValueError(f"Unknown document: '{name}'.")
    survivors = _surviving(
        documents[name]["blocks"], profile, skills_installed=bool(installed_skills(profile))
    )
    return blocks_module.join(survivors) if survivors else None


def neighbor_profiles(profile: Profile) -> Iterator[tuple[str, Profile]]:
    """Every profile one answer away from *profile*, labelled ``<question>=<value>``.

    The route yields its other token, each yes/no its opposite: six neighbours
    in all, after normalising (a Memory opt-in flipped while Memory is off is no
    new profile). `lore health` renders a file under each to tell a file
    installed for another answer from one that was merely edited.
    """
    current = profile.as_answers()
    seen = {profile}
    for question in QUESTIONS:
        name = question_kwarg(question)
        value = current[name]
        if isinstance(value, bool):
            label, changed = str(not value).lower(), not value
        else:
            other = next(route for route in Route if route.value != value)
            label, changed = other.value, other
        neighbour = replace(profile, **{name: changed}).normalized()
        if neighbour not in seen:
            seen.add(neighbour)
            yield f"{question}={label}", neighbour


def unresolved_marker(text: str) -> str | None:
    """The first marker still standing in *text*, or ``None``.

    Covers the earlier ``<!-- lore:access -->`` grammar and the block and
    skills-table markers: a skill file carries none of them once rendered, so
    this is the question "was this text rendered?" asked of output rather than
    of input. `lore health` uses it to tell a half-converted install from an
    ordinary edit, which a digest comparison reports identically.

    It lives beside the renderer because the marker grammar has exactly one
    owner (``standards-single-source``) — a second regex elsewhere would be a
    second opinion about what a marker is.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if _ACCESS_MARKER_RE.match(stripped) or stripped.startswith(_BLOCK_MARKER_PREFIXES):
            return stripped
    return None


def rendered_bytes(skill_id: str, relative: str, profile: Profile) -> bytes | None:
    """The bytes an install of *skill_id*'s *relative* file would write for *profile*.

    ``None`` when that profile does not write the file. `lore init` reaches it
    through ``desired_files``; `lore health` reaches it directly, to ask whether
    a file on disk is another render of this release — a question a digest
    comparison can only answer as "edited".

    Raises ``ValueError`` for an unknown skill or file, which for health is a
    broken install rather than a broken project.
    """
    text = render_skill_file(skill_id, relative, profile)
    return None if text is None else text.encode("utf-8")


def desired_files(
    *, targets: Iterable[AgentTarget], profile: Profile
) -> dict[str, DesiredFile]:
    """Enumerate the skill files *profile* would write, keyed by path.

    Every installed skill's materialised files, assembled from blocks, in each
    root the targets install into. Decides *what*, never *when*: nothing here
    touches the project, and the result is the ``desired`` half of the
    reconciliation comparison.
    """
    roots = install_roots(targets)
    desired: dict[str, DesiredFile] = {}
    for skill_id in installed_skills(profile):
        for relative in skill_files(skill_id, profile):
            content = rendered_bytes(skill_id, relative, profile)
            assert content is not None
            _place(desired, roots, skill_id, relative, content)
    return desired


def _place(
    desired: dict[str, DesiredFile],
    roots: tuple[str, ...],
    skill_id: str,
    relative: str,
    content: bytes,
) -> None:
    for root in roots:
        path = f"{root}/{skill_id}/{relative}"
        desired[path] = DesiredFile(
            path=path, kind=OWNED_KIND, source=f"skill:{skill_id}", content=content
        )
