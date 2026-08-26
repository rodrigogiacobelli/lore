"""Pure utility validators for Lore entity IDs, messages, and priorities.

No imports from lore.* — this is a standalone utility module.
"""

import re

# ---------------------------------------------------------------------------
# Compiled regex patterns (strict hex: [0-9a-f], length 4–6)
# ---------------------------------------------------------------------------

_HEX = r"[0-9a-f]{4,6}"

# Name pattern: alphanumeric start, then letters/digits/hyphens/underscores
_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")

# Loose quest ID pattern: accepts non-hex chars (g–z) for test-DB-inserted IDs
_QUEST_LOOSE_RE = re.compile(r"^q-[a-z0-9]{4,8}$")

# Quest ID: q-<4-6 hex>
_QUEST_RE = re.compile(rf"^q-{_HEX}$")

# Standalone mission ID: m-<4-6 hex>
_STANDALONE_MISSION_RE = re.compile(rf"^m-{_HEX}$")

# Scoped mission ID: q-<4-6 hex>/m-<4-6 hex>
_SCOPED_MISSION_RE = re.compile(rf"^q-{_HEX}/m-{_HEX}$")

# Any valid entity ID (quest, standalone mission, or scoped mission)
_ENTITY_RE = re.compile(
    rf"^(?:q-{_HEX}|m-{_HEX}|q-{_HEX}/m-{_HEX})$"
)

# Any valid mission ID (standalone or scoped — NOT a bare quest ID)
_MISSION_RE = re.compile(
    rf"^(?:m-{_HEX}|q-{_HEX}/m-{_HEX})$"
)

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

_PRIORITY_MIN = 0
_PRIORITY_MAX = 4


def validate_message(message: str) -> str | None:
    """Return an error string if *message* is empty/whitespace, else None."""
    if not message or not message.strip():
        return "Message cannot be empty."
    return None


def _validate_content_nonempty(content: str) -> str | None:
    """Return error string if *content* is empty / whitespace-only, else None.

    Internal helper (leading underscore) shared by file-backed entity
    create/update flows. NOT part of the public ``lore.api`` surface.
    """
    if not content or not content.strip():
        return "Content cannot be empty."
    return None


def validate_entity_id(eid: str) -> str | None:
    """Return an error string if *eid* is not a valid quest or mission ID, else None."""
    if not eid or not _ENTITY_RE.match(eid):
        return f'Invalid entity ID format: "{eid}"'
    return None


def validate_mission_id(mid: str) -> str | None:
    """Return an error string if *mid* is not a valid mission ID, else None.

    A valid mission ID is either a standalone (m-<hex>) or scoped
    (q-<hex>/m-<hex>) form.  A bare quest ID is rejected.
    """
    if not mid or not _MISSION_RE.match(mid):
        return f'Invalid mission ID format: "{mid}"'
    return None


def validate_priority(priority: int | None) -> str | None:
    """Return an error string if *priority* is out of range [0, 4], else None.

    None is accepted (means "no priority set").
    """
    if priority is None:
        return None
    if not (_PRIORITY_MIN <= priority <= _PRIORITY_MAX):
        return (
            f"Priority {priority} is out of range; must be between "
            f"{_PRIORITY_MIN} and {_PRIORITY_MAX}."
        )
    return None


def validate_name(name: str) -> str | None:
    """Return an error string if *name* is not a valid knight/doctrine name, else None.

    A valid name must start with an alphanumeric character and contain only
    letters, digits, hyphens, and underscores.
    """
    if not name or not _NAME_RE.match(name):
        return (
            "Invalid name: must start with alphanumeric and contain only "
            "letters, digits, hyphens, underscores."
        )
    return None


def validate_rite_id(s: str) -> None:
    """Raise ``ValueError`` if *s* is not a valid rite name, else return None.

    A valid rite name must start with an alphanumeric character and contain only
    letters, digits, hyphens, and underscores (``^[a-zA-Z0-9][a-zA-Z0-9_-]*$``).
    """
    if not s or not _NAME_RE.match(s):
        raise ValueError(
            "Invalid name: must be alphanumeric, hyphens, underscores only."
        )


def validate_group(group: str | None) -> str | None:
    """Return an error string if *group* is not a safe group path, else None.

    Rules: None → None; empty → error; backslash → error; leading `/` → error;
    trailing `/` → error; each segment must be non-empty, not `..`, and match
    ``_NAME_RE``.
    """
    if group is None:
        return None

    def err(reason: str) -> str:
        return f"invalid group '{group}': {reason}"

    if group == "":
        return err("empty group not allowed")
    if "\\" in group:
        return err("backslash not allowed")
    if group.startswith("/"):
        return err("absolute paths not allowed (leading '/')")
    if group.endswith("/"):
        return err("trailing slash not allowed")
    for seg in group.split("/"):
        if seg == "":
            return err("empty segment not allowed")
        if seg == "..":
            return err("path traversal ('..') not allowed")
        if not _NAME_RE.match(seg):
            return err(f"bad segment characters in '{seg}'")
    return None


def is_glob_pattern(s: str) -> bool:
    """Return ``True`` iff *s* contains any of ``*``, ``?``, ``[``.

    Used by the codex-seed JSON renderer to classify each binding as
    ``"exact"`` or ``"glob"`` (FR-12) and by the path-seed exact/glob
    dedup (FR-9).
    """
    return any(c in s for c in "*?[")


def validate_binds_entry(s: object) -> str | None:
    """Return an error string if *s* is not a valid `binds:` entry, else None.

    Rules mirror the JSON-Schema layer on ``codex-frontmatter.yaml``:
    must be a non-empty string; must not start with ``/`` (absolute path);
    must not contain any ``..`` path segment (leading, embedded, or trailing).
    """
    if not isinstance(s, str):
        return f"Invalid binds entry: {s!r} (not a string)"
    if s == "":
        return 'Invalid binds entry: "" (empty string)'
    if s.startswith("/"):
        return f'Invalid binds entry: "{s}" (absolute path not allowed)'
    if any(seg == ".." for seg in s.split("/")):
        return f'Invalid binds entry: "{s}" (".." segment not allowed)'
    return None


def validate_quest_id_loose(quest_id: str) -> str | None:
    """Return an error string if *quest_id* does not match the loose quest ID pattern.

    Uses pattern ``^q-[a-z0-9]{4,8}$`` rather than the strict hex pattern
    ``^q-[0-9a-f]{4,6}$``.  The loose variant deliberately accepts non-hex
    characters (``g``–``z``) because test databases may insert IDs that were
    written by hand or by a fixture and do not conform to the standard hex
    format produced by ``lore.ids.generate_id()``.

    **Restricted use:** this function must NOT be used for new ID creation or
    for user-facing format validation.  Its only legitimate use is in CLI paths
    that must accept test-DB-inserted IDs (e.g. the ``lore show`` handler when
    exercised with synthetic IDs in the E2E test suite).  Using this function
    for real user input is a bug — use ``validate_entity_id`` instead.
    """
    if not quest_id or not _QUEST_LOOSE_RE.match(quest_id):
        return "Invalid quest ID format."
    return None


_CHAOS_THRESHOLD_MIN = 30
_CHAOS_THRESHOLD_MAX = 100


def validate_chaos_threshold(value: int) -> tuple[bool, str | None]:
    """Return (True, None) if value is within [30, 100], else (False, error_message)."""
    if not (_CHAOS_THRESHOLD_MIN <= value <= _CHAOS_THRESHOLD_MAX):
        return (
            False,
            f"--threshold must be between {_CHAOS_THRESHOLD_MIN} and {_CHAOS_THRESHOLD_MAX}",
        )
    return (True, None)


def route_entity(eid: str) -> tuple[str, str]:
    """Return (table, id_col) for a valid entity ID.

    Quest IDs   → ("quests",   "id")
    Mission IDs → ("missions", "id")

    Raises ValueError for unrecognised IDs.
    """
    if _QUEST_RE.match(eid):
        return ("quests", "id")
    if _MISSION_RE.match(eid):
        return ("missions", "id")
    raise ValueError(f"Cannot route unrecognised entity ID: '{eid}'")


# ---------------------------------------------------------------------------
# `lore init` answer tokens
# ---------------------------------------------------------------------------
#
# ADR-011: any rule that exists only in the CLI is a bug. The CLI's
# constrained-flag layer rejects an out-of-set token at the argv boundary with
# the wording and exit code ADR-017 pins; these four are what make the Python
# surface reject exactly the same tokens, and `validate_agent_selection` is
# additionally where the `none` exclusivity rule lives, so that neither layer
# owns a second copy of it.
#
# The two data-driven sets — the agent registry and the skill catalogue — are
# passed in rather than looked up. `lore.agents` and `lore.skills` read packaged
# YAML through `jsonschema`, and importing either here would drop this module
# out of the foundation position `standards-dependency-inversion` gives it (and
# out of the no-lore-imports invariant `test_validators_has_no_lore_imports`
# pins). `plan_init` and `cli.py` both hold those sets already.

ACCESS_MODES: tuple[str, ...] = ("cli", "native")
"""The two access modes. Mirrors ``lore.initplan.AccessMode``, which cannot be
imported here; a unit test pins the two together so they cannot drift."""

AGENT_NONE = "none"
"""The registry id meaning "no agent" — exclusive with every other id."""


def validate_access_mode(
    mode: object, accepted: "tuple[str, ...]" = ACCESS_MODES
) -> str | None:
    """Return an error string if *mode* is not an access-mode token, else None."""
    if isinstance(mode, str) and mode in accepted:
        return None
    return f"Unknown access mode: '{mode}'. Accepted tokens: {', '.join(accepted)}."


def validate_skill_family(family: object, accepted: "tuple[str, ...]") -> str | None:
    """Return an error string if *family* is not an accepted token, else None.

    *accepted* is the caller's token set — the concrete family ids plus the two
    aggregates ``all`` and ``none`` where those are legal.
    """
    if isinstance(family, str) and family in accepted:
        return None
    return f"Unknown skill family: '{family}'. Accepted tokens: {', '.join(accepted)}."


def validate_agent_id(agent_id: object, known_ids: "tuple[str, ...]") -> str | None:
    """Return an error string if *agent_id* is not a registry id, else None."""
    if isinstance(agent_id, str) and agent_id in known_ids:
        return None
    return f"Unknown agent: '{agent_id}'. Known agents: {', '.join(known_ids)}."


def validate_agent_selection(
    agents: "tuple[str, ...] | list[str]", known_ids: "tuple[str, ...]"
) -> str | None:
    """Return an error string if *agents* is not a legal selection, else None.

    An unknown id is reported before the exclusivity rule, so a caller fixes the
    typo it can see rather than a rule it has not reached yet. Duplicates are
    not an error — two spellings of one selection are one selection.
    """
    for agent_id in agents:
        error = validate_agent_id(agent_id, known_ids)
        if error is not None:
            return error
    if AGENT_NONE in agents and len(set(agents)) > 1:
        return f"--agent {AGENT_NONE} cannot be combined with other agents."
    return None
