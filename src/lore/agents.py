"""The coding-agent registry — which agents `lore init` can target.

The registry is shipped data (``src/lore/defaults/agents.yaml``) read through
``importlib.resources``, not a list compiled into the initialisation logic:
adding a newly verified convention is one YAML block and no code change.

It is **package** data rather than project data because ``lore init`` runs where
no ``.lore/`` exists, and because ``click.Choice`` evaluates its set when the
``--agent`` decorator runs, which is import time.

``lore.schemas`` is imported inside the loader rather than at module level so
that ``import lore.agents`` stays as cheap as the decorator needs it to be; the
module's own import surface is stdlib, ``yaml``, ``jsonschema`` and
``lore.initplan``.

Validation reaches for ``load_schema`` rather than the overlay-capable
resolvers: this file ships inside the wheel, so a project must not be able to
change how it validates (decisions-018-overlays-are-path-discovered-config).
"""

from __future__ import annotations

import functools
from importlib import resources
from typing import Any

import jsonschema
import yaml

from lore.initplan import AgentTarget

PACKAGED_REGISTRY = "src/lore/defaults/agents.yaml"
"""Where the registry is authored — quoted in the build-defect message."""

_RESOURCE_PACKAGE = "lore.defaults"
_RESOURCE_NAME = "agents.yaml"
_SCHEMA_KIND = "agents"


def _read_registry_payload() -> Any:
    """Parse the packaged registry file.

    The single read step, so a test can inject a payload without touching the
    shipped file.
    """
    text = resources.files(_RESOURCE_PACKAGE).joinpath(_RESOURCE_NAME).read_text(encoding="utf-8")
    return yaml.safe_load(text)


def _build_defect(reason: str) -> RuntimeError:
    """A shipped file that will not load is a build defect, never a user error."""
    return RuntimeError(f"{PACKAGED_REGISTRY}: {reason}")


def _validated_payload() -> dict[str, Any]:
    """Read the packaged registry and check it against its schema."""
    # Imported here, not at module level: the registry has to be reachable when
    # click.Choice evaluates its set, and pulling the validator in at that point
    # would make every `lore` invocation pay for it. ``load_schema`` rather than
    # a resolver, so no project overlay can reach a file inside the wheel.
    from lore.schemas import load_schema

    try:
        payload = _read_registry_payload()
    except yaml.YAMLError as exc:
        raise _build_defect(f"invalid YAML: {exc}") from exc

    if not isinstance(payload, dict):
        raise _build_defect("registry must be a mapping")

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
def load_registry() -> tuple[AgentTarget, ...]:
    """Return every shipped agent convention, in the order the file declares them.

    Raises ``RuntimeError`` naming the packaged file when it does not parse or
    does not validate — ``lore init`` cannot do its job without a registry.
    """
    return tuple(
        AgentTarget(
            id=row["id"],
            label=row["label"],
            instruction_file=row["instruction_file"],
            skills_dir=row["skills_dir"],
        )
        for row in _validated_payload()["agents"]
    )


@functools.lru_cache(maxsize=1)
def agent_ids() -> tuple[str, ...]:
    """Return every registry id, sorted. This is the token set ``--agent`` accepts."""
    return tuple(sorted(row.id for row in load_registry()))


def get_agent(agent_id: str) -> AgentTarget:
    """Return the registry row for *agent_id*.

    Raises ``ValueError`` naming the known ids when the registry has no such row.
    """
    row = next((candidate for candidate in load_registry() if candidate.id == agent_id), None)
    if row is None:
        known = ", ".join(agent_ids())
        raise ValueError(f"Unknown agent: '{agent_id}'. Known agents: {known}.")
    return row
