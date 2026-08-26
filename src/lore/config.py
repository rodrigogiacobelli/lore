"""Project configuration loader for ``.lore/config.toml``.

Spec: ``glossary-us-003``. Internal module — ``Config`` is intentionally
NOT exported via :mod:`lore.models` ``__all__`` per FR-14 / ADR-010
(public-API stability). Promote only when Realm asks.

Single responsibility: parse ``.lore/config.toml`` and return a typed,
frozen :class:`Config` dataclass. Failure modes always fall back to
:data:`DEFAULT_CONFIG` and emit at most one stderr warning per process.

Standards:
  * ``standards-single-responsibility`` — this module owns project-config
    loading exclusively.
  * ``standards-dependency-inversion`` — depends only on stdlib
    (:mod:`tomllib`) and :mod:`lore.paths`.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from lore.paths import config_path


# ---------------------------------------------------------------------------
# TOML key → dataclass attribute mapping
# ---------------------------------------------------------------------------
#
# Single source of truth for every known root-level setting. To add a new
# setting:
#   1. add a typed field to :class:`Config` with its default value;
#   2. add one entry to :data:`_FROM_TOML` mapping the kebab-case TOML key to
#      the snake_case attribute name;
#   3. add one entry to :data:`_EXPECTED_TYPE` naming the accepted Python type;
#   4. (constrained strings only) add one entry to :data:`_ALLOWED_VALUES`
#      listing every accepted token, in the order the warning should print;
#   5. (list-typed keys only) add one entry to :data:`_ALLOWED_ITEM_VALUES`
#      returning the tokens each item may take;
#   6. add one entry to :data:`_KEY_DOC` describing the key in a line.
#
# The comment block `lore init` writes above the settings is generated from
# those tables by :func:`render_known_keys_header`, so a project initialised
# before a key existed learns about it on its next `lore init` and no header
# text is ever hand-copied (``standards-dry``).
#
# Unknown root keys (and nested tables) are preserved verbatim in
# ``Config.extras`` for forward compatibility — never silently dropped.

_FROM_TOML: dict[str, str] = {
    "show-glossary-on-codex-commands": "show_glossary_on_codex_commands",
    "health-report-retention": "health_report_retention",
    "init-agents": "init_agents",
    "init-access-mode": "init_access_mode",
    "init-skill-families": "init_skill_families",
    "init-skills-gitignore": "init_skills_gitignore",
}

# Accepted Python type per known key. A value of any other type is rejected
# with a one-time ``invalid type ... (expected <name>)`` warning and the key
# falls back to its default.
_EXPECTED_TYPE: dict[str, type] = {
    "show-glossary-on-codex-commands": bool,
    "health-report-retention": str,
    "init-agents": list,
    "init-access-mode": str,
    "init-skill-families": list,
    "init-skills-gitignore": str,
}

# Accepted tokens for constrained string keys. Keys absent from this table
# take any value of the right type.
_ALLOWED_VALUES: dict[str, tuple[str, ...]] = {
    "health-report-retention": ("none", "latest", "all"),
    "init-access-mode": ("cli", "native"),
    "init-skills-gitignore": ("lore-only", "none", "all"),
}

# Accepted tokens for each *item* of a list-typed key. Held as callables rather
# than tuples because both sets are shipped data — the agent registry and the
# skill catalogue — and resolving them at import time would make every `lore`
# invocation parse two packaged YAML files to load a config it may not read.
#
# A list holding one unknown token drops the WHOLE key to its default, which is
# fail-soft parity with the scalar path: half a selection is not a selection.
# `init-skill-families` never accepts the aggregates `all` and `none`; those
# resolve in `skills.resolve_families` before anything is persisted.
def _agent_ids() -> tuple[str, ...]:
    from lore.agents import agent_ids

    return agent_ids()


def _family_ids() -> tuple[str, ...]:
    from lore.skills import family_ids

    return family_ids()


_ALLOWED_ITEM_VALUES: dict[str, Callable[[], tuple[str, ...]]] = {
    "init-agents": _agent_ids,
    "init-skill-families": _family_ids,
}

# One line of prose per known key, rendered under its row in the generated
# header. A key's type, token set and default are already in the tables above
# and are never restated here — this says what the setting is *for*. A value
# may span several lines when each accepted token needs its own gloss.
_KEY_DOC: dict[str, str] = {
    "show-glossary-on-codex-commands": (
        "append a ## Glossary block to `lore codex show` output"
    ),
    "health-report-retention": (
        "none   - lore health writes no report file (console/API output only)\n"
        "latest - keep only the newest report, pruning older ones\n"
        "all    - keep every report"
    ),
    "init-agents": (
        "which coding agents `lore init` installs skills and instructions for"
    ),
    "init-access-mode": (
        "whether skills tell agents to use the Lore CLI or their own file tools"
    ),
    "init-skill-families": "which seeded skill families `lore init` installs",
    "init-skills-gitignore": "how the installed skills are tracked in git",
}


# ---------------------------------------------------------------------------
# Public (within-package) types
# ---------------------------------------------------------------------------


DEFAULT_SKILL_FAMILIES: tuple[str, ...] = ("memory", "machinery", "workflow")
"""The non-interactive default for ``init-skill-families``.

Every family, so a deployment depending on a machinery skill keeps it across an
upgrade. The interactive checkbox preselects a smaller set; that is a CLI-layer
concern and never reaches this file (Tech Spec §9.2).
"""


@dataclass(frozen=True)
class Config:
    """Typed, immutable view of ``.lore/config.toml``.

    Attributes:
        show_glossary_on_codex_commands: Whether ``lore codex show`` should
            auto-surface a glossary footer. Default ``True``.
        health_report_retention: How ``lore health`` persists its markdown
            report — ``"none"`` (write nothing), ``"latest"`` (keep only the
            newest report) or ``"all"`` (keep every report). Default
            ``"none"``: no local persistence.
        init_agents: Which coding agents ``lore init`` installs skills and
            instructions for. Default ``[]`` — no agent, skills to
            ``.lore/skills/``. This default is reached only when the key is
            *present* and empty: an absent key means the project has never
            answered, and ``init.plan_init`` derives the selection from what
            the project holds rather than taking a silence as "deselect every
            agent and uninstall the lot".
        init_access_mode: Whether installed skills tell an agent to use the
            Lore CLI (``"cli"``) or its own file tools (``"native"``). Default
            ``"native"``.
        init_skill_families: Which seeded skill families install. Default is
            every family, so a deployment that depends on one keeps it across
            an upgrade.
        init_skills_gitignore: How the installed skills are tracked in git —
            ``"lore-only"``, ``"none"`` or ``"all"``. Default ``"lore-only"``.

    The four ``init_*`` fields are read by ``init.plan_init`` and by nothing
    else (ADR-021 constraint 2): a second reader of a command-scoped key is a
    duplicate implementation and an ADR-011 violation.
        extras: Forward-compatibility bucket. Any root-level key not listed
            in :data:`_FROM_TOML` (including whole TOML tables) is preserved
            here verbatim, so projects that adopt a newer ``config.toml``
            against an older Lore release still parse cleanly.
    """

    show_glossary_on_codex_commands: bool = True
    health_report_retention: str = "none"
    init_agents: list[str] = field(default_factory=list)
    init_access_mode: str = "native"
    init_skill_families: list[str] = field(
        default_factory=lambda: list(DEFAULT_SKILL_FAMILIES)
    )
    init_skills_gitignore: str = "lore-only"
    extras: Mapping[str, object] = field(default_factory=dict)


DEFAULT_CONFIG = Config()


# ---------------------------------------------------------------------------
# Per-process warning latch
# ---------------------------------------------------------------------------
#
# Module-level boolean (NOT thread-local, NOT per-call). Once a parse error
# or wrong-type warning is emitted, no further config warning fires for the
# remaining lifetime of the Python process. Tests reset ``_warned`` directly
# via an autouse fixture; production code must never touch it.

_warned: bool = False

_UNREADABLE = (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError)
"""Every way ``.lore/config.toml`` fails to yield a table, as one tuple.

Malformed TOML is only one of them. ``tomllib`` decodes the file itself, so
bytes that are not UTF-8 raise ``UnicodeDecodeError`` before any parsing
happens, and a directory in the place of the file raises ``IsADirectoryError``
when it is opened. All three mean the same thing to a caller — there is nothing
to read — and all three take the same fail-soft branch. Held here so
:func:`load_config` and :func:`recorded_keys` cannot drift apart on what counts
as unreadable.
"""


def _warn_once(msg: str) -> None:
    """Emit ``msg`` to stderr at most once per process.

    Side effect: flips the module-level ``_warned`` latch. Subsequent calls
    (for any warning kind) become no-ops. Idempotent stderr per FR-Reliability.
    """
    global _warned
    if _warned:
        return
    _warned = True
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(root: Path) -> Config:
    """Load ``<root>/.lore/config.toml`` into a :class:`Config`.

    Fail-soft contract:
      * Missing file → :data:`DEFAULT_CONFIG`, no stderr.
      * Malformed TOML, bytes that are not UTF-8, or a file that cannot be
        opened at all → :data:`DEFAULT_CONFIG` and a one-time
        ``lore: invalid config at <path>: <reason> (using defaults)`` stderr
        line. The path is in the message because the reason on its own — a
        decoder's byte offset — names no file.
      * Known key with wrong type → that key falls back to its default
        and emits a one-time
        ``lore: invalid type for <key> at <path> (expected <type>); using default``
        stderr line; other keys parse normally.
      * Constrained string key with an out-of-set value → that key falls back
        to its default and emits a one-time
        ``lore: invalid value for <key> at <path> (expected one of: ...); using default``
        stderr line; other keys parse normally.
      * List-typed key holding an item outside its token set (or an item that
        is not a string) → the **whole** key falls back to its default and
        emits a one-time
        ``lore: invalid value for <key> at <path> (expected items from: ...); using default``
        stderr line. Half a selection is not a selection.
      * Unknown root keys / tables → preserved in :attr:`Config.extras`.
    """
    return _read(root, warn=True)[0]


def recorded_keys(root: Path) -> frozenset[str]:
    """Return the known keys ``<root>/.lore/config.toml`` answers.

    Presence **and** validity. A caller that needs to know whether a project
    has already answered a question cannot learn it from :func:`load_config`,
    because a recorded answer that happens to equal the built-in default is
    indistinguishable from an absent one there — but "the key is in the file"
    is not the answer either, because :func:`load_config` is fail-soft and
    throws away a value it cannot use.

    Asking only about presence made those two functions disagree about exactly
    one thing, and it was the destructive one: ``init-agents = 42`` counted as
    an answer while the value it resolved to was the built-in ``[]``, which is
    the empty selection that uninstalls Lore's skills from every agent
    directory. A config Lore cannot understand must never authorise that, so
    the rule is one line: **a value the loader could not use is not an
    answer**, and both functions read it off the same parse.

    Fail-soft like :func:`load_config` and silent: an absent or unparseable
    file has recorded nothing, and the warning for a broken file belongs to
    the load that reads its values.
    """
    return _read(root, warn=False)[1]


def _read(root: Path, *, warn: bool) -> tuple[Config, frozenset[str]]:
    """Parse the config once, returning the values **and** the keys it answers.

    The single parse behind :func:`load_config` and :func:`recorded_keys`. Two
    parses were two notions of what a key says, and the pair that mattered was
    "this key is set" against "this key's value is usable".

    *warn* is what keeps :func:`recorded_keys` silent: the stderr line about a
    broken file belongs to the load that reads its values, and both functions
    firing it would say the same thing twice or say it in the wrong order.
    """
    path = config_path(root)
    if not path.exists():
        return DEFAULT_CONFIG, frozenset()

    try:
        with path.open("rb") as fp:
            data = tomllib.load(fp)
    except _UNREADABLE as exc:
        if warn:
            _warn_once(f"lore: invalid config at {path}: {exc} (using defaults)")
        return DEFAULT_CONFIG, frozenset()

    # ``Any`` (not ``object``): the values are splatted into :class:`Config`,
    # whose fields have heterogeneous types.
    kwargs: dict[str, Any] = {}
    extras: dict[str, object] = {}
    answered: set[str] = set()
    for key, value in data.items():
        attr = _FROM_TOML.get(key)
        if attr is None:
            extras[key] = value
            continue
        problem = _unusable_reason(key, value, path)
        if problem is not None:
            if warn:
                _warn_once(problem)
            continue
        kwargs[attr] = value
        answered.add(key)
    return Config(extras=extras, **kwargs), frozenset(answered)


def _unusable_reason(key: str, value: object, path: Path) -> str | None:
    """The stderr line for a value the loader cannot use, or ``None`` when it can.

    The whole of "is this a usable value" in one place, because both halves of
    :func:`_read` ask it — the values half to fall back to the default, the
    keys half to leave the key out of the answered set:

      * wrong type → ``invalid type for <key> at <path> (expected <type>)``;
      * constrained string outside its token set → ``invalid value for <key> at
        <path> (expected one of: ...)``;
      * list-typed key holding an item outside its token set, or an item that
        is not a string → the same wording with ``expected items from``, for
        the **whole** key. Half a selection is not a selection.
    """
    expected = _EXPECTED_TYPE[key]
    if not isinstance(value, expected):
        return (
            f"lore: invalid type for {key} at {path} "
            f"(expected {expected.__name__}); using default"
        )
    allowed = _ALLOWED_VALUES.get(key)
    if allowed is not None and value not in allowed:
        return (
            f"lore: invalid value for {key} at {path} "
            f"(expected one of: {', '.join(allowed)}); using default"
        )
    allowed_items = _ALLOWED_ITEM_VALUES.get(key)
    if allowed_items is not None:
        accepted = allowed_items()
        if any(item not in accepted for item in value):
            return (
                f"lore: invalid value for {key} at {path} "
                f"(expected items from: {', '.join(accepted)}); using default"
            )
    return None


# ---------------------------------------------------------------------------
# Rendering `.lore/config.toml`
# ---------------------------------------------------------------------------


def render_toml_value(value: bool | str | Sequence[str]) -> str:
    """Render *value* as the TOML literal a config file carries.

    Booleans, strings and string sequences — every type a known key takes, and
    the only renderer for them, so the header `lore init` generates, the
    settings it seeds and the answers it records all spell a value one way.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    return "[" + ", ".join(f'"{item}"' for item in value) + "]"


def _key_signature(key: str) -> str:
    """Render *key*'s accepted values: its token set, its item set, or its type."""
    allowed = _ALLOWED_VALUES.get(key)
    if allowed is not None:
        return " | ".join(f'"{token}"' for token in allowed)
    allowed_items = _ALLOWED_ITEM_VALUES.get(key)
    if allowed_items is not None:
        return "list of " + " | ".join(f'"{token}"' for token in allowed_items())
    return _EXPECTED_TYPE[key].__name__


def render_known_keys_header() -> str:
    """Return the comment block `lore init` writes above the settings.

    Built from :data:`_FROM_TOML`, :data:`_EXPECTED_TYPE`,
    :data:`_ALLOWED_VALUES`, :data:`_ALLOWED_ITEM_VALUES`,
    :data:`DEFAULT_CONFIG` and :data:`_KEY_DOC` — the loader's own registry, so
    the block cannot drift from what the loader accepts.

    Every line is a comment, and the first two say the block is regenerated:
    that is what makes replacing it on a project's existing file legitimate,
    the same social contract the ``<!-- lore:begin -->`` marker blocks carry.
    """
    width = max(len(key) for key in _FROM_TOML)
    lines = [
        "# Project-level Lore configuration. The comment block above the first setting",
        "# is regenerated by `lore init`; edits inside it are replaced.",
        "#",
        "# Known keys (additional keys are accepted, preserved, and ignored):",
    ]
    for key, attr in _FROM_TOML.items():
        default = render_toml_value(getattr(DEFAULT_CONFIG, attr))
        lines.append(
            f"#   {key.ljust(width)} : {_key_signature(key)}, default {default}"
        )
        lines.extend(f"#       {doc}" for doc in _KEY_DOC[key].splitlines())
    return "".join(f"{line}\n" for line in lines)


def render_default_settings() -> str:
    """Return every known key at its default value, as TOML settings lines.

    What `lore init` writes under the header when a project has no
    ``.lore/config.toml`` at all. A project that already has one keeps its own
    lines untouched — only the header above them is regenerated.
    """
    return "".join(
        f"{key} = {render_toml_value(getattr(DEFAULT_CONFIG, attr))}\n"
        for key, attr in _FROM_TOML.items()
    )
