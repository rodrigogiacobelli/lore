"""Tagged instruction blocks: parse, gate, assemble.

An instruction file or a skill is a list of block ids. Each block is a small
markdown file with YAML frontmatter that says what it needs — a feature, a
route, capabilities, conditions. :func:`assemble` keeps the blocks whose gate
holds for a :class:`~lore.initplan.Profile` and :func:`join` writes them out.

The gate language is a conjunction of tags and a list of exclusions. There is no
``or``, no variable, no include: Lore does not evaluate templates
(decisions-001-dumb-infrastructure). A block that must hold under either of two
conditions is authored twice.

This module also owns the two checks that make the capability-leak guarantee a
property of the block set: :func:`commands_in` extracts the ``lore`` commands a
text contains and :func:`leaked_commands` says which of them no capability
grants. :func:`max_lines` is the conservative size bound the line-cap lint
(``lore.blocklint``) relies on.

Package data, like the agent registry and the skill catalogue: read through
``importlib.resources``, cached for the process, schema-checked with
``load_schema`` rather than an overlay resolver because the files ship inside
the wheel (decisions-018-overlays-are-path-discovered-config). ``lore.schemas``
is imported inside the loaders so importing this module stays cheap. Imports
``lore.initplan`` at module level and nothing else from ``lore``.
"""

from __future__ import annotations

import functools
import itertools
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from importlib import resources
from typing import Any, cast

import jsonschema
import yaml

from lore.initplan import (
    FILE_FEATURES,
    Capability,
    Feature,
    Profile,
    Route,
)

PACKAGED_ROOT = "src/lore/defaults/blocks"
"""Where blocks are authored — quoted in every build-defect message."""

_RESOURCE_PACKAGE = "lore.defaults"
_BLOCKS_DIR = "blocks"
_COMMANDS_FILE = "commands.yaml"
_BLOCK_SCHEMA = "block"
_COMMANDS_SCHEMA = "block-commands"

GLUE_BLANK = "blank"
GLUE_TIGHT = "tight"

_FRONTMATTER_FENCE = "---"


class BlockDefect(RuntimeError):
    """A shipped block or grant table that does not load: a build defect, never a user error."""


@dataclass(frozen=True)
class Block:
    """One gated piece of an instruction file or skill."""

    id: str
    feature: str
    route: str | None
    capabilities: tuple[str, ...]
    requires: tuple[str, ...]
    unless: tuple[str, ...]
    commands: tuple[str, ...]
    mentions: tuple[str, ...]
    glue: str
    body: str
    path: str
    """The packaged path relative to the blocks root, for messages."""


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

_PSEUDO = ("cli", "skills")
_FEATURE_IDS = tuple(f.value for f in Feature)
_FILE_FEATURE_IDS = tuple(f.value for f in FILE_FEATURES)
_ROUTE_IDS = tuple(r.value for r in Route)

_FEATURE_RE = re.compile(rf"^({'|'.join(_FEATURE_IDS)})$")
_ROUTE_RE = re.compile(rf"^route=({'|'.join(_ROUTE_IDS)})$")
_FEATURE_ROUTE_RE = re.compile(rf"^({'|'.join(_FILE_FEATURE_IDS)})\.({'|'.join(_ROUTE_IDS)})$")


@dataclass(frozen=True)
class Condition:
    """One parsed condition string."""

    text: str
    kind: str
    """``feature`` | ``route`` | ``feature-route`` | ``capability`` | ``pseudo``."""

    feature: str | None = None
    route: str | None = None
    capability: str | None = None
    pseudo: str | None = None


def parse_condition(text: str) -> Condition:
    """Parse one condition string. Raises ``ValueError`` for an unknown form.

    ``memory`` (a feature is on), ``route=cli`` (the global route),
    ``memory.cli`` (the feature is on *and* the route is that one — the
    conjunction a grant row needs), ``cap:memory-index`` and ``pseudo:cli``.
    """
    if _FEATURE_RE.match(text):
        return Condition(text, "feature", feature=text)
    match = _ROUTE_RE.match(text)
    if match:
        return Condition(text, "route", route=match.group(1))
    match = _FEATURE_ROUTE_RE.match(text)
    if match:
        feature, route = match.groups()
        return Condition(text, "feature-route", feature=feature, route=route)
    if text.startswith("cap:") and text[4:] in {c.value for c in Capability}:
        return Condition(text, "capability", capability=text[4:])
    if text.startswith("pseudo:") and text[7:] in _PSEUDO:
        return Condition(text, "pseudo", pseudo=text[7:])
    raise ValueError(f"Unknown condition: {text!r}.")


def _holds(
    condition: Condition,
    profile: Profile,
    skills_installed: bool,
    free: Mapping[str, bool] | None = None,
) -> bool:
    """Evaluate a condition. *free* overrides pseudo-capabilities (the size bound's relaxation)."""
    if condition.kind == "feature":
        return profile.feature_on(Feature(str(condition.feature)))
    if condition.kind == "route":
        return profile.route is Route(str(condition.route))
    if condition.kind == "feature-route":
        return profile.feature_on(Feature(str(condition.feature))) and profile.route is Route(
            str(condition.route)
        )
    if condition.kind == "capability":
        return profile.has(Capability(str(condition.capability)))
    pseudo = str(condition.pseudo)
    if free is not None and pseudo in free:
        return free[pseudo]
    if pseudo == "cli":
        return profile.cli_taught
    return skills_installed


# ---------------------------------------------------------------------------
# Parsing and loading
# ---------------------------------------------------------------------------


def _schema_errors(payload: object, kind: str) -> list[str]:
    from lore.schemas import load_schema

    validator = jsonschema.Draft202012Validator(load_schema(kind))
    return [
        f"/{'/'.join(str(part) for part in err.absolute_path)}: {err.message}"
        for err in sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
    ]


def _trim_blank_lines(text: str) -> str:
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def parse_block(text: str, *, source: str) -> Block:
    """Parse one block file. Raises ``ValueError`` naming *source* for any defect."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        raise ValueError(f"{source}: a block starts with a '---' frontmatter fence.")
    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == _FRONTMATTER_FENCE
        )
    except StopIteration:
        raise ValueError(f"{source}: the frontmatter is never closed with '---'.") from None
    try:
        meta = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise ValueError(f"{source}: invalid frontmatter YAML: {exc}") from exc
    errors = _schema_errors(meta, _BLOCK_SCHEMA)
    if errors:
        raise ValueError(f"{source}: does not match the block schema — {'; '.join(errors)}")
    meta = cast(dict[str, Any], meta)
    return Block(
        id=meta["id"],
        feature=meta["feature"],
        route=meta.get("route"),
        capabilities=tuple(meta.get("capabilities", ())),
        requires=tuple(meta.get("requires", ())),
        unless=tuple(meta.get("unless", ())),
        commands=tuple(meta.get("commands", ())),
        mentions=tuple(meta.get("mentions", ())),
        glue=meta.get("glue", GLUE_BLANK),
        body=_trim_blank_lines("\n".join(lines[end + 1 :])),
        path=source,
    )


def _read_block_files() -> Mapping[str, str]:
    """Every packaged block file, keyed by its path relative to the blocks root.

    The single read step, so a test can inject files without touching the
    shipped tree.
    """
    root = resources.files(_RESOURCE_PACKAGE).joinpath(_BLOCKS_DIR)
    found: dict[str, str] = {}
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            if entry.name.endswith(".md"):
                found[f"{directory.name}/{entry.name}"] = entry.read_text(encoding="utf-8")
    return found


def _read_commands_payload() -> Any:
    """Parse the packaged grant table. A test injects a payload here."""
    text = (
        resources.files(_RESOURCE_PACKAGE)
        .joinpath(_BLOCKS_DIR)
        .joinpath(_COMMANDS_FILE)
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


def _defect(where: str, reason: str) -> BlockDefect:
    return BlockDefect(f"{PACKAGED_ROOT}/{where}: {reason}")


@functools.lru_cache(maxsize=1)
def load_blocks() -> Mapping[str, Block]:
    """Every shipped block, keyed by id. Cached and schema-checked.

    Raises :class:`BlockDefect` naming the packaged file when one does not parse,
    does not carry its own stem as its id, or repeats another block's id.
    """
    loaded: dict[str, Block] = {}
    for relative, text in sorted(_read_block_files().items()):
        try:
            block = parse_block(text, source=relative)
        except ValueError as exc:
            raise _defect(relative, str(exc)) from exc
        stem = relative.rsplit("/", 1)[-1].removesuffix(".md")
        if block.id != stem:
            raise _defect(relative, f"id '{block.id}' must equal the file name '{stem}'.")
        if block.id in loaded:
            raise _defect(relative, f"id '{block.id}' is already used by {loaded[block.id].path}.")
        loaded[block.id] = block
    return loaded


def parse_grants(payload: object) -> dict[str, tuple[Condition, ...]]:
    """Validate a grant-table payload and parse its conditions.

    Raises :class:`BlockDefect` naming ``commands.yaml``.
    """
    errors = _schema_errors(payload, _COMMANDS_SCHEMA)
    if errors:
        raise _defect(_COMMANDS_FILE, f"does not match the block-commands schema — {'; '.join(errors)}")
    grants: dict[str, tuple[Condition, ...]] = {}
    for phrase, conditions in cast(dict[str, Any], payload)["commands"].items():
        try:
            grants[phrase] = tuple(parse_condition(text) for text in conditions)
        except ValueError as exc:
            raise _defect(_COMMANDS_FILE, f"'{phrase}': {exc}") from exc
    return grants


@functools.lru_cache(maxsize=1)
def load_grants() -> Mapping[str, tuple[Condition, ...]]:
    """The command-grant table: phrase to the conditions that permit it (any one)."""
    try:
        payload = _read_commands_payload()
    except yaml.YAMLError as exc:
        raise _defect(_COMMANDS_FILE, f"invalid YAML: {exc}") from exc
    return parse_grants(payload)


# ---------------------------------------------------------------------------
# Gate evaluation, assembly and joining
# ---------------------------------------------------------------------------


def _gate_conditions(block: Block) -> tuple[list[Condition], list[Condition]]:
    """The conditions a block requires (from its tags) and the ones it excludes."""
    required: list[Condition] = []
    if block.feature != "core":
        required.append(parse_condition(block.feature))
    if block.route:
        required.append(parse_condition(f"route={block.route}"))
    required.extend(parse_condition(f"cap:{capability}") for capability in block.capabilities)
    required.extend(parse_condition(text) for text in block.requires)
    return required, [parse_condition(text) for text in block.unless]


def _survives(
    block: Block,
    profile: Profile,
    skills_installed: bool,
    free: Mapping[str, bool] | None = None,
) -> bool:
    required, excluded = _gate_conditions(block)
    return all(_holds(c, profile, skills_installed, free) for c in required) and not any(
        _holds(c, profile, skills_installed, free) for c in excluded
    )


def gate_conditions(block: Block) -> tuple[list[Condition], list[Condition]]:
    """The conditions *block* requires and the ones it excludes, as parsed.

    Raises ``ValueError`` for a condition string or tag combination that does
    not parse (``lore.blocklint`` reports those as L1 and L8).
    """
    return _gate_conditions(block)


def gate_variables(block: Block) -> set[str]:
    """The profile fields and ``pseudo:`` names *block*'s gate reads."""
    return _block_variables(block)


def survives_relaxed(
    block: Block, profile: Profile, free: Mapping[str, bool], *, skills_installed: bool = False
) -> bool:
    """Like :func:`survives`, with the pseudo-capabilities named in *free* fixed by the caller.

    The size bound and the mention-closure lint both reason over assignments
    where ``pseudo:cli`` and friends are free variables.
    """
    return _survives(block, profile, skills_installed, free)


def holds(condition: str, profile: Profile, *, skills_installed: bool = False) -> bool:
    """Whether one condition string (the gate grammar) holds for *profile*.

    The same evaluation a block gate uses, offered for callers that gate
    something other than a block on the same vocabulary — the seeded default
    trees `lore init` keeps or drops. Raises ``ValueError`` for an unknown form.
    """
    return _holds(parse_condition(condition), profile, skills_installed)


def survives(block: Block, profile: Profile, *, skills_installed: bool = False) -> bool:
    """Whether *block* is kept for *profile*.

    All of: the feature is ``core`` or on; the route tag, when set, is the
    profile's route; every capability is on; every ``requires`` holds; no
    ``unless`` holds. *skills_installed* answers ``pseudo:skills``.
    """
    return _survives(block, profile, skills_installed)


def assemble(
    ids: Sequence[str],
    profile: Profile,
    *,
    blocks: Mapping[str, Block] | None = None,
    skills_installed: bool = False,
) -> list[Block]:
    """The blocks of *ids* that survive for *profile*, in the order listed.

    Raises ``ValueError`` naming an id that no block carries — whether or not
    that block would have survived.
    """
    table = load_blocks() if blocks is None else blocks
    chosen = []
    for block_id in ids:
        if block_id not in table:
            raise ValueError(f"Unknown block: '{block_id}'.")
        chosen.append(table[block_id])
    return [b for b in chosen if survives(b, profile, skills_installed=skills_installed)]


def join(blocks: Sequence[Block]) -> str:
    """Write *blocks* as one text.

    One blank line between two blocks, none before a block tagged
    ``glue: tight``; the result ends with exactly one newline. An empty list
    is the empty string.
    """
    out: list[str] = []
    for index, block in enumerate(blocks):
        if index and block.glue != GLUE_TIGHT:
            out.append("")
        out.extend(block.body.splitlines())
    return "\n".join(out) + "\n" if out else ""


# ---------------------------------------------------------------------------
# Command extraction
# ---------------------------------------------------------------------------

_GROUP_WORDS = ("codex", "rite", "glossary", "index", "doctrine", "artifact", "watcher", "board")
_TOP_LEVEL_WORDS = (
    "init",
    "new",
    "claim",
    "done",
    "block",
    "unblock",
    "ready",
    "needs",
    "unneed",
    "list",
    "missions",
    "show",
    "stats",
    "oracle",
    "edit",
    "delete",
    "impacts",
)
_GLOBAL_FLAGS = ("--help", "--version", "--json")
_BARE_WORDS = (*_GROUP_WORDS, "health", "impacts")

_LORE_RE = re.compile(r"(?<![\w./-])lore(?=\s|$)")
_SPAN_RE = re.compile(r"`([^`\n]+)`")
_FENCE_RE = re.compile(r"^\s*```")
_SHELL_BREAK = {"&&", "||", "|", ";"}
_WORD_RE = re.compile(r"^[a-z][a-z-]*")


def _code_fragments(text: str) -> Iterable[str]:
    """Every fenced line and inline code span of *text*."""
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            yield line
        else:
            yield from _SPAN_RE.findall(line)


def _prose(text: str) -> Iterable[str]:
    """Every line of *text* outside a fence, with its inline code spans removed."""
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            yield _SPAN_RE.sub(" ", line)


def _phrases(tokens: list[str]) -> list[str]:
    """The command phrases of one ``lore ...`` invocation, given the tokens after ``lore``."""
    flags = []
    index = 0
    while index < len(tokens) and tokens[index].startswith("--"):
        flags.append(tokens[index])
        index += 1
    if index >= len(tokens):
        return [flag for flag in flags if flag in _GLOBAL_FLAGS]
    word = tokens[index]
    rest = tokens[index + 1 :]
    if word in _GROUP_WORDS:
        verb = _WORD_RE.match(rest[0]) if rest else None
        return [f"{word} {verb.group(0)}" if verb else word]
    if word == "health":
        if "--scope" not in rest:
            return ["health"]
        scopes = []
        for token in rest[rest.index("--scope") + 1 :]:
            match = _WORD_RE.fullmatch(token)
            if match is None:
                break
            scopes.append(f"health --scope {match.group(0)}")
        return scopes
    if word in _TOP_LEVEL_WORDS:
        return [word]
    return []


def commands_in(text: str) -> tuple[str, ...]:
    """The normalised ``lore`` command phrases in the code of *text*.

    Only inline code spans and fenced lines are read, in order of first
    appearance without repeats. A group word takes the next word as its verb
    (``codex list``); ``health`` yields one phrase per ``--scope`` token (bare
    ``health`` when it has none); ``new`` is ``new`` whatever follows; a
    global flag alone is its own phrase.
    """
    seen: dict[str, None] = {}
    for fragment in _code_fragments(text):
        for chunk in _LORE_RE.split(fragment)[1:]:
            tokens = []
            for token in chunk.split():
                if token in _SHELL_BREAK:
                    break
                tokens.append(token)
            for phrase in _phrases(tokens):
                seen.setdefault(phrase)
    return tuple(seen)


def bare_commands(text: str) -> tuple[str, ...]:
    """The ``lore <group-word>`` mentions that sit outside every code span."""
    found: dict[str, None] = {}
    for line in _prose(text):
        for chunk in _LORE_RE.split(line)[1:]:
            tokens = chunk.split()
            if tokens and tokens[0] in _BARE_WORDS:
                found.setdefault(f"lore {tokens[0]}")
    return tuple(found)


def leaked_commands(
    text: str,
    profile: Profile,
    *,
    skills_installed: bool = False,
    grants: Mapping[str, tuple[Condition, ...]] | None = None,
) -> tuple[str, ...]:
    """The command phrases in *text* that no grant permits for *profile*.

    A phrase with no row in the grant table is always a leak. *grants* replaces
    the shipped table.
    """
    table = load_grants() if grants is None else grants
    return tuple(
        phrase
        for phrase in commands_in(text)
        if not any(
            _holds(condition, profile, skills_installed) for condition in table.get(phrase, ())
        )
    )


# ---------------------------------------------------------------------------
# The size bound
# ---------------------------------------------------------------------------

_ROUTE_VARIABLE = tuple(Route)
_BOOL_VARIABLE = (False, True)
_BOOL_FIELDS = ("memory", "memory_search", "memory_index", "memory_graph", "quests", "watchers")


def _condition_variables(condition: Condition) -> set[str]:
    """The profile fields and free pseudo-variables a condition reads."""
    if condition.kind == "pseudo":
        return {f"pseudo:{condition.pseudo}"}
    if condition.kind == "capability":
        capability = Capability(str(condition.capability))
        if capability is Capability.VALIDATE:
            return set()
        return {"memory", capability.value.replace("-", "_")}
    if condition.kind == "route":
        return {"route"}
    feature = str(condition.feature)
    found = {feature} if feature in _BOOL_FIELDS else set()
    if condition.kind == "feature-route":
        found.add("route")
    return found


def _block_variables(block: Block) -> set[str]:
    required, excluded = _gate_conditions(block)
    variables: set[str] = set()
    for condition in (*required, *excluded):
        variables |= _condition_variables(condition)
    return variables


def _components(variables_of: Mapping[str, set[str]]) -> list[list[str]]:
    """Group block ids into components that share at least one variable."""
    parent: dict[str, str] = {}

    def find(name: str) -> str:
        while parent.setdefault(name, name) != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    for block_id, variables in variables_of.items():
        find(f"block:{block_id}")
        for variable in variables:
            parent[find(f"block:{block_id}")] = find(f"var:{variable}")
    groups: dict[str, list[str]] = {}
    for block_id in variables_of:
        groups.setdefault(find(f"block:{block_id}"), []).append(block_id)
    return list(groups.values())


def _size(block: Block) -> int:
    return len(block.body.splitlines()) + (0 if block.glue == GLUE_TIGHT else 1)


def max_lines(ids: Sequence[str], blocks: Mapping[str, Block]) -> int:
    """A conservative upper bound on the lines *ids* can render to, for any profile.

    Blocks are grouped into components that share a gate variable; each
    component's variables are enumerated, the largest sum of surviving block
    sizes (lines plus one separator, none for a tight block) is taken, and the
    component maxima are added. Components share no variable, so the sum is a
    valid bound. The pseudo-capabilities are treated as free variables — a
    relaxation that can only raise the bound — so the result equals the true
    maximum when no pseudo-capability is involved.

    Raises ``ValueError`` naming an unknown id.
    """
    chosen: dict[str, Block] = {}
    for block_id in ids:
        if block_id not in blocks:
            raise ValueError(f"Unknown block: '{block_id}'.")
        chosen[block_id] = blocks[block_id]
    variables_of = {block_id: _block_variables(block) for block_id, block in chosen.items()}

    total = 0
    for component in _components(variables_of):
        names = sorted(set().union(*(variables_of[b] for b in component)))
        domains = [
            _ROUTE_VARIABLE if name == "route" else _BOOL_VARIABLE
            for name in names
        ]
        best = 0
        for values in itertools.product(*domains):
            assignment: dict[str, Any] = dict(zip(names, values, strict=True))
            profile = replace(
                Profile(),
                **{k: v for k, v in assignment.items() if not k.startswith("pseudo:")},
            )
            free: dict[str, bool] = {
                k.removeprefix("pseudo:"): v for k, v in assignment.items() if k.startswith("pseudo:")
            }
            best = max(
                best,
                sum(_size(chosen[b]) for b in component if _survives(chosen[b], profile, False, free)),
            )
        total += best
    return total


__all__: list[str] = [
    "Block",
    "BlockDefect",
    "Condition",
    "assemble",
    "bare_commands",
    "commands_in",
    "gate_conditions",
    "gate_variables",
    "join",
    "leaked_commands",
    "load_blocks",
    "load_grants",
    "max_lines",
    "parse_block",
    "parse_condition",
    "parse_grants",
    "survives",
    "survives_relaxed",
]
