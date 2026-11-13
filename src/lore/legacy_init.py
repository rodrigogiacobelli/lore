"""Migration and deprecated-alias translation for `lore init`.

Three pure functions over the answer vocabulary in :mod:`lore.initplan`:

* :func:`profile_from_legacy` turns the pre-0.14 ``init-access-mode`` and
  ``init-skill-families`` answers into the feature answers that preserve what
  that release installed;
* :func:`profile_from_interim` does the same for the fifteen ``init-*`` keys the
  unreleased 0.14.0 build wrote (a read and a write route per file feature,
  a validate opt-in each);
* :func:`translate_aliases` does it for the deprecated ``--access`` and
  ``--skills`` flags and keywords, and says so in a notice.

Both surfaces call it (decisions-011-api-parity-with-cli), so an alias behaves
identically on the command line and in Python. Nothing here reads a file or
writes one: the values arrive as arguments and the answers leave as a return
value. Imports ``lore.initplan`` and nothing else
(standards-dependency-inversion).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from lore.initplan import Profile, Route

LEGACY_FAMILIES: tuple[str, ...] = ("machinery", "memory", "workflow")
"""The three retired skill families."""

LEGACY_FAMILY_SKILLS: dict[str, tuple[str, ...]] = {
    "memory": ("retrieve-memory", "store-memory"),
    "machinery": (
        "update-artifact",
        "update-custom-schema",
        "update-doctrine",
        "update-index",
        "update-watcher",
    ),
    "workflow": ("inquest", "start-quest", "sync-codex-guide"),
}
"""Which skill ids each retired family installed. Restates the catalogue's
``legacy_families``; a unit test pins the two together."""

_ACCESS_MODES: tuple[str, ...] = ("cli", "native")
_SKILL_PREFIX = "skill:"
_REPLACEMENT_FLAGS = "Use --route, --memory, --quests and --watchers."


@dataclass(frozen=True)
class AliasTranslation:
    """What a deprecated alias means in the new vocabulary."""

    answers: dict[str, Route | bool]
    """Keyword name to value. Only the route for ``--access`` alone, complete for ``--skills``."""

    notices: tuple[str, ...]
    """One sentence per alias used, naming its replacement."""


def profile_from_legacy(access_mode: str, families: Sequence[str]) -> Profile:
    """The profile that preserves what ``access_mode`` and ``families`` installed.

    The family ``memory`` is Memory with search, index and graph (the old
    instruction text always taught them); ``workflow`` is Quests & Missions;
    ``machinery`` is the core plus Watchers (Doctrines and Artifacts are core
    now, so they are on whatever the families say).

    The one route follows the access mode (``native`` is the harness, ``cli`` the
    CLI), with one exception: a project with no ``memory`` family but with
    ``machinery`` or ``workflow`` keeps the CLI, because those skills always
    used it and the access mode only ever described Memory.

    Raises ``ValueError`` for an unknown access mode or family.
    """
    if access_mode not in _ACCESS_MODES:
        raise ValueError(
            f"Unknown access mode: '{access_mode}'. Accepted tokens: {', '.join(_ACCESS_MODES)}."
        )
    unknown = [family for family in families if family not in LEGACY_FAMILIES]
    if unknown:
        raise ValueError(
            f"Unknown skill family: '{unknown[0]}'. Accepted tokens: {', '.join(LEGACY_FAMILIES)}."
        )
    memory, machinery, workflow = (
        "memory" in families,
        "machinery" in families,
        "workflow" in families,
    )
    if not memory and (machinery or workflow):
        route = Route.CLI
    else:
        route = Route.HARNESS if access_mode == "native" else Route.CLI
    return Profile(
        route=route,
        memory=memory,
        memory_search=memory,
        memory_index=memory,
        memory_graph=memory,
        quests=workflow,
        watchers=machinery,
    )


def profile_from_interim(
    interim: Mapping[str, object], *, memory_index: bool, memory_graph: bool, quests: bool
) -> Profile:
    """The profile the unreleased 0.14.0 build's fifteen answers mean.

    *interim* holds the usable route keys the project recorded (``"off"``,
    ``"harness"`` or ``"cli"``); an absent one takes that build's default
    (Memory ``harness``, the rest ``cli``). The validate keys carry nothing
    forward: ``lore health`` is core now. *memory_index*, *memory_graph* and
    *quests* are the same-named keys, which kept their meaning.

    Memory is on when either of its routes was not off; search is on when its
    read route was the CLI (that route is where search lived); watchers are on
    when either of theirs was not off; the one route is ``cli`` when any route
    that was on had been ``cli``, else ``harness``.
    """

    def route_of(feature: str, action: str) -> str:
        default = "harness" if feature == "memory" else "cli"
        value = interim.get(f"init-{feature}-{action}", default)
        return str(value)

    routes = {
        (feature, action): route_of(feature, action)
        for feature in ("memory", "doctrines", "artifacts", "watchers")
        for action in ("read", "write")
    }
    memory = routes[("memory", "read")] != "off" or routes[("memory", "write")] != "off"
    watchers = routes[("watchers", "read")] != "off" or routes[("watchers", "write")] != "off"
    route = Route.CLI if "cli" in routes.values() else Route.HARNESS
    return Profile(
        route=route,
        memory=memory,
        memory_search=memory and routes[("memory", "read")] == "cli",
        memory_index=memory and memory_index,
        memory_graph=memory and memory_graph,
        quests=quests,
        watchers=watchers,
    )


def infer_families(recorded_skill_ids: Iterable[str]) -> tuple[str, ...]:
    """The families an install manifest's recorded skills imply, sorted.

    Accepts a bare skill id or the manifest's ``skill:<id>`` source form; ids no
    family installed are ignored.
    """
    ids = {value.removeprefix(_SKILL_PREFIX) for value in recorded_skill_ids}
    return tuple(
        sorted(
            family
            for family, skill_ids in LEGACY_FAMILY_SKILLS.items()
            if ids & set(skill_ids)
        )
    )


def translate_aliases(
    *,
    access_mode: str | None,
    skill_families: Sequence[str] | None,
    current_route: Route,
) -> AliasTranslation:
    """Translate ``--access`` / ``--skills`` into feature answers and notices.

    ``--access`` alone sets only the route. ``--skills`` yields the complete
    legacy profile, in the mode ``--access`` names, else the mode the project's
    current route implies. *skill_families* arrives already expanded: ``all``
    and ``none`` are resolved by the caller.
    """
    answers: dict[str, Route | bool] = {}
    notices: list[str] = []

    if skill_families is not None:
        mode = access_mode or ("cli" if current_route is Route.CLI else "native")
        profile = profile_from_legacy(mode, skill_families)
        answers.update(
            {
                name: (Route(value) if name == "route" else value)
                for name, value in profile.as_answers().items()
            }
        )
        named = " ".join(skill_families) or "none"
        notices.append(
            f"--skills {named} is deprecated: it sets {profile.summary()}. {_REPLACEMENT_FLAGS}"
        )

    if access_mode is not None:
        route = Route.HARNESS if access_mode == "native" else Route.CLI
        if skill_families is None:
            answers["route"] = route
        notices.append(
            f"--access {access_mode} is deprecated: it sets --route {route.value}."
        )

    return AliasTranslation(answers=answers, notices=tuple(notices))
