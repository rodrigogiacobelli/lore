"""The structural lint over instruction blocks and the skill catalogue.

Two promises are made to every project and kept here as properties of the
shipped block set rather than checked against any one profile: no rendered
instruction file or skill exceeds its line cap, and none mentions a command
whose capability is off. The rules (L1 to L10) read tags, counts and structure
— never prose (decisions-006-no-seed-content-tests) — and :func:`lint_rendered`
re-checks the actual output for a given profile as a belt on the proof.

Used by the unit tests and ``scripts/check_blocks.py`` (a release preflight and
a CI step). `lore init` never imports it.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from lore import blocks as blocks_module
from lore import skills
from lore.blocks import Block, Condition
from lore.initplan import (
    FILE_FEATURES,
    Capability,
    Profile,
    Route,
)

SKILL_LINE_CAP = 100
"""The default rendered-line limit of one skill file."""

TABLE_OPENER = "<!-- lore:skills-table -->"
TABLE_CLOSER = "<!-- lore:skills-table end -->"
TABLE_BLOCK_ID = "i-skills-table"
TABLE_BASE_ROWS = 4
"""Lines the skills table adds around its rows: heading, header, rule and a blank."""

_MARKER_RE = re.compile(r"<!--\s*lore:")
_TEMPLATE_TOKENS = ("{{", "}}", "${")
_ENUMERATION_LIMIT = 250_000
_FILE_FEATURE_IDS = tuple(f.value for f in FILE_FEATURES)


@dataclass(frozen=True)
class LintProblem:
    """One rule a block, the catalogue or a rendering breaks."""

    code: str
    where: str
    detail: str


# ---------------------------------------------------------------------------
# Loading the defaults
# ---------------------------------------------------------------------------


def _load(
    blocks: Mapping[str, Block] | None,
    catalogue: Mapping[str, Any] | None,
    grants: Mapping[str, tuple[Condition, ...]] | None,
    problems: list[LintProblem],
) -> tuple[Mapping[str, Block], Mapping[str, Any], Mapping[str, tuple[Condition, ...]]] | None:
    """The three inputs, loading the shipped ones; None (with a problem) when one does not load."""
    try:
        loaded_blocks = blocks_module.load_blocks() if blocks is None else blocks
    except blocks_module.BlockDefect as exc:
        problems.append(LintProblem("L1", blocks_module.PACKAGED_ROOT, str(exc)))
        return None
    try:
        loaded_catalogue = skills.load_catalogue() if catalogue is None else catalogue
    except RuntimeError as exc:
        problems.append(LintProblem("L3", skills.PACKAGED_CATALOGUE, str(exc)))
        return None
    try:
        loaded_grants = blocks_module.load_grants() if grants is None else grants
    except blocks_module.BlockDefect as exc:
        problems.append(LintProblem("L2", f"{blocks_module.PACKAGED_ROOT}/commands.yaml", str(exc)))
        return None
    return loaded_blocks, loaded_catalogue, loaded_grants


# ---------------------------------------------------------------------------
# Per-block rules
# ---------------------------------------------------------------------------


def _stem(path: str) -> str:
    return path.rsplit("/", 1)[-1].removesuffix(".md")


def _lint_parse(block: Block, problems: list[LintProblem]) -> None:
    """L1: the file's place and tags are well formed."""
    directory = block.path.rsplit("/", 1)[0] if "/" in block.path else ""
    if _stem(block.path) != block.id:
        problems.append(LintProblem("L1", block.id, f"id must equal the file stem '{_stem(block.path)}'"))
    if directory != block.feature:
        problems.append(
            LintProblem("L1", block.id, f"directory '{directory}' must equal feature '{block.feature}'")
        )
    known_capabilities = {c.value for c in Capability}
    for capability in block.capabilities:
        if capability not in known_capabilities:
            problems.append(LintProblem("L1", block.id, f"unknown capability '{capability}'"))
    for text in (*block.requires, *block.unless):
        try:
            blocks_module.parse_condition(text)
        except ValueError as exc:
            problems.append(LintProblem("L1", block.id, str(exc)))


def implied_conditions(block: Block) -> set[str]:
    """Every condition the block's own tags guarantee, literally or by the fixed axioms.

    Doctrines, Artifacts and ``cap:validate`` hold in every profile; a Memory
    capability proves Memory; a feature proven on together with a route proves
    the ``<feature>.<route>`` grant form; the Lore CLI is taught whenever the
    route is the CLI, a Memory capability or Quests is on.
    """
    literals: set[str] = {"doctrines", "artifacts", "cap:validate"}
    if block.feature != "core":
        literals.add(block.feature)
    if block.route:
        literals.add(f"route={block.route}")
    literals.update(f"cap:{capability}" for capability in block.capabilities)
    literals.update(block.requires)

    implied = set(literals)
    if any(t.startswith("cap:memory-") for t in literals):
        implied.add("memory")
    routes = {t.removeprefix("route=") for t in literals if t.startswith("route=")}
    for feature in _FILE_FEATURE_IDS:
        if feature in implied:
            implied.update(f"{feature}.{route}" for route in routes)
    for text in literals:
        match = re.fullmatch(r"([a-z]+)\.(harness|cli)", text)
        if match:
            implied.update({match.group(1), f"route={match.group(2)}"})
            routes.add(match.group(2))
    if "cli" in routes or "quests" in implied or any(t.startswith("cap:memory-") for t in implied):
        implied.add("pseudo:cli")
    return implied


def _lint_commands(
    block: Block,
    grants: Mapping[str, tuple[Condition, ...]],
    problems: list[LintProblem],
) -> None:
    """L2: declared commands equal the body's, have rows, and are implied by the tags."""
    extracted = set(blocks_module.commands_in(block.body))
    declared = set(block.commands)
    for phrase in sorted(extracted - declared):
        problems.append(LintProblem("L2", block.id, f"'lore {phrase}' is used but not declared"))
    for phrase in sorted(declared - extracted):
        problems.append(LintProblem("L2", block.id, f"'{phrase}' is declared but not in the body"))
    implied = implied_conditions(block)
    for phrase in sorted(declared):
        row = grants.get(phrase)
        if row is None:
            problems.append(LintProblem("L2", block.id, f"'{phrase}' has no row in commands.yaml"))
        elif not any(condition.text in implied for condition in row):
            wanted = " or ".join(condition.text for condition in row)
            problems.append(
                LintProblem("L2", block.id, f"'{phrase}' needs {wanted}, which the block's tags do not imply")
            )


def _lint_markers(block: Block, problems: list[LintProblem]) -> None:
    """L6: no marker but the single skills-table pair in its own block."""
    lines = [line.strip() for line in block.body.splitlines()]
    markers = [line for line in lines if _MARKER_RE.search(line)]
    if block.id == TABLE_BLOCK_ID:
        if markers != [TABLE_OPENER, TABLE_CLOSER]:
            problems.append(
                LintProblem("L6", block.id, "must hold exactly the skills-table marker pair, once")
            )
        return
    for marker in markers:
        problems.append(LintProblem("L6", block.id, f"marker '{marker}' is not allowed here"))


def _lint_syntax(block: Block, problems: list[LintProblem]) -> None:
    """L7: no template syntax and no command outside a code span."""
    for token in _TEMPLATE_TOKENS:
        if token in block.body:
            problems.append(LintProblem("L7", block.id, f"template syntax '{token}' in the body"))
    for bare in blocks_module.bare_commands(block.body):
        problems.append(LintProblem("L7", block.id, f"'{bare}' appears outside a code span"))


def _lint_placement(block: Block, skill_body: bool, problems: list[LintProblem]) -> None:
    """L8: core and the skills pseudo-condition are used where they mean something."""
    if skill_body:
        if block.feature == "core":
            problems.append(LintProblem("L8", block.id, "a skill body block must not be core"))
        if "pseudo:skills" in (*block.requires, *block.unless):
            problems.append(LintProblem("L8", block.id, "a skill block must not use pseudo:skills"))


def _lint_unsatisfiable(block: Block, problems: list[LintProblem]) -> None:
    """L9: an exclusion never contradicts what the block itself requires."""
    required = {f"cap:{capability}" for capability in block.capabilities} | set(block.requires)
    if block.feature != "core":
        required.add(block.feature)
    for text in block.unless:
        if text in required:
            problems.append(LintProblem("L9", block.id, f"unless '{text}' contradicts what the block requires"))


# ---------------------------------------------------------------------------
# Catalogue rules
# ---------------------------------------------------------------------------


def _catalogue_lists(catalogue: Mapping[str, Any]) -> list[tuple[str, Sequence[str]]]:
    lists: list[tuple[str, Sequence[str]]] = []
    for entry in catalogue["skills"]:
        for row in entry["files"]:
            lists.append((f"{entry['id']}/{row['path']}", row["blocks"]))
    for name, document in catalogue["documents"].items():
        lists.append((f"documents.{name}", document["blocks"]))
    return lists


def _head_meta(block: Block) -> dict[str, Any] | None:
    import yaml

    lines = block.body.splitlines()
    fences = [i for i, line in enumerate(lines) if line.strip() == "---"]
    if len(fences) < 2 or fences[0] != 0:
        return None
    try:
        meta = yaml.safe_load("\n".join(lines[1 : fences[1]]))
    except yaml.YAMLError:
        return None
    return meta if isinstance(meta, dict) else None


def _lint_catalogue(
    blocks: Mapping[str, Block], catalogue: Mapping[str, Any], problems: list[LintProblem]
) -> None:
    """L3: every block is referenced, every reference exists, every head is a real head."""
    referenced: set[str] = set()
    for where, ids in _catalogue_lists(catalogue):
        seen: set[str] = set()
        for block_id in ids:
            if block_id in seen:
                problems.append(LintProblem("L3", where, f"block '{block_id}' is listed twice"))
            seen.add(block_id)
            if block_id not in blocks:
                problems.append(LintProblem("L3", where, f"block '{block_id}' does not exist"))
        referenced |= seen
    for entry in catalogue["skills"]:
        head_id = entry["head"]
        referenced.add(head_id)
        head = blocks.get(head_id)
        if head is None:
            problems.append(LintProblem("L3", entry["id"], f"head block '{head_id}' does not exist"))
            continue
        meta = _head_meta(head)
        if meta is None:
            problems.append(LintProblem("L3", head_id, "the head must be a '---' frontmatter block"))
            continue
        if meta.get("name") != entry["id"]:
            problems.append(LintProblem("L3", head_id, f"head name must be '{entry['id']}'"))
        description = meta.get("description")
        if not isinstance(description, str) or not description.strip():
            problems.append(LintProblem("L3", head_id, "head description must not be empty"))
    for block_id in sorted(set(blocks) - referenced):
        problems.append(LintProblem("L3", block_id, "no catalogue list references this block"))


def _safe_max_lines(ids: Sequence[str], blocks: Mapping[str, Block]) -> int | None:
    try:
        return blocks_module.max_lines([b for b in ids if b in blocks], blocks)
    except ValueError:
        return None


def _lint_line_caps(
    blocks: Mapping[str, Block], catalogue: Mapping[str, Any], problems: list[LintProblem]
) -> None:
    """L4: documents and skill files fit their caps; every listed exception is real."""
    skill_count = len(catalogue["skills"])
    for name, document in catalogue["documents"].items():
        size = _safe_max_lines(document["blocks"], blocks)
        if size is None:
            continue
        has_table = any(TABLE_OPENER in blocks[b].body for b in document["blocks"] if b in blocks)
        bound = size + (TABLE_BASE_ROWS + skill_count if has_table else 0)
        if bound > document["max_lines"]:
            problems.append(
                LintProblem(
                    "L4", f"documents.{name}", f"can render {bound} lines, over its cap of {document['max_lines']}"
                )
            )

    oversize: Mapping[str, int] = catalogue.get("oversize", {})
    files = {f"{e['id']}/{row['path']}" for e in catalogue["skills"] for row in e["files"]}
    for entry in catalogue["skills"]:
        head = blocks.get(entry["head"])
        for row in entry["files"]:
            key = f"{entry['id']}/{row['path']}"
            size = _safe_max_lines(row["blocks"], blocks)
            if size is None:
                continue
            if row["path"] == "SKILL.md" and head is not None:
                size += len(head.body.splitlines()) + 1
            limit = oversize.get(key, SKILL_LINE_CAP)
            if size > limit:
                problems.append(LintProblem("L4", key, f"can render {size} lines, over its limit of {limit}"))
    for key, bound in oversize.items():
        if key not in files:
            problems.append(LintProblem("L4", key, "the oversize exception names no catalogue file"))
        elif bound <= SKILL_LINE_CAP:
            problems.append(
                LintProblem("L4", key, f"the exception ({bound}) is not above the {SKILL_LINE_CAP}-line cap")
            )


# ---------------------------------------------------------------------------
# Mention closure (L5, L10)
# ---------------------------------------------------------------------------

def _domain(name: str) -> tuple[Any, ...]:
    if name == "route":
        return tuple(Route)
    return (False, True)


def _consistent(assignment: Mapping[str, Any]) -> bool:
    """Whether the free ``pseudo:cli`` agrees with the enumerated fields.

    ``pseudo:cli`` may be ``True`` whatever is enumerated (a field outside the
    enumeration could make it so); it may be ``False`` only when nothing
    enumerated forces the CLI to be taught.
    """
    if assignment.get("pseudo:cli") is not False:
        return True
    memory_on = assignment.get("memory") is True
    forced = (
        assignment.get("route") is Route.CLI
        or assignment.get("quests") is True
        or (
            memory_on
            and any(assignment.get(name) is True for name in ("memory_search", "memory_index", "memory_graph"))
        )
    )
    return not forced


def _assignments(names: Sequence[str]) -> Iterator[dict[str, Any]]:
    for values in itertools.product(*(_domain(n) for n in names)):
        assignment = dict(zip(names, values, strict=True))
        if _consistent(assignment):
            yield assignment


def _target_blocks(
    catalogue: Mapping[str, Any], blocks: Mapping[str, Block], target: str
) -> tuple[list[Block], list[Block]] | None:
    """(SKILL.md blocks, file blocks) of a mention target; None when it names nothing."""
    skill_id, _, path = target.partition("/")
    entry = next((e for e in catalogue["skills"] if e["id"] == skill_id), None)
    if entry is None:
        return None
    body = [blocks[b] for b in entry["files"][0]["blocks"] if b in blocks]
    if not path:
        return body, []
    row = next((r for r in entry["files"] if r["path"] == path), None)
    if row is None:
        return None
    return body, [blocks[b] for b in row["blocks"] if b in blocks]


def _lint_mentions(
    blocks: Mapping[str, Block], catalogue: Mapping[str, Any], problems: list[LintProblem]
) -> None:
    for block in blocks.values():
        for target in block.mentions:
            skill_id, _, path = target.partition("/")
            if path and not any(
                e["id"] == skill_id and any(r["path"] == path for r in e["files"])
                for e in catalogue["skills"]
            ):
                if any(e["id"] == skill_id for e in catalogue["skills"]):
                    problems.append(LintProblem("L10", block.id, f"mentions '{target}', which the catalogue does not declare"))
                else:
                    problems.append(LintProblem("L5", block.id, f"mentions '{target}', but no skill '{skill_id}' exists"))
                continue
            resolved = _target_blocks(catalogue, blocks, target)
            if resolved is None:
                problems.append(LintProblem("L5", block.id, f"mentions '{target}', but no skill '{skill_id}' exists"))
                continue
            if "pseudo:skills" in block.requires:
                problems.append(
                    LintProblem("L5", block.id, f"a block gated on pseudo:skills cannot prove that '{target}' is installed")
                )
                continue
            _prove_mention(block, target, resolved, problems)


def _prove_mention(
    block: Block, target: str, resolved: tuple[list[Block], list[Block]], problems: list[LintProblem]
) -> None:
    body, file_blocks = resolved
    try:
        names = sorted(
            set(blocks_module.gate_variables(block)).union(
                *(blocks_module.gate_variables(b) for b in (*body, *file_blocks))
            )
        )
    except ValueError:
        return
    size = 1
    for name in names:
        size *= len(_domain(name))
    if size > _ENUMERATION_LIMIT:
        problems.append(LintProblem("L5", block.id, f"too many gate variables to prove closure for '{target}'"))
        return
    for assignment in _assignments(names):
        profile = replace(
            Profile(), **{k: v for k, v in assignment.items() if not k.startswith("pseudo:")}
        )
        free = {k.removeprefix("pseudo:"): v for k, v in assignment.items() if k.startswith("pseudo:")}
        if not blocks_module.survives_relaxed(block, profile, free):
            continue
        installed = any(blocks_module.survives_relaxed(b, profile, free) for b in body)
        present = installed and (
            not file_blocks or any(blocks_module.survives_relaxed(b, profile, free) for b in file_blocks)
        )
        if not present:
            shown = ", ".join(f"{k.removeprefix('pseudo:')}={getattr(v, 'value', v)}" for k, v in assignment.items())
            problems.append(
                LintProblem("L5", block.id, f"survives while '{target}' is absent (for example {shown})")
            )
            return


# ---------------------------------------------------------------------------
# Distinct renderings
# ---------------------------------------------------------------------------


def distinct_renders(
    skill_id: str,
    relative: str,
    *,
    blocks: Mapping[str, Block] | None = None,
    catalogue: Mapping[str, Any] | None = None,
) -> set[str]:
    """Every text the file *relative* of *skill_id* can render to, for any profile.

    The release script hashes each one into the legacy-hash table, so a project
    that committed its skills and lost its manifest still recognises an
    unedited install as Lore's. The gate variables the skill's body and the file
    read are enumerated exactly as the size bound and the mention proof
    enumerate them; the texts are deduplicated. A file the skill does not write
    for an assignment (the skill is not installed, or no block of the file
    survives) contributes nothing.

    Raises ``ValueError`` for an unknown skill or file.
    """
    table = blocks_module.load_blocks() if blocks is None else blocks
    cat = skills.load_catalogue() if catalogue is None else catalogue
    entry = next((e for e in cat["skills"] if e["id"] == skill_id), None)
    if entry is None:
        raise ValueError(f"Unknown skill: '{skill_id}'.")
    row = next((r for r in entry["files"] if r["path"] == relative), None)
    if row is None:
        raise ValueError(f"Unknown file '{relative}' for skill '{skill_id}'.")

    body = [table[b] for b in entry["files"][0]["blocks"]]
    own = [table[b] for b in row["blocks"]]
    head = table[entry["head"]].body
    names = sorted(set().union(*(blocks_module.gate_variables(b) for b in (*body, *own))))

    texts: set[str] = set()
    for assignment in _assignments(names):
        profile = replace(
            Profile(), **{k: v for k, v in assignment.items() if not k.startswith("pseudo:")}
        )
        free = {k.removeprefix("pseudo:"): v for k, v in assignment.items() if k.startswith("pseudo:")}
        if not any(blocks_module.survives_relaxed(b, profile, free) for b in body):
            continue
        survivors = [b for b in own if blocks_module.survives_relaxed(b, profile, free)]
        if not survivors:
            continue
        text = blocks_module.join(survivors)
        texts.add(text if relative != skills.SKILL_FILE else f"{head}\n\n{text}")
    return texts


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def lint(
    *,
    blocks: Mapping[str, Block] | None = None,
    catalogue: Mapping[str, Any] | None = None,
    grants: Mapping[str, tuple[Condition, ...]] | None = None,
) -> list[LintProblem]:
    """Check the block set against rules L1 to L10. An empty list is a clean tree.

    With no arguments, lints the shipped blocks, catalogue and grant table.
    """
    problems: list[LintProblem] = []
    loaded = _load(blocks, catalogue, grants, problems)
    if loaded is None:
        return problems
    table, cat, table_grants = loaded

    skill_bodies = {
        b for entry in cat["skills"] for row in entry["files"] for b in row["blocks"]
    }
    for block in table.values():
        _lint_parse(block, problems)
        _lint_commands(block, table_grants, problems)
        _lint_markers(block, problems)
        _lint_syntax(block, problems)
        _lint_placement(block, block.id in skill_bodies, problems)
        _lint_unsatisfiable(block, problems)
    _lint_catalogue(table, cat, problems)
    _lint_line_caps(table, cat, problems)
    _lint_mentions(table, cat, problems)
    return problems


def lint_rendered(profile: Profile) -> list[LintProblem]:
    """Render every document and skill file for *profile* and re-check the output.

    ``R1``: a rendered file is over its cap (a document leaves room for the
    skills table, which `lore init` fills). ``R2``: it mentions a command no
    capability of *profile* grants.
    """
    problems: list[LintProblem] = []
    catalogue = skills.load_catalogue()
    installed = skills.installed_skills(profile)
    grants_installed = bool(installed)

    for name, document in catalogue["documents"].items():
        text = skills.render_document(name, profile)
        if text is None:
            continue
        lines = len(text.splitlines())
        if TABLE_OPENER in text:
            lines += len(installed)
        if lines > document["max_lines"]:
            problems.append(LintProblem("R1", f"documents.{name}", f"renders {lines} lines, over {document['max_lines']}"))
        for phrase in blocks_module.leaked_commands(text, profile, skills_installed=grants_installed):
            problems.append(LintProblem("R2", f"documents.{name}", f"mentions 'lore {phrase}', which is off"))

    oversize: Mapping[str, int] = catalogue.get("oversize", {})
    for skill_id in installed:
        for relative in skills.skill_files(skill_id, profile):
            text = skills.render_skill_file(skill_id, relative, profile) or ""
            limit = oversize.get(f"{skill_id}/{relative}", SKILL_LINE_CAP)
            if len(text.splitlines()) > limit:
                problems.append(
                    LintProblem("R1", f"{skill_id}/{relative}", f"renders {len(text.splitlines())} lines, over {limit}")
                )
            for phrase in blocks_module.leaked_commands(text, profile):
                problems.append(LintProblem("R2", f"{skill_id}/{relative}", f"mentions 'lore {phrase}', which is off"))
    return problems
