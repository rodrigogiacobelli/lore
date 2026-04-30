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
from typing import Mapping

from lore.paths import config_path


# ---------------------------------------------------------------------------
# TOML key → dataclass attribute mapping
# ---------------------------------------------------------------------------
#
# Single source of truth for every known root-level setting. To add a new
# setting:
#   1. add a typed field to :class:`Config` with its default value;
#   2. add one entry here mapping the kebab-case TOML key to the snake_case
#      attribute name;
#   3. (if non-bool) extend the type-check branch in :func:`load_config`.
#
# Unknown root keys (and nested tables) are preserved verbatim in
# ``Config.extras`` for forward compatibility — never silently dropped.

_FROM_TOML: dict[str, str] = {
    "show-glossary-on-codex-commands": "show_glossary_on_codex_commands",
}


# ---------------------------------------------------------------------------
# Public (within-package) types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Typed, immutable view of ``.lore/config.toml``.

    Attributes:
        show_glossary_on_codex_commands: Whether ``lore codex show`` should
            auto-surface a glossary footer. Default ``True``.
        extras: Forward-compatibility bucket. Any root-level key not listed
            in :data:`_FROM_TOML` (including whole TOML tables) is preserved
            here verbatim, so projects that adopt a newer ``config.toml``
            against an older Lore release still parse cleanly.
    """

    show_glossary_on_codex_commands: bool = True
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
      * Malformed TOML or unreadable file → :data:`DEFAULT_CONFIG` and a
        one-time ``lore: invalid config at <path>: <reason> (using defaults)``
        stderr line.
      * Known key with wrong type → that key falls back to its default
        and emits a one-time
        ``lore: invalid type for <key> at <path> (expected <type>); using default``
        stderr line; other keys parse normally.
      * Unknown root keys / tables → preserved in :attr:`Config.extras`.
    """
    path = config_path(root)
    if not path.exists():
        return DEFAULT_CONFIG

    try:
        with path.open("rb") as fp:
            data = tomllib.load(fp)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        _warn_once(f"lore: invalid config at {path}: {exc} (using defaults)")
        return DEFAULT_CONFIG

    kwargs: dict[str, object] = {}
    extras: dict[str, object] = {}
    for key, value in data.items():
        attr = _FROM_TOML.get(key)
        if attr is None:
            extras[key] = value
            continue
        # Known key — type-check before accepting. Currently every known
        # field is bool; extend this branch when adding non-bool settings.
        if not isinstance(value, bool):
            _warn_once(
                f"lore: invalid type for {key} at {path} (expected bool); using default"
            )
            continue
        kwargs[attr] = value
    return Config(extras=extras, **kwargs)
