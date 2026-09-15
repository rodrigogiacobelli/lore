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
    (:mod:`tomllib`), :mod:`lore.paths` and :mod:`lore.validators`, both of
    which sit below it and import nothing from ``lore``.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from lore.paths import config_path, resolve_beneath
from lore.validators import validate_project_name


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
#   6. (free-form values only) add one entry to :data:`_VALUE_CHECK` naming the
#      validator that decides whether a value of the right type is usable;
#   7. add one entry to :data:`_KEY_DOC` describing the key in a line.
#
# A setting that is a multi-field or repeating record is a TOML table instead
# (A-1). A table is named in :data:`_KNOWN_TABLES`, parsed by its own function
# after the flat loop, and lands in its own frozen dataclass field.
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
    "project-name": "project_name",
    "default-project-scope": "default_project_scope",
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
    "project-name": str,
    "default-project-scope": str,
}

# Accepted tokens for constrained string keys. Keys absent from this table
# take any value of the right type.
_ALLOWED_VALUES: dict[str, tuple[str, ...]] = {
    "health-report-retention": ("none", "latest", "all"),
    "init-access-mode": ("cli", "native"),
    "init-skills-gitignore": ("lore-only", "none", "all"),
    "default-project-scope": ("self", "all"),
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
    "project-name": (
        "this project's name in an origin qualifier and in --project "
        "(empty: the project directory's name)"
    ),
    "default-project-scope": (
        "self - a bare read command covers this project and what it inherits\n"
        "all  - it also covers every Lore project beneath this one"
    ),
}


# Free-form values a token set cannot express, checked after the type and the
# token set. Held as a table for the same reason the others are: a key's rules
# live beside the key, and :func:`_unusable_reason` reads them all one way.
_VALUE_CHECK: dict[str, Callable[[object], str | None]] = {
    "project-name": validate_project_name,
}


# Root keys the loader parses as tables rather than as flat settings. Consulted
# beside :data:`_FROM_TOML` so a known table never also lands in
# :attr:`Config.extras`, which is documented as holding only keys the loader
# does not know (A-1, D-23).
_KNOWN_TABLES: frozenset[str] = frozenset({"shared", "descendants"})


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
class SharedExports:
    """The ``[shared]`` table: what an ancestor offers every descendant.

    ``exports`` holds literal entity ids and glob patterns; ``glossary``
    exports the whole glossary file, which is the only unit a glossary has
    (D-22).
    """

    exports: tuple[str, ...] = ()
    glossary: bool = False


@dataclass(frozen=True)
class DescendantExport:
    """One ``[[descendants]]`` block: what an ancestor offers one project.

    ``path`` is the identity — resolved beneath the ancestor's root — and
    ``name`` is a label for human readers and for messages. A block cannot
    name a project that does not resolve to that path, so a label that
    disagrees with its target's real name is inert (D-11).
    """

    name: str
    path: str
    exports: tuple[str, ...] = ()


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
        project_name: This project's name in an origin qualifier and in
            ``--project``. Default ``""``, which means "the project
            directory's name" — a project names itself, and no ancestor can
            rename it (A-5).
        default_project_scope: What a bare read command covers downward —
            ``"self"`` or ``"all"``. Default ``"self"``. It governs the
            downward axis only: entities inherited from an ancestor are
            visible at every scope (A-7).
        shared: The ``[shared]`` table — what this project offers every
            descendant. Default: nothing.
        descendants: The ``[[descendants]]`` blocks — what this project
            offers one named project beneath it. Default: none.
        extras: Forward-compatibility bucket. Any root-level key not listed
            in :data:`_FROM_TOML` and not named in :data:`_KNOWN_TABLES`
            (including whole TOML tables) is preserved here verbatim, so
            projects that adopt a newer ``config.toml`` against an older Lore
            release still parse cleanly.
    """

    show_glossary_on_codex_commands: bool = True
    health_report_retention: str = "none"
    init_agents: list[str] = field(default_factory=list)
    init_access_mode: str = "native"
    init_skill_families: list[str] = field(
        default_factory=lambda: list(DEFAULT_SKILL_FAMILIES)
    )
    init_skills_gitignore: str = "lore-only"
    project_name: str = ""
    default_project_scope: str = "self"
    shared: SharedExports = SharedExports()
    descendants: tuple[DescendantExport, ...] = ()
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
      * ``[shared]`` or ``[[descendants]]`` the loader cannot use → that
        table falls back to its default and emits a one-time
        ``lore: invalid [shared] table at <path> (<reason>); using default``
        or ``lore: invalid [[descendants]] entry at <path> (<reason>); using
        default`` stderr line. One malformed ``[[descendants]]`` entry drops
        the **whole** key, on the same rule the list-typed flat keys follow.
      * A ``[[descendants]]`` ``path`` that does not resolve beneath this
        project's root → that entry alone is dropped, with a one-time
        ``lore: descendant path "<path>" at <config path> escapes the project
        root; ignored`` stderr line. That case is a security refusal (N-5)
        rather than a shape error, and dropping the whole key would silently
        disable exports the operator did author correctly.
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
            if key not in _KNOWN_TABLES:
                extras[key] = value
            continue
        problem = _unusable_reason(key, value, path)
        if problem is not None:
            if warn:
                _warn_once(problem)
            continue
        kwargs[attr] = value
        answered.add(key)

    tables = _read_tables(data, root, path, warn=warn)
    kwargs.update(tables)
    return Config(extras=extras, **kwargs), frozenset(answered | set(tables))


class _TableError(Exception):
    """A table the loader cannot use, carrying the reason for its warning."""


def _read_tables(
    data: Mapping[str, Any], root: Path, path: Path, *, warn: bool
) -> dict[str, Any]:
    """Parse ``[shared]`` and ``[[descendants]]``, keyed by attribute name.

    Runs after the flat loop and follows the same two rules: a table the
    loader cannot use is left out, so the field keeps its default, and a table
    that parses cleanly is an answered key — which is why the returned keys
    are both the values and the answers (D-23).
    """
    parsed: dict[str, Any] = {}

    if "shared" in data:
        try:
            parsed["shared"] = _parse_shared(data["shared"])
        except _TableError as reason:
            if warn:
                _warn_once(
                    f"lore: invalid [shared] table at {path} "
                    f"({reason}); using default"
                )

    if "descendants" in data:
        try:
            blocks, escaped = _parse_descendants(data["descendants"], root)
        except _TableError as reason:
            if warn:
                _warn_once(
                    f"lore: invalid [[descendants]] entry at {path} "
                    f"({reason}); using default"
                )
        else:
            if warn:
                for escaping_path in escaped:
                    _warn_once(
                        f'lore: descendant path "{escaping_path}" at {path} '
                        "escapes the project root; ignored"
                    )
            parsed["descendants"] = blocks

    return parsed


def _is_string_list(value: object) -> bool:
    """Whether *value* is a list holding nothing but strings."""
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _parse_shared(value: object) -> SharedExports:
    """Parse the ``[shared]`` table, raising :class:`_TableError` on any shape
    the loader cannot use.

    An unknown key inside the table is ignored rather than refused, so a file
    written for a newer Lore release still parses here (FR-6).
    """
    if not isinstance(value, dict):
        raise _TableError("expected a table")
    exports = value.get("exports", [])
    if not _is_string_list(exports):
        raise _TableError("exports must be a list of strings")
    glossary = value.get("glossary", False)
    if not isinstance(glossary, bool):
        raise _TableError("glossary must be a boolean")
    return SharedExports(exports=tuple(exports), glossary=glossary)


def _parse_descendants(
    value: object, root: Path
) -> tuple[tuple[DescendantExport, ...], tuple[str, ...]]:
    """Parse the ``[[descendants]]`` blocks.

    Returns the usable blocks and the raw ``path`` values refused for escaping
    *root* — two different outcomes, because a shape error drops the whole key
    while a path escape drops one entry (N-5). Raises :class:`_TableError` for
    the first shape error found.
    """
    if not isinstance(value, list) or not all(
        isinstance(entry, dict) for entry in value
    ):
        raise _TableError("expected an array of tables")

    blocks: list[DescendantExport] = []
    escaped: list[str] = []
    for entry in value:
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise _TableError("name must be a non-empty string")
        declared_path = entry.get("path")
        if not isinstance(declared_path, str) or not declared_path:
            raise _TableError("path must be a non-empty string")
        exports = entry.get("exports", [])
        if not _is_string_list(exports):
            raise _TableError("exports must be a list of strings")
        if resolve_beneath(root, declared_path) is None:
            escaped.append(declared_path)
            continue
        blocks.append(
            DescendantExport(
                name=name, path=declared_path, exports=tuple(exports)
            )
        )
    return tuple(blocks), tuple(escaped)


def _unusable_reason(key: str, value: object, path: Path) -> str | None:
    """The stderr line for a value the loader cannot use, or ``None`` when it can.

    The whole of "is this a usable value" in one place, because both halves of
    :func:`_read` ask it — the values half to fall back to the default, the
    keys half to leave the key out of the answered set:

      * wrong type → ``invalid type for <key> at <path> (expected <type>)``;
      * constrained string outside its token set → ``invalid value for <key> at
        <path> (expected one of: ...)``;
      * free-form value its own validator rejects → ``invalid value for <key>
        at <path> (<the validator's reason>)``;
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
    check = _VALUE_CHECK.get(key)
    if check is not None:
        reason = check(value)
        if reason is not None:
            return (
                f"lore: invalid value for {key} at {path} "
                f"({reason}); using default"
            )
    allowed_items = _ALLOWED_ITEM_VALUES.get(key)
    if allowed_items is not None and isinstance(value, list):
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
