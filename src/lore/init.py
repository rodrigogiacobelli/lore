"""Project initialization logic for `lore init`.

Three things live here, in dependency order:

* the writers a marked block needs — ``write_marked_section`` and
  ``remove_marked_section`` — plus the two small renderers that produce the
  blocks Lore owns inside files the project owns;
* ``plan_init``, which composes the agent registry, the skill catalogue, the
  recorded answers and the install manifest into an ``InitPlan`` **without
  touching the working tree**;
* ``apply_init``, which performs one, writing the manifest last so an
  interrupted run leaves a state the next reconcile recovers from.

``run_init()`` is ``apply_init(plan_init())`` and keeps its zero-argument
signature: it is the pinned public contract (standards-public-api-stability),
and a positional-argument change would be a major bump.

**Every byte this module writes goes through ``lore.safewrite``**, and no write
site opens a path itself. That is what holds the two properties a scattering of
``write_text`` calls could not: nothing is written or removed through a link or
outside the project root, and nothing is ever truncated in place. A write site
that reached for ``Path.write_text`` again would quietly drop both.

Prompting is deliberately absent. ADR-011 forbids a rule that lives only in the
CLI, so every question `lore init` can ask is a keyword parameter on
``plan_init`` and ``prompts_needed`` tells the CLI which conditional questions
this project state justifies. A Python caller reaches the same behaviour
without a terminal.
"""

import textwrap
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path, PurePath, PurePosixPath
from typing import Any

from lore import agents as agent_registry
from lore import manifest, paths, reconcile, safewrite, skills, validators
from lore.config import (
    DEFAULT_CONFIG,
    load_config,
    recorded_keys,
    render_default_settings,
    render_known_keys_header,
    render_toml_value,
)
from lore.db import SCHEMA_VERSION, init_database
from lore.frontmatter import parse_frontmatter_text
from lore.initplan import (
    SUMMARY_ACTIONS,
    SUMMARY_ORDER,
    WRITING_ACTIONS,
    AccessMode,
    DesiredFile,
    FileAction,
    InitAnswers,
    InitPlan,
    InitResult,
    PlannedFile,
)


AGENT_TEMPLATE = "docs/LORE-AGENT.md"
"""The packaged instruction text. A render source, not a file `lore init` copies."""

_TABLE_OPENER = "<!-- lore:skills-table -->"
_TABLE_CLOSER = "<!-- lore:skills-table end -->"
_TABLE_HEADER = ("| Skill | What it does | Where |", "|---|---|---|")

DEFAULT_ACCESS_MODE = AccessMode.NATIVE
"""The access mode a run with no recorded answer uses (`init-access-mode`)."""

OWNED_KIND = "owned"
"""Lore wrote the whole file, and it is eligible for removal."""

SECTION_KIND = "section"
"""Lore wrote a marked block inside a file the project owns."""

MARKDOWN_MARKERS = ("<!-- lore:begin -->", "<!-- lore:end -->")
"""The marker pair for a markdown instruction file — comments in every renderer."""

GITIGNORE_MARKERS = (
    "# lore:begin — managed by `lore init`; edits between these markers are replaced",
    "# lore:end",
)
"""The marker pair a release before this one wrote into the root `.gitignore`.

Nothing writes it any more — see :data:`ROOT_GITIGNORE_PATH`. It is kept, and
kept spelled exactly as it shipped, because it is the only thing that can find
the block in a project that already carries one: the upgrade removes what these
two lines delimit, and a marker changed here strands that block for good.
"""

SKILLS_GITIGNORE_LORE_ONLY = "lore-only"
SKILLS_GITIGNORE_TOKENS = (SKILLS_GITIGNORE_LORE_ONLY, "none", "all")
"""How the installed skills are tracked in git (`init-skills-gitignore`)."""

ON_EXISTING_AGENT_FILE_TOKENS = ("append", "skip")
"""What to do with an instruction file that exists and carries no Lore markers.

Two answers, not three: `.lore/LORE-AGENT.md` is written either way, so the
`separate` option the draft offered produced identical bytes to `skip`.
"""

PROMPT_AGENTS = "agents"
PROMPT_ACCESS_MODE = "access-mode"
PROMPT_SKILL_FAMILIES = "skill-families"
PROMPT_EXISTING_AGENT_FILE = "on-existing-agent-file"
PROMPT_SKILLS_GITIGNORE = "skills-gitignore"
PROMPT_ON_CONFLICT = "on-conflict"

CONDITIONAL_PROMPTS = (
    PROMPT_EXISTING_AGENT_FILE,
    PROMPT_SKILLS_GITIGNORE,
    PROMPT_ON_CONFLICT,
)
"""The conditional questions, in the order the CLI asks them.

Each token is the ``plan_init`` keyword it fills, kebab-cased: the CLI asks,
then calls ``plan_init`` again with that keyword set. No prompt lives inside the
core function, which is how ADR-011 holds without a callback.
"""

PERSISTED_ANSWER_PROMPTS = {
    "init-agents": PROMPT_AGENTS,
    "init-access-mode": PROMPT_ACCESS_MODE,
    "init-skill-families": PROMPT_SKILL_FAMILIES,
    "init-skills-gitignore": PROMPT_SKILLS_GITIGNORE,
}
"""The four config keys that answer a question, and the question each answers."""


def answered_prompts(project_root: Path) -> frozenset[str]:
    """The questions this project has already recorded an answer to.

    A project is asked once (FR-10), so the CLI has to know which questions are
    settled before it decides what to ask. It learns it here rather than
    reading `.lore/config.toml` itself: ADR-021 constraint 2 makes the business
    layer a command-scoped key's only reader, and a second reader in `cli.py`
    would be exactly the duplicate implementation ADR-011 forbids.

    Presence is the test, not value — a recorded answer that happens to equal
    the built-in default is still an answer the project gave.
    """
    return frozenset(
        PERSISTED_ANSWER_PROMPTS[key]
        for key in recorded_keys(Path(project_root))
        if key in PERSISTED_ANSWER_PROMPTS
    )

MANIFEST_PATH = ".lore/.install-manifest.json"
LORE_DIR_PATH = ".lore"
CONFIG_PATH = ".lore/config.toml"
LORE_AGENT_PATH = manifest.LORE_AGENT_PATH
LORE_AGENT_SOURCE = "lore-agent"
"""The one file Lore writes outside a skills tree that is not an agent's own.

Declared where the rule that reads it lives — `manifest` refuses a recorded
path that is not one it knows, and a second spelling here would be a second
answer to "does this release install there?".
"""

ROOT_GITIGNORE_PATH = manifest.ROOT_GITIGNORE_PATH
"""The project's own `.gitignore`, which Lore used to write a marked block into.

No longer written, and still named: every line the block carried was already
ignored by the `*` opening `.lore/.gitignore`, so it decided nothing, and a
write into a file the user owns that buys nothing is a write that should not
happen. What is left is the removal — the block sits inside Lore's own markers
in every project initialised before this release, so it is Lore's to take back,
and `_marker_pair` needs this name to know which pair to look for.

The path is declared where the rule that reads it lives: `manifest` refuses a
recorded path that is neither this nor under a skills root, and a second
spelling here would be a second answer to "may this release remove there?".
"""


_GLOSSARY_SKELETON = (
    "# Project glossary — see the Glossary section of .lore/codex/codex.md.\n"
    "# Before adding a term, run: `lore artifact show glossary-design`.\n"
    "# Auto-surfaced on `lore codex show`. Toggle via .lore/config.toml.\n"
    "items: []\n"
)


def _reject_occupied_path(target: Path, project_root: Path | None = None) -> None:
    """Stop when *target* is not a path Lore may write a file to.

    `lore init` writes files, and every write it performs assumes the path is
    either free or a file **of Lore's own**. Three ways it is neither, and all
    three used to end in a stdlib traceback or, worse, a silent success:

    * a directory in the place of a file — ``IsADirectoryError``, frames all
      stdlib, nothing naming which of thirty paths stopped the run;
    * a symlink — followed without a word, which put a file outside the project
      and, under `--on-conflict overwrite`, truncated one there;
    * a path that resolves out of the project through a linked ancestor.

    Naming the path and the repair is what conceptual-workflows-error-handling
    asks for instead, and stopping here leaves the manifest unwritten — the
    interrupted-run state the next `lore init` already reconciles.

    Checked inside the writer rather than at each caller, because the set of
    paths a run writes is not known until the plan is: the seeded files come
    from this module and the rest from the reconciliation table.
    """
    safewrite.refuse_unsafe(target, project_root=project_root)


def _seed_skeleton_if_absent(
    target: Path, content: str, label: str, *, project_root: Path | None = None
) -> list[str]:
    """Write ``content`` to ``target`` only when the file does not exist.

    Creates parent directories as needed.  Idempotent — existing files are
    left byte-for-byte untouched.  Returns a single-element status message
    list when a file is created, or an empty list when skipped.

    The path is checked before the existence test rather than inside the write:
    a link sitting here is refused even though this branch would never have
    written through it, because the next run's answer must not depend on which
    branch looked.
    """
    _reject_occupied_path(target, project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return []
    safewrite.atomic_write_text(target, content, project_root=project_root)
    return [f"  Created {label}"]


def _seed_codex_md(project_root: Path) -> list[str]:
    """Seed `.lore/codex/codex.md` from the packaged artifact if absent.

    Reads `src/lore/defaults/artifacts/codex/codex.md`, rewrites the
    frontmatter `id: example-codex` line to `id: codex`, and writes it
    via the idempotent `_seed_skeleton_if_absent` helper.
    """
    content = (
        resources.files("lore.defaults")
        .joinpath("artifacts/codex/codex.md")
        .read_text(encoding="utf-8")
    )
    rewritten = content.replace("id: example-codex", "id: codex", 1)
    return _seed_skeleton_if_absent(
        paths.codex_md_path(project_root),
        rewritten,
        "codex/codex.md",
        project_root=project_root,
    )


def _replace_leading_comment_block(
    target: Path, header: str, *, project_root: Path | None = None
) -> None:
    """Replace *target*'s leading contiguous run of ``#`` lines with *header*.

    The run ends at the first line that is not a comment — a setting, a blank
    line, anything. Every line from there onward is written back byte-identical,
    so a project's values, ordering, blank lines and inline comments all survive
    a header refresh, and a comment further down the file is the project's own.

    A file with no leading comments gains the header as a prepend, losing no
    line; an empty file becomes the header alone.
    """
    lines = manifest.read_text(target).splitlines(keepends=True)
    first_setting = next(
        (
            index
            for index, line in enumerate(lines)
            if not line.lstrip().startswith("#")
        ),
        len(lines),
    )
    safewrite.atomic_write_text(
        target, header + "".join(lines[first_setting:]), project_root=project_root
    )


def _seed_config(project_root: Path) -> list[str]:
    """Seed `.lore/config.toml`, or refresh the known-key header it carries.

    Absent: the generated header plus every known key at its default. Present:
    only the leading comment block is regenerated, which is how a project
    initialised before a key existed learns about it (FR-36). The generated
    block says it is regenerated, which is the ADR-013 exception this bends —
    the comment block is Lore's, every settings line is the project's.
    """
    target = paths.config_path(project_root)
    _reject_occupied_path(target, project_root)
    header = render_known_keys_header()
    if target.exists():
        _replace_leading_comment_block(target, header, project_root=project_root)
        return []
    safewrite.atomic_write_text(
        target, header + render_default_settings(), project_root=project_root
    )
    return ["  Created config.toml"]


def _seed_glossary(project_root: Path) -> list[str]:
    """Seed `.lore/codex/glossary.yaml` and `.lore/config.toml`.

    The glossary is written only when absent and is never touched again. The
    config file is seeded the same way, with one exception: its known-key
    comment header is regenerated on every run (see `_seed_config`).
    """
    messages = _seed_skeleton_if_absent(
        paths.glossary_path(project_root),
        _GLOSSARY_SKELETON,
        "codex/glossary.yaml",
        project_root=project_root,
    )
    messages.extend(_seed_config(project_root))
    return messages


def _seed_user_tracked(project_root: Path) -> list[str]:
    """Seed all user-tracked files (codex.md, glossary.yaml, config.toml).

    Idempotent: existing files are left byte-for-byte untouched.  Emits
    `Created` messages in the order codex.md, glossary.yaml, config.toml.
    """
    messages = _seed_codex_md(project_root)
    messages.extend(_seed_glossary(project_root))
    return messages


@dataclass(frozen=True)
class _SeedTree:
    """One packaged tree `lore init` copies into `.lore/` on every run.

    These are Lore's own files in Lore's own directory: `.lore/.gitignore`
    ignores each ``default/`` tree wholesale, and reconciliation does not manage
    them — no manifest row, no hash, no conflict. What that buys is an upgrade
    that cannot fail on them; what it costs is the two things fixed here. They
    were absent from the plan, so a summary promising "every file it would
    create, replace or remove" named about seventy fewer than the run wrote.
    And nothing removed a file the release stopped shipping, so a project seeded
    by 0.1.0 kept artifacts at paths since renamed, failing `lore health`
    against a schema that had moved on.
    """

    package: str
    """The subdirectory of ``lore.defaults`` the files come from."""

    relative: str
    """Where they land under `.lore/`. Empty for ``docs``, which lands at the root."""

    exclude: frozenset[str] = frozenset()
    """Directory names skipped at every level, in the tree and in the prune alike."""

    exclude_files: frozenset[str] = frozenset()
    """File names something else produces — ``LORE-AGENT.md`` is rendered, not copied."""

    prune: bool = False
    """Whether a file this release no longer ships is removed.

    True for the four ``default/`` trees, which are Lore's alone. False for
    ``docs``, whose target is `.lore/` itself: pruning there would delete the
    project.
    """

    @property
    def label(self) -> str:
        """The prefix the status lines put on a path from this tree.

        The tree's destination, never its source package. ``docs`` lands at
        `.lore/` itself and so carries no prefix at all: reporting
        ``docs/GETTING-STARTED.md`` named a path that does not exist, and a plan
        cannot promise to list every file the run writes while the run reports
        them under a directory of its own invention.
        """
        return self.relative

    @property
    def path(self) -> str:
        """The tree's repo-relative root."""
        return f".lore/{self.relative}" if self.relative else ".lore"

    def target(self, project_root: Path) -> Path:
        return paths.lore_dir(project_root) / self.relative


SEEDED_TREES = (
    _SeedTree("doctrines", "doctrines/default", prune=True),
    _SeedTree("knights", "knights/default", prune=True),
    _SeedTree(
        "artifacts", "artifacts/default", exclude=frozenset({"bootstrap"}), prune=True
    ),
    _SeedTree("docs", "", exclude_files=frozenset({"LORE-AGENT.md"})),
    _SeedTree("watchers", "watchers/default", prune=True),
)
"""Every packaged tree `_seed_lore_directory` copies, in the order it copies them."""

UNTRACKED_WRITES = (
    ".lore/.gitignore",
    ".lore/lore.db",
    ".lore/codex/codex.md",
    ".lore/codex/glossary.yaml",
    CONFIG_PATH,
    MANIFEST_PATH,
)
"""The single files `lore init` writes that reconciliation does not manage.

Named here for one reason: the plan is the consent surface. `lore init --help`
says the flow "prints every file it would create, replace or remove, and writes
nothing until you confirm", and a plan that omitted these was asking for consent
to something narrower than what ran.
"""


def _defaults_tree_files(
    source_package: str,
    exclude: set[str] | None = None,
    exclude_files: set[str] | None = None,
) -> tuple[tuple[str, object], ...]:
    """Every file a seeded tree would copy, as ``(relative POSIX path, node)``.

    The walk itself, separated from the copying, because three callers need the
    same answer and only one of them writes: the copy, the plan that has to name
    what the copy will overwrite, and the prune that removes what this release
    stopped shipping. Two implementations of "which files are in this tree"
    would be two ways to disagree about it.

    Sorted, so a run's status lines and the plan's listing arrive in the same
    order twice running.
    """
    source_root = resources.files("lore.defaults").joinpath(source_package)
    found: list[tuple[str, object]] = []

    def _walk(node, prefix: str) -> None:
        for item in sorted(node.iterdir(), key=lambda entry: entry.name):
            if item.is_dir():
                if exclude and item.name in exclude:
                    continue
                _walk(item, f"{prefix}{item.name}/")
            elif item.is_file():
                if exclude_files and item.name in exclude_files:
                    continue
                found.append((f"{prefix}{item.name}", item))

    _walk(source_root, "")
    return tuple(found)


def _copy_defaults_tree(
    source_package: str,
    target_dir: Path,
    exclude: set[str] | None = None,
    label: str | None = None,
    exclude_files: set[str] | None = None,
) -> list[str]:
    """Copy default files from a nested package subdirectory tree, overwriting existing files.

    Args:
        source_package: Subdirectory name within ``lore.defaults`` to copy from.
        target_dir: Destination directory where files are written.
        exclude: Optional set of directory names to skip at the top level.
        label: Prefix used in status messages instead of ``source_package``.
               Useful when the target path differs from the package name. An
               empty string means no prefix — the tree lands at *target_dir*
               itself, so a path from it is already the path it is written to.
        exclude_files: Optional set of file names this tree does not copy
               verbatim, because something else produces them. ``docs/`` holds
               one such file: ``LORE-AGENT.md`` is rendered, not copied.

    Returns:
        List of human-readable status messages (one per file copied).
    """
    messages = []
    prefix = source_package if label is None else label
    for relative, item in _defaults_tree_files(source_package, exclude, exclude_files):
        dest = target_dir / relative
        verb = "Updated" if dest.is_file() else "Created"
        # The tree is copied *into* ``target_dir``, so that is the boundary a
        # copy must stay inside — a linked subdirectory that leaves it is
        # refused by name rather than followed.
        safewrite.atomic_write_text(dest, item.read_text(), project_root=target_dir)
        shown = f"{prefix}/{relative}" if prefix else relative
        messages.append(f"  {verb} {shown}")
    return messages


def _seed_tree(project_root: Path, spec: _SeedTree) -> list[str]:
    """Copy one packaged tree in, then remove what this release stopped shipping."""
    target = spec.target(project_root)
    messages = _copy_defaults_tree(
        spec.package,
        target,
        exclude=set(spec.exclude) or None,
        label=spec.label,
        exclude_files=set(spec.exclude_files) or None,
    )
    if spec.prune:
        messages.extend(_prune_seeded_tree(target, spec))
    return messages


def _prune_seeded_tree(target_dir: Path, spec: _SeedTree) -> list[str]:
    """Remove files under *target_dir* this release no longer ships.

    The rule is the one the tree already lives by rather than a per-version
    migration chain: a ``default/`` tree is Lore's, so a file in it that Lore
    does not ship is stale, whatever release put it there and whether it was
    renamed, merged or dropped. That is what makes a hop from the oldest release
    land on the same tree as a fresh install.

    Reported, never silent, and never taken on trust: a link is left alone, and
    an unlink the filesystem refuses is skipped rather than raised — tidying is
    the least important thing an initialisation does.
    """
    if target_dir.is_symlink() or not target_dir.is_dir():
        return []

    shipped = {
        target_dir / relative
        for relative, _ in _defaults_tree_files(
            spec.package, set(spec.exclude) or None, set(spec.exclude_files) or None
        )
    }
    messages: list[str] = []
    removed: list[Path] = []
    for candidate in sorted(target_dir.rglob("*")):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        if candidate in shipped:
            continue
        within = candidate.relative_to(target_dir)
        if spec.exclude & set(within.parts[:-1]):
            continue
        try:
            candidate.unlink()
        except OSError:
            continue
        removed.append(candidate)
        messages.append(
            f"  Removed {spec.label}/{within.as_posix()} — no longer shipped"
        )

    try:
        reconcile.prune_empty_dirs(removed, target_dir)
    except OSError:
        pass
    return messages


def seeded_paths() -> tuple[str, ...]:
    """Every path `lore init` writes that the reconciliation table does not cover.

    The seeded trees plus the handful of single files in ``UNTRACKED_WRITES``.
    Read by ``plan_init`` alone, so the plan can name what the run will
    overwrite; nothing here consults the working tree, and nothing here writes.
    """
    found = list(UNTRACKED_WRITES)
    for spec in SEEDED_TREES:
        found.extend(
            f"{spec.path}/{relative}"
            for relative, _ in _defaults_tree_files(
                spec.package, set(spec.exclude) or None, set(spec.exclude_files) or None
            )
        )
    return tuple(sorted(set(found)))


# ---------------------------------------------------------------------------
# The agent instruction text
# ---------------------------------------------------------------------------


def _read_agent_template() -> str:
    """Return the packaged instruction template.

    The single read step, so a test can inject a template without touching the
    shipped file.
    """
    return (
        resources.files("lore.defaults").joinpath(AGENT_TEMPLATE).read_text(encoding="utf-8")
    )


def _skill_description(skill_id: str) -> str:
    """Return a skill's own one-line description, from its packaged frontmatter.

    The description is authored once, in the skill's ``SKILL.md``, and is
    deliberately absent from the catalogue (standards-dry). Returns an empty
    string when the frontmatter carries none — a `lore health --scope skills`
    finding, not a reason to fail an installation.
    """
    text = (
        resources.files("lore.defaults")
        .joinpath(f"skills/{skill_id}/SKILL.md")
        .read_text(encoding="utf-8")
    )
    record = parse_frontmatter_text(text, required_fields=("name", "description"))
    return record["description"].strip() if record else ""


def _posix_root(install_root: PurePath | str) -> PurePosixPath:
    """Normalise an install root to forward slashes, whatever wrote it.

    The table is markdown a human reads and an agent follows; a backslash in it
    on Windows would name a path no documentation elsewhere uses.
    """
    if isinstance(install_root, PurePath):
        return PurePosixPath(install_root.as_posix())
    return PurePosixPath(install_root)


def _render_skills_table(
    skill_ids: tuple[str, ...] | list[str], install_roots: Iterable[PurePath | str]
) -> str:
    """Render the installed skills as a markdown table, one row per id.

    Every root a skill was installed into is named in its row. A project
    selecting an agent with a native skills directory *and* one without gets two
    copies of each skill, and ``.lore/LORE-AGENT.md`` is the canonical text for
    both of those agents — naming one root would send half its readers to a
    directory their agent does not read.

    Sorted, so two runs with the same selection produce the same bytes — the
    manifest hashes this text. An empty selection renders the header alone
    rather than raising: a project may legitimately install no skills.
    """
    roots = [_posix_root(root) for root in install_roots]
    rows = []
    for skill_id in sorted(skill_ids):
        where = ", ".join(f"`{root / skill_id}/`" for root in roots)
        rows.append(f"| `{skill_id}` | {_skill_description(skill_id)} | {where} |")
    return "\n".join([*_TABLE_HEADER, *rows]) + "\n"


def _replace_skills_table_region(text: str, table: str, source: str) -> str:
    """Swap the ``<!-- lore:skills-table -->`` region's body for *table*.

    Raises ``ValueError`` naming the source and the line for an unterminated
    region or a closer with no opener. A template that cannot say where its
    generated table goes is a build defect, the same class as an unterminated
    access block.
    """
    kept: list[str] = []
    open_line = 0

    for lineno, line in enumerate(text.splitlines(keepends=True), start=1):
        stripped = line.strip()

        if stripped == _TABLE_OPENER:
            if open_line:
                raise ValueError(f"{source}:{lineno}: nested {_TABLE_OPENER} region")
            open_line = lineno
            kept.append(table)
            continue

        if stripped == _TABLE_CLOSER:
            if not open_line:
                raise ValueError(f"{source}:{lineno}: {_TABLE_CLOSER} with no open region")
            open_line = 0
            continue

        if not open_line:
            kept.append(line)

    if open_line:
        raise ValueError(f"{source}:{open_line}: unterminated {_TABLE_OPENER} region")

    return "".join(kept)


def render_agent_instructions(
    *,
    skill_ids: tuple[str, ...] | list[str],
    install_roots: Iterable[PurePath | str],
    access_mode: AccessMode,
) -> str:
    """Render the packaged instruction template into one project's text.

    Two regions are generated rather than authored: the skills table, filled
    from *skill_ids* and every root they were installed into, and the
    access-mode blocks, resolved for *access_mode* by ``skills.render`` — the
    one block selector. Neither marker survives.

    *install_roots* is what the text is written *for*: one agent's own block
    names that agent's directory, and the canonical ``.lore/LORE-AGENT.md``
    names every directory the run installed into.

    Deterministic — the same arguments produce the same bytes, because the
    manifest records this text by hash.
    """
    text = _read_agent_template()
    table = _render_skills_table(skill_ids, install_roots)
    text = _replace_skills_table_region(text, table, AGENT_TEMPLATE)
    return skills.render(text, access_mode, source=AGENT_TEMPLATE)


# ---------------------------------------------------------------------------
# Marked blocks inside files the project owns
# ---------------------------------------------------------------------------


def _marker_pair(target: str | PurePath) -> tuple[str, str]:
    """Return the begin/end marker pair for *target*.

    A `.gitignore` takes `#`-comment markers because a stray HTML comment in one
    is a pattern, not a comment. Everything else — `CLAUDE.md`, `AGENTS.md`,
    `.cursor/rules/lore.mdc` — takes HTML comments.

    The `.gitignore` branch is now reached only on the way *out*: no release
    writes a block there, and the pair is what lets an upgrade find and delete
    the block an older one left.
    """
    name = PurePosixPath(manifest.to_posix(str(target))).name
    return GITIGNORE_MARKERS if name == ROOT_GITIGNORE_PATH else MARKDOWN_MARKERS


def _locate_block(
    lines: list[str], markers: tuple[str, str], target: Path
) -> tuple[int, int] | None:
    """Return the marker line indices in *lines*, or None when there is no block.

    ``manifest.marker_span`` holds the rule, because the *reader* — the digest
    reconciliation takes of the block — has to apply exactly the same one. It
    did not: the reader took the first pair it found, so a file torn into two
    pairs by concurrent runs digested as already-correct and the run that would
    have raised here never got the chance.
    """
    begin, end = markers
    return manifest.marker_span(lines, begin, end, source=target)


def _newline_terminated(text: str) -> str:
    """Return *text* ending in a newline, so a marker never shares a line."""
    return text if not text or text.endswith("\n") else text + "\n"


def write_marked_section(
    target: Path,
    block_text: str,
    *,
    markers: tuple[str, str],
    project_root: Path | None = None,
) -> None:
    """Write *block_text* into *target* between *markers*.

    Three cases, and every one of them is a user-file-safety branch:

    * the file is absent — it is created holding the block alone;
    * the file exists without markers — the block is appended and every prior
      byte is left where it was;
    * the file already carries the markers — only the text between them moves.

    Adopting Lore costs the project nothing it has already written.

    The splice is a read-modify-write, and the write half is where two
    concurrent runs used to destroy 1121 lines of a user's `CLAUDE.md`: the old
    ``write_text`` truncated the file in place, so a second process reading in
    that window spliced its block onto a torn prefix and then wrote *that*
    back. Going through ``safewrite`` makes the file arrive by ``os.replace``,
    which no reader and no second writer can catch half-done — two runs racing
    on an unmarked file now both append the same block to the same bytes and
    agree on the result.
    """
    begin, end = markers
    block = f"{begin}\n{_newline_terminated(block_text)}{end}\n"
    target = Path(target)
    _reject_occupied_path(target, project_root)

    if not target.exists():
        safewrite.atomic_write_text(target, block, project_root=project_root)
        return

    text = manifest.read_text(target)
    lines = text.splitlines(keepends=True)
    found = _locate_block(lines, markers, target)

    if found is None:
        safewrite.atomic_write_text(
            target, _newline_terminated(text) + block, project_root=project_root
        )
        return

    opener, closer = found
    safewrite.atomic_write_text(
        target,
        "".join([*lines[:opener], block, *lines[closer + 1 :]]),
        project_root=project_root,
    )


def remove_marked_section(
    target: Path, *, markers: tuple[str, str], project_root: Path | None = None
) -> bool:
    """Delete the marked block from *target*; return whether one was there.

    The two marker lines go with it and every other byte stays. Retiring an
    agent must never delete the file the user owns — and a link at this path is
    not the file Lore wrote a block into, so it is left exactly as it is.
    """
    target = Path(target)
    if target.is_symlink() or not target.is_file():
        return False

    lines = manifest.read_text(target).splitlines(keepends=True)
    found = _locate_block(lines, markers, target)
    if found is None:
        return False

    opener, closer = found
    safewrite.atomic_write_text(
        target,
        "".join([*lines[:opener], *lines[closer + 1 :]]),
        project_root=project_root,
    )
    return True


def _has_marked_block(target: Path, markers: tuple[str, str]) -> bool:
    """True when *target* exists and already carries a complete Lore block."""
    if not target.is_file():
        return False
    begin, end = markers
    block = manifest.section_text(
        manifest.read_text(target), begin, end, source=target
    )
    return block is not None


_SKILLS_GITIGNORE_ALL = (
    "# Auto-generated by `lore init`. `--skills-gitignore all` ignores this whole\n"
    "# directory, your own skills included. The rule itself stays tracked.\n"
    "*\n"
    "!.gitignore\n"
)

_SKILLS_GITIGNORE_LORE_ONLY_HEADER = (
    "# Auto-generated by `lore init`. Lists the skills Lore installed here so they\n"
    "# stay untracked. Your own skills in this directory are not ignored.\n"
)


def render_skills_gitignore(
    skill_ids, skills_gitignore: str = SKILLS_GITIGNORE_LORE_ONLY
) -> str | None:
    """Render the rule that lives beside the installed skills, or None.

    One file per install root, and the answer decides what is in it:

    * ``lore-only`` — every installed skill, by directory name. Anything else
      in the tree, which is the user's own authored work, stays tracked.
    * ``all`` — the whole directory, the user's own skills included, with the
      rule itself un-ignored so it reaches the clone.
    * ``none`` — no file at all, which is what ``None`` says. Because all three
      answers are manifest-tracked, switching between them replaces or removes
      the previous file cleanly.
    """
    if skills_gitignore == "all":
        return _SKILLS_GITIGNORE_ALL
    if skills_gitignore != SKILLS_GITIGNORE_LORE_ONLY:
        return None
    return _SKILLS_GITIGNORE_LORE_ONLY_HEADER + "".join(
        f"{skill_id}/\n" for skill_id in sorted(skill_ids)
    )


# ---------------------------------------------------------------------------
# The desired set — every path this release would write, given the answers
# ---------------------------------------------------------------------------


def _section(path: str, source: str, text: str) -> DesiredFile:
    """A marked block inside a file the project owns.

    ``content`` is the block text alone, markers excluded, because that is what
    the manifest hashes: a user editing prose elsewhere in the same file never
    registers as a conflict.
    """
    return DesiredFile(
        path=path, kind=SECTION_KIND, source=source, content=text.encode("utf-8")
    )


def _owned(path: str, source: str, text: str) -> DesiredFile:
    """A whole file Lore writes."""
    return DesiredFile(
        path=path, kind=OWNED_KIND, source=source, content=text.encode("utf-8")
    )


def build_desired(
    *, project_root: Path, targets, answers: InitAnswers
) -> dict[str, DesiredFile]:
    """Compose everything this release would write, keyed by repo-relative path.

    The skills come from the catalogue; the rest is produced here — the
    canonical instruction text, each selected agent's marked block and the
    installed-skill listing. The seeded ``.lore/`` default trees are
    deliberately absent: re-init overwrites those in place and reconciliation
    does not manage them.

    Takes the resolved answers rather than loose keywords so ``plan_init`` and
    ``apply_init`` cannot compose the same desired set two different ways.
    """
    access_mode = answers.access_mode
    skills_gitignore = answers.skills_gitignore
    desired = dict(
        skills.desired_files(
            targets=targets,
            skill_families=answers.skill_families,
            access_mode=access_mode,
        )
    )
    skill_ids = skills.skills_in_families(answers.skill_families)
    roots = skills.install_roots(targets)

    # The canonical rendered text, written whether or not an agent is selected,
    # and read by every selected agent — so it names every root, not the first.
    desired[LORE_AGENT_PATH] = _owned(
        LORE_AGENT_PATH,
        LORE_AGENT_SOURCE,
        render_agent_instructions(
            skill_ids=skill_ids, install_roots=roots, access_mode=access_mode
        ),
    )

    for target in targets:
        if not target.instruction_file:
            continue
        if _leaves_existing_file_alone(
            project_root, target.instruction_file, answers.on_existing_agent_file
        ):
            continue
        desired[target.instruction_file] = _section(
            target.instruction_file,
            f"agent-instructions:{target.id}",
            render_agent_instructions(
                skill_ids=skill_ids,
                install_roots=(target.skills_dir or skills.LORE_SKILLS_ROOT,),
                access_mode=access_mode,
            ),
        )

    # The root `.gitignore` is deliberately absent. Lore used to write a marked
    # block there naming its generated artefacts, and every one of those paths
    # was already ignored by the `*` opening `.lore/.gitignore`: deleting the
    # whole block from a real project left `git check-ignore -v` reporting the
    # identical deciding rule for every path. A project that still carries the
    # block therefore meets it as a path Lore recorded and no longer desires,
    # which is the retirement row — the block goes, the rest of the file stays.

    listing = render_skills_gitignore(skill_ids, skills_gitignore)
    if listing is not None and skill_ids:
        # Every root the skills went to, not every selected agent: five of the
        # six agents have no native skills directory, and iterating targets
        # left `.lore/skills/` with no rule of its own — so the blanket
        # `skills/` line the seeded `.lore/.gitignore` used to carry decided
        # all three answers there, silently ignoring the user's own skills.
        #
        # And nothing at all when nothing is installed: the file governs Lore's
        # skills, and a directory holding only the user's own is not a
        # directory this answer has anything to say about.
        for root in roots:
            path = f"{root}/{ROOT_GITIGNORE_PATH}"
            desired[path] = _owned(
                path, reconcile.skills_gitignore_source(root), listing
            )

    return desired


def _is_unmarked_existing_file(project_root: Path, relative: str) -> bool:
    """True in the one case FR-4 asks about: the file is there and has no markers."""
    target = manifest.resolve_path(project_root, relative)
    return target.is_file() and not _has_marked_block(target, _marker_pair(relative))


def _leaves_existing_file_alone(
    project_root: Path, relative: str, on_existing_agent_file: str
) -> bool:
    """True when the ``skip`` answer applies to *relative*.

    A file that does not exist is created with markers and a file that already
    has them has its block replaced; neither asks, so neither can be skipped.
    """
    return on_existing_agent_file == "skip" and _is_unmarked_existing_file(
        project_root, relative
    )


# ---------------------------------------------------------------------------
# plan_init — compute an initialisation without performing it
# ---------------------------------------------------------------------------


def _reject(message: str | None) -> None:
    """Raise ``ValueError`` on a validator's error string; do nothing on None."""
    if message is not None:
        raise ValueError(message)


def _unknown_token(name: str, value: str, accepted: tuple[str, ...]) -> str | None:
    """The error string for a token out of set, or None when it is in."""
    if value in accepted:
        return None
    return f"Unknown {name}: '{value}'. Accepted tokens: {', '.join(accepted)}."


RECORDED_ANSWER_FLAGS = {
    "agents": ("init-agents", "--agent"),
    "access_mode": ("init-access-mode", "--access"),
    "skill_families": ("init-skill-families", "--skills"),
    "skills_gitignore": ("init-skills-gitignore", "--skills-gitignore"),
}
"""The four persisted answers: the key that records each, and the flag that replaces it.

Read by ``_reject_recorded`` for the way out of a recorded answer that no
longer validates, and by `lore init` for the questions a run with no terminal
cannot ask. One table, because the two have to name the same four flags.
"""

AGENTS_CONFIG_KEY = RECORDED_ANSWER_FLAGS["agents"][0]
"""The `.lore/config.toml` key whose *presence* means somebody answered "which agents"."""


def missing_recorded_answers(answers: Mapping[str, Any]) -> tuple[str, ...]:
    """Which of the four recorded answers *answers* leaves unsupplied.

    Returned as parameter names, in ``RECORDED_ANSWER_FLAGS`` order, because
    both callers name the same four things in different vocabularies: the CLI
    maps them through the table to `--agent`, `--access`, `--skills` and
    `--skills-gitignore`, and `plan_init` reports them as its own keywords.

    The rule they share is `--reconfigure`'s: it means "ask me again", so a run
    that supplies no new answer for a question is not reconfiguring it — it is
    silently re-resolving it from the built-in default. Pure argument
    inspection, with nothing terminal-shaped about it, which is why it may not
    live in `cli.py` alone (ADR-011).
    """
    return tuple(field for field in RECORDED_ANSWER_FLAGS if answers.get(field) is None)


def _reject_recorded(message: str | None, *, field: str, value, recorded: bool) -> None:
    """Raise a validator's error, saying where the value came from when it was recorded.

    An answer taken from ``.lore/config.toml`` is one nobody typed on this run,
    and every later run takes it again: without naming the key that holds it and
    the flag that replaces it, a project whose recorded answer cannot resolve
    has no way back that does not involve a text editor.
    """
    if message is None:
        return
    if not recorded:
        raise ValueError(message)
    key, flag = RECORDED_ANSWER_FLAGS[field]
    raise ValueError(
        f"{message} {key} in .lore/config.toml records "
        f"{render_toml_value(value)}, and this run took it from there. "
        f"Re-run with {flag} to record a new answer."
    )


def _token_sequence(value, *, parameter: str, noun: str) -> list[str] | None:
    """*value* as a list of tokens, or ``ValueError`` naming the parameter.

    Two shapes get here that the CLI's own layer can never produce, and both
    used to fail from inside rather than at the boundary. A non-iterable reached
    ``list()`` and raised the interpreter's ``'int' object is not iterable``,
    which names no parameter; a **bare string** is iterable, so ``agents=
    "claude"`` was six agents and the run was rejected for an agent ``'c'``
    nobody typed. That is the single likeliest mistake a library caller makes,
    because the flag it mirrors is singular (``--agent claude``).
    """
    if value is None:
        return None
    if isinstance(value, (str, bytes, bytearray)):
        shown = value.decode(errors="replace") if isinstance(value, (bytes, bytearray)) else value
        raise ValueError(
            f"{parameter} takes a sequence of {noun}, not a single string — "
            f"pass [{shown!r}] rather than {value!r}."
        )
    if not isinstance(value, Iterable):
        raise ValueError(
            f"{parameter} takes a sequence of {noun}, not {type(value).__name__}."
        )
    return list(value)


def _selected_targets(agent_ids) -> tuple:
    """Registry rows for *agent_ids*, deduplicated, in the order the registry declares."""
    wanted = set(agent_ids)
    return tuple(row for row in agent_registry.load_registry() if row.id in wanted)


def _recorded_entries(project_root: Path) -> tuple[dict, frozenset[str]]:
    """The ``recorded`` half of the comparison, and the paths Lore has shipped to.

    A project initialised before the manifest existed has no manifest, so the
    packaged historical hashes stand in. Once one exists it does not wholly
    replace them: a manifest is a record of what one run wrote, not proof of
    what is on disk now, and something else may have written since. Rolling
    back to an older `lore` and re-initialising is the case that showed it —
    the old binary reinstalls thirteen retired skills and rewrites two current
    ones with its own text, and the manifest the newer release then reads
    mentions none of it. Trusting it alone stranded those directories
    permanently: no later `lore init` had a record that would ever remove them.

    Three grades of evidence, and they do not all say the same *kind* of thing:

    * the **manifest** — the paths this project's own runs wrote, with the hash
      each was written at: true when it was written, silent about since;
    * an **installed** hit — the bytes on disk *are* bytes Lore shipped for that
      path, which the disk agrees with right now;
    * a **guess** — ``retired_edits`` and ``shipped_paths``, which say the
      packaged table has a row at this name and something else under the same
      root proves Lore installed *somewhere* in it. Evidence about the tree,
      offered in place of evidence about the path.

    Under the ownership ruling the recorded set authorises destruction, so the
    guess only ever runs where nothing better exists. **A project holding a
    manifest has the answer already**: the manifest is the list of what Lore
    installed *here*, and a path missing from it is missing because no run ever
    wrote it — including every path a run met and deliberately declined to take
    under ``--on-conflict skip``. Merging the guess in on top of it claimed
    those paths back, on evidence drawn from the neighbours Lore had just
    installed around them: a skill the project authored at a retired id was
    unlinked, and a file kept by name on one run was overwritten on the next.
    The two records that speak about *this* project still rank as they did, the
    one that knows the bytes on disk last.

    The second return value is none of those grades and never merged with them:
    the paths the historical table knows, whatever is there now. It authorises
    nothing on its own and only settles how a conflict is worded — see
    ``reconcile``'s *installed_before*. It is a guess too, and goes the same way.
    """
    records = reconcile.legacy_records(
        project_root, retirement_reason=skills.retirement_for
    )
    stored = manifest.load(project_root)
    if stored is None:
        merged = dict(records.retired_edits)
        merged.update(records.installed)
        return merged, records.shipped_paths

    merged = dict(stored.by_path)
    merged.update(records.installed)
    return merged, frozenset()


AGENT_INSTRUCTIONS_SOURCE_PREFIX = "agent-instructions:"


def agents_in_evidence(recorded) -> tuple[str, ...]:
    """The agents this project shows evidence of having been set up for.

    Two signals, both drawn from the ``recorded`` set and so from files Lore
    itself installed: a marked instruction block written for an agent, and
    Lore's own skills sitting in an agent's skills directory. The second is what
    reaches a pre-manifest project, because the ``GETTING-STARTED.md`` those
    releases shipped told people to run ``cp -r .lore/skills/. .claude/skills/``.

    A directory holding only the user's own skills is not evidence of anything:
    nothing in it is in ``recorded``, which is the same reason nothing in it is
    ever touched.
    """
    prefix = AGENT_INSTRUCTIONS_SOURCE_PREFIX
    registry = agent_registry.load_registry()
    known = {row.id for row in registry}
    found = {
        entry.source[len(prefix) :]
        for entry in recorded.values()
        if entry.source.startswith(prefix)
    } & known
    for row in registry:
        if row.skills_dir and any(
            path.startswith(f"{row.skills_dir}/") for path in recorded
        ):
            found.add(row.id)
    return tuple(row.id for row in registry if row.id in found)


def unmarked_instruction_files(project_root: Path, targets) -> tuple[str, ...]:
    """The selected agents' instruction files that exist and carry no markers.

    The FR-4 gate and the question that gate opens both read this, so the
    question names exactly the files it is about: an agent whose file does not
    exist yet gets one written with markers, which is not what is being asked.
    """
    return tuple(
        target.instruction_file
        for target in targets
        if target.instruction_file
        and _is_unmarked_existing_file(project_root, target.instruction_file)
    )


def _prompts_needed(project_root: Path, targets, unresolved) -> tuple[str, ...]:
    """Name the conditional questions this project state justifies.

    This is what lets the CLI know a prompt is warranted without the core
    function owning one: it inspects the tokens, asks, and calls ``plan_init``
    again with the answers filled in.

    *unresolved* is every row the ``on_conflict`` answer can still settle, which
    since the ownership ruling is one thing: a path holding a file Lore did not
    install. Lore's own files take no answer — an edited one is overwritten,
    an edited retired one removed — and a refused path takes none either, so
    neither opens a question. ``reconcile.unsettled`` decides which rows those
    are; this only asks whether there are any.
    """
    needed = []
    if unmarked_instruction_files(project_root, targets):
        needed.append(PROMPT_EXISTING_AGENT_FILE)
    if skills.install_roots(targets):
        # Every project has an install root, so every project has a tracking
        # answer worth asking for. The gate used to read `target.skills_dir`,
        # which is null for five of the six agents — so the projects whose
        # skills land in `.lore/skills/` were never asked the one question that
        # decides whether their own authored skills reach a clone.
        needed.append(PROMPT_SKILLS_GITIGNORE)
    if unresolved:
        needed.append(PROMPT_ON_CONFLICT)
    return tuple(needed)


def _resolve_answers(
    project_root: Path,
    *,
    agents: list[str] | None,
    access_mode: str | None,
    skill_families: list[str] | None,
    on_existing_agent_file: str,
    skills_gitignore: str | None,
    on_conflict: str,
    reconfigure: bool,
    recorded: dict,
) -> InitAnswers:
    """Settle every answer, in one order: argument, then config, then default.

    ``reconfigure=True`` drops the config layer for the four persisted answers,
    so a caller that means "ask me again" gets the built-in defaults rather than
    what the project recorded last time.

    The agents answer has a fourth layer, and it exists because its built-in
    default is the only one that *destroys* something. "Deselect every agent"
    uninstalls Lore's skills from every agent directory, which is a reasonable
    thing to do when somebody asked for it and never a reasonable thing to
    assume. Nobody had asked for it in the case that mattered most: no release
    before this one recorded an answer, so every upgrading project arrives with
    the question unanswered, and a run with no terminal to ask at read that
    silence as ``--agent none`` and emptied ``.claude/skills/``. So an empty
    selection has to be *stated* — as ``--agent none``, or as the answer the
    project recorded last time. Absent both, the default is what the project
    demonstrably is (``agents_in_evidence``), and only a project showing no
    evidence at all falls through to selecting nothing, where there is by
    definition nothing to uninstall.

    Every token is checked before anything is computed, so a typo costs nothing
    and reaches the caller with the wording the CLI would have used for it. A
    token that came from the config rather than the arguments is rejected with
    the key that holds it and the flag that replaces it, because that answer
    outlives the run that hit it.
    """
    config = DEFAULT_CONFIG if reconfigure else load_config(project_root)
    answered = frozenset() if reconfigure else recorded_keys(project_root)

    if agents is not None:
        agent_tokens = list(agents)
    elif AGENTS_CONFIG_KEY in answered:
        agent_tokens = list(config.init_agents)
    else:
        agent_tokens = list(agents_in_evidence(recorded))
    mode_token = access_mode if access_mode is not None else config.init_access_mode
    family_tokens = (
        list(skill_families)
        if skill_families is not None
        else list(config.init_skill_families)
    )
    gitignore_token = (
        skills_gitignore
        if skills_gitignore is not None
        else config.init_skills_gitignore
    )

    # `validate_agent_selection` composes `validate_agent_id` over the selection,
    # so an unknown id is reported before the `none`-exclusivity rule.
    _reject_recorded(
        validators.validate_agent_selection(agent_tokens, agent_registry.agent_ids()),
        field="agents",
        value=agent_tokens,
        recorded=agents is None and AGENTS_CONFIG_KEY in answered,
    )
    _reject_recorded(
        validators.validate_access_mode(mode_token),
        field="access_mode",
        value=mode_token,
        recorded=access_mode is None,
    )
    accepted_families = (*skills.family_ids(), skills.ALL_FAMILIES, skills.NO_FAMILIES)
    for token in family_tokens:
        _reject_recorded(
            validators.validate_skill_family(token, accepted_families),
            field="skill_families",
            value=family_tokens,
            recorded=skill_families is None,
        )
    _reject_recorded(
        _unknown_token(
            "skills gitignore policy", gitignore_token, SKILLS_GITIGNORE_TOKENS
        ),
        field="skills_gitignore",
        value=gitignore_token,
        recorded=skills_gitignore is None,
    )
    _reject(_unknown_token("conflict policy", on_conflict, reconcile.ON_CONFLICT_TOKENS))
    _reject(
        _unknown_token(
            "existing-file policy", on_existing_agent_file, ON_EXISTING_AGENT_FILE_TOKENS
        )
    )

    return InitAnswers(
        agents=tuple(target.id for target in _selected_targets(agent_tokens)),
        access_mode=AccessMode(mode_token),
        skill_families=skills.resolve_families(family_tokens),
        on_existing_agent_file=on_existing_agent_file,
        skills_gitignore=gitignore_token,
        on_conflict=on_conflict,
    )


def plan_init(
    project_root: Path | None = None,
    *,
    agents: list[str] | None = None,
    access_mode: str | None = None,
    skill_families: list[str] | None = None,
    on_existing_agent_file: str = "append",
    skills_gitignore: str | None = None,
    on_conflict: str = reconcile.ON_CONFLICT_SKIP,
    reconfigure: bool = False,
) -> InitPlan:
    """Compute what an initialisation would do, without performing any of it.

    Every keyword defaulting to ``None`` resolves in one order: explicit
    argument, then ``.lore/config.toml``, then the built-in default.
    ``reconfigure=True`` skips the config layer for the four persisted answers,
    which is what ``--reconfigure`` means.

    **This function is the only reader of the four ``init-*`` config keys**
    (ADR-021 constraint 2): a second reader is a duplicate implementation and an
    ADR-011 violation, which is why no CLI flag carries a config-derived
    default.

    ``project_root=None`` resolves to ``Path.cwd()`` — `lore init` is the
    documented exception to ``find_project_root()``, because it runs where no
    ``.lore/`` exists yet.

    Raises ``ValueError`` on any token the CLI's constrained-flag layer would
    reject, so the Python surface rejects exactly what the CLI does — and on
    the argument *shapes* click's own parsing makes unreachable, which is where
    a library caller's mistakes actually land.

    ``reconfigure=True`` needs all four recorded answers supplied. `--reconfigure`
    means "ask me again", and a call has no way to ask: without them it would
    re-resolve every one from the built-in defaults, silently, which is what the
    CLI refuses at the terminal for the same reason (ADR-011 — the rule is
    argument inspection, so it belongs here and not in `cli.py`).
    """
    agents = _token_sequence(agents, parameter="agents", noun="agent ids")
    skill_families = _token_sequence(
        skill_families, parameter="skill_families", noun="family ids"
    )
    if not isinstance(reconfigure, bool):
        raise ValueError(
            f"reconfigure takes True or False, not {type(reconfigure).__name__}."
        )
    if reconfigure:
        unsupplied = missing_recorded_answers(
            {
                "agents": agents,
                "access_mode": access_mode,
                "skill_families": skill_families,
                "skills_gitignore": skills_gitignore,
            }
        )
        if unsupplied:
            raise ValueError(
                "reconfigure=True asks the four recorded questions again, and this "
                f"call has no way to ask them. Pass {', '.join(unsupplied)}, or drop "
                "reconfigure=True to reuse what .lore/config.toml records."
            )

    # Resolved once, here, so the plan names the directory it describes rather
    # than a directory relative to wherever the caller happened to be standing.
    # A stored `.` re-joined at apply time wrote a whole project tree into a
    # different directory, silently, and `InitResult.project_root` could not
    # even say which (round 5, defect 5).
    root = Path(project_root).resolve() if project_root is not None else Path.cwd()
    # Read before the answers are settled, not after: what Lore installed last
    # time is what an unanswered agents question falls back on.
    recorded, shipped = _recorded_entries(root)
    answers = _resolve_answers(
        root,
        agents=agents,
        access_mode=access_mode,
        skill_families=skill_families,
        on_existing_agent_file=on_existing_agent_file,
        skills_gitignore=skills_gitignore,
        on_conflict=on_conflict,
        reconfigure=reconfigure,
        recorded=recorded,
    )
    targets = _selected_targets(answers.agents)
    _reject_escaping_roots(root, targets)

    desired = build_desired(project_root=root, targets=targets, answers=answers)
    files = reconcile.reconcile(
        desired,
        recorded,
        root,
        on_conflict=answers.on_conflict,
        retirement_reason=skills.retirement_for,
        section_markers=_marker_pair,
        installed_before=shipped,
    )
    unresolved = reconcile.unsettled(files)

    return InitPlan(
        project_root=root,
        answers=answers,
        targets=targets,
        files=files,
        prompts_needed=_prompts_needed(root, targets, unresolved),
        seeded=seeded_paths(),
        unstated_uninstall=_unstated_uninstall(
            answers, recorded, files, stated=agents is not None
        ),
    )


_MESSAGE_WIDTH = 78
"""Where a multi-sentence refusal wraps, so it reads the same everywhere.

The report's own rows are laid out to about this, and a paragraph handed to
`click` unwrapped arrives as one line however wide the terminal is.
"""


def _wrapped(message: str) -> str:
    """*message* as lines no wider than :data:`_MESSAGE_WIDTH`.

    A path is never broken across two lines, however long it is: half a path on
    each of two lines is a path nobody can copy, and every one of these messages
    names one.
    """
    return textwrap.fill(
        message,
        width=_MESSAGE_WIDTH,
        break_long_words=False,
        break_on_hyphens=False,
    )


def _reject_escaping_roots(project_root: Path, targets) -> None:
    """Refuse when a directory this run installs into is not inside the project.

    `.lore/` and every skills root, asked once, before anything is planned. The
    containment property says Lore never writes outside the project it was run
    in, and a directory that leaves it takes every file under it with it — so
    the honest answer is one refusal naming the directory, not a report line per
    file that could not be written.

    **The ruling on a deliberately linked skills tree.** A shared
    `.claude/skills` on another volume is a real workflow, and it is refused
    anyway. The tempting distinction — "the user chose where their skills live,
    which is not a link Lore was tricked into following" — cannot be drawn from
    here: a symlink is a file in a repository, so a clone carries one, and
    honouring it would let a checkout decide where a later `lore init` writes.
    The property has to hold for the tree Lore is standing in, whoever made it.

    What was wrong before this was the *shape* of the refusal, not the refusal.
    Fourteen identical ``! Kept`` rows on exit 0 left a project with no skills,
    no manifest rows and `lore health` reporting a pass, because the health scan
    walks manifest paths and there were none: `lore init && lore health` was
    green with nothing installed. A stop with the cause named is what a person —
    or a CI job — can act on.

    A link pointing **inside** the project is untouched by any of this. The rule
    is about the boundary, not about links.
    """
    for relative in (LORE_DIR_PATH, *skills.install_roots(targets)):
        target = manifest.resolve_path(project_root, relative)
        reason = safewrite.outside_root_reason(target, project_root)
        if reason is None:
            continue
        raise ValueError(
            f"{relative} {reason}\n"
            + _wrapped(
                f"Everything `lore init` writes stays inside {project_root}, so "
                "this run has nowhere to install to. A shared tree still works "
                "the other way round: keep the real directory here and link to "
                "it from the shared location."
            )
        )


def _unstated_uninstall(
    answers: InitAnswers, recorded, files, *, stated: bool
) -> str | None:
    """The refusal for an uninstall-everything plan nobody asked for, or ``None``.

    The backstop behind the empty-agent guard, and it is deliberately about the
    *plan* rather than about the route that produced it. The guard itself asks
    where the empty selection came from, and smoke testing found two ways to
    hand it a false answer — an unanswered question read as silence-means-none,
    and a ``config.toml`` value the loader could not use falling back to the
    empty default. Both ended in the same place: every skill removed, the
    instruction file deleted, exit 0. A third route is a question of time, so
    this one asks about the destination.

    Three conditions, all needed:

    * the run selects **no agent at all** — ``--agent none`` resolves to the
      registry's ``none`` row and is therefore *not* this, which is what lets
      the flag be the way through;
    * the project shows evidence of agents it is dropping, so there is a setup
      to uninstall rather than nothing to do;
    * the plan actually removes something, so the steady state a stated
      ``--agent none`` leaves behind still runs, and re-running is never
      refused for a decision already carried out.

    *stated* is "this call passed an agents argument", which is the only thing
    that means somebody decided on **this** run. A value in a file is not that:
    it is what the last run recorded, or what something wrote there by mistake.
    """
    if stated or answers.agents:
        return None
    dropped = agents_in_evidence(recorded)
    if not dropped:
        return None
    if not any(
        entry.action is FileAction.REMOVE and entry.reported for entry in files
    ):
        return None
    keeping = " ".join(dropped)
    return _wrapped(
        f"this run would remove every file Lore installed for {', '.join(dropped)} "
        "and select no agent in their place, and nothing on this run asked for "
        f"that — the empty selection came from init-agents in {CONFIG_PATH}. "
        "Deselecting every agent uninstalls Lore's skills from every agent "
        "directory, so the run that does it has to say so: re-run with "
        f"`--agent none` to go ahead, or `--agent {keeping}` to keep this "
        "project set up the way it is."
    )


# ---------------------------------------------------------------------------
# render_plan — the summary a person reads before anything is written
# ---------------------------------------------------------------------------


_SUMMARY_LABELS = {
    action: word.capitalize() for action, word in SUMMARY_ACTIONS.items()
}
"""What each action is called in the summary — the shared tally words, titled.

Derived rather than authored, because ``InitPlan.counts()`` reports the same
buckets and two tables were two ways to disagree: ``counts()`` used to tally raw
actions and report seventeen changes for a plan this summary printed as five
zeroes.
"""

_SUMMARY_ORDER = SUMMARY_ORDER
"""The counts line, in a fixed order with zeroes included, so two runs of the
same project produce comparable output. ``counts()`` drops its zeroes; this
keeps them, which is the only difference between the two."""

_LABEL_WIDTH = 8
_PATH_WIDTH = 46

# Renders in `init.py` rather than `cli.py` so a caller without a terminal —
# and a unit test without a CliRunner — reaches the same text. `cli.py` prints
# it and owns nothing else about it (standards-separation-of-concerns).


def _summary_line(entry: PlannedFile) -> str:
    """One planned path, its action word, and its reason when it has one."""
    label = _SUMMARY_LABELS[entry.action]
    if not entry.detail:
        return f"  {label:<{_LABEL_WIDTH}} {entry.path}"
    return f"  {label:<{_LABEL_WIDTH}} {entry.path:<{_PATH_WIDTH}} {entry.detail}"


def _summary_counts(plan: InitPlan) -> str:
    """The closing tally, one bucket per action word, zeroes included.

    ``plan.counts()`` is the computation; this only formats it. The Python
    surface and the terminal therefore cannot report a different number.

    The reconciled buckets only, in ``_SUMMARY_ORDER``. ``counts()`` carries one
    more — the seeded files — and they are reported below, in the block that
    lists them, with the total this line would otherwise dwarf.
    """
    tally = dict.fromkeys(_SUMMARY_ORDER, 0) | plan.counts()
    return "  " + " · ".join(f"{tally[name]} {name}" for name in _SUMMARY_ORDER)


def _answer_summary(values) -> str:
    """An answer list as the header prints it, or ``none`` when it is empty."""
    return ", ".join(values) if values else "none"


SEEDED_HEADING = "Also refreshed in place, not tracked for edits"
SEEDED_LABEL = "Seed"


def _seeded_block(seeded: tuple[str, ...]) -> list[str]:
    """The listing of the files reconciliation does not manage, or nothing.

    Its own block below the tally rather than rows in the listing: these paths
    take no conflict and are never left alone, so counting them beside the
    decisions the run actually made would say they were decisions too. The tally
    line stays the tally of the tracked half, which is what it has always been.
    """
    if not seeded:
        return []
    # Repo-relative, like every other row of the plan. The status lines an
    # applied run prints name a path inside `.lore/` relative to it; the plan
    # does not, which is what keeps `.lore/.gitignore` and the project's own
    # `.gitignore` two visibly different rows.
    return [
        "",
        f"  {SEEDED_HEADING} ({len(seeded)} files):",
        *(f"  {SEEDED_LABEL:<{_LABEL_WIDTH}} {path}" for path in seeded),
    ]


def render_plan(plan: InitPlan) -> str:
    """Render *plan* as the block `lore init` shows before it writes anything.

    A header naming the project and the three answers that shape the file set,
    one line per path that would change, a counts line, and then the files Lore
    refreshes in place. Rows that would change nothing — a file already
    byte-identical to what Lore would write — are absent from both the listing
    and the tally, so an unchanged project reports all zeroes rather than a wall
    of no-ops.
    """
    answers = plan.answers
    reported = [entry for entry in plan.files if entry.reported]
    header = (
        f"Plan for {plan.project_root} "
        f"(agents: {_answer_summary(answers.agents)} · "
        f"access: {answers.access_mode} · "
        f"families: {_answer_summary(answers.skill_families)})"
    )
    listing = [_summary_line(entry) for entry in reported]
    # One blank line between the parts, and no empty listing block: a project
    # already exactly as Lore would leave it prints a header and five zeroes.
    parts = [header, "", *listing]
    if listing:
        parts.append("")
    parts.append(_summary_counts(plan))
    parts.extend(_seeded_block(plan.seeded))
    if plan.unstated_uninstall is not None:
        # Under the listing it is about: `--dry-run` and the confirm prompt are
        # where somebody sees the removals, and the refusal belongs beside them
        # rather than only in the exception nobody printed the plan alongside.
        parts.extend(
            [
                "",
                "  ! Refused",
                *(
                    f"          {line}"
                    for line in plan.unstated_uninstall.splitlines()
                ),
            ]
        )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# apply_init — perform a computed plan
# ---------------------------------------------------------------------------


_STEP_ORDER = (
    "skill:",
    LORE_AGENT_SOURCE,
    "agent-instructions:",
    "skills-gitignore:",
)
"""Tech Spec §6.7's write order, as the source-token prefix that opens each step.

Skills first, then the canonical instruction text, then each agent's marked
block, then the installed-skill listing. The root gitignore block sat between
the last two and is no longer written by any release.
"""

_IN_PLACE_WRITES = frozenset(WRITING_ACTIONS) - {FileAction.REMOVE}
"""The actions apply performs as a write. Removals run later, after every write."""


def _step(entry: PlannedFile) -> int:
    """Which §6.7 step *entry* belongs to. Anything unrecognised writes last."""
    for position, prefix in enumerate(_STEP_ORDER):
        if entry.source.startswith(prefix):
            return position
    return len(_STEP_ORDER)


def _display(path: str) -> str:
    """The path as the report names it: relative to `.lore/` when inside it.

    Matches the existing status lines — `doctrines/default/...`, `config.toml` —
    while a path outside `.lore/` keeps its repo-relative form so a human can
    tell `CLAUDE.md` from `.lore/LORE-AGENT.md`.
    """
    prefix = ".lore/"
    return path[len(prefix) :] if path.startswith(prefix) else path


def _write_messages(entry: PlannedFile) -> list[str]:
    """The status lines for one performed write.

    Two of them when the row carries a detail, which is a write that destroys
    something the project put there: what went, and where a copy of their own
    would have survived. The removal path and ``_kept_messages`` have always
    printed the row's detail and this one built its line from the action alone
    — so the project that actually loses an edit was the one never told, unless
    it happened to be at a terminal where the plan is rendered before the
    confirm. Everything writing without one — `--yes`, a pipe, a CI job, Realm
    — saw `Updated` and nothing else.

    Indented under the line rather than appended to it, which is the shape
    ``! Kept`` already uses for the same job: the detail is a sentence, and the
    status lines stay one path each for anything reading them.
    """
    shown = _display(entry.path)
    if entry.kind == SECTION_KIND:
        lines = [f"  Updated {shown} (Lore section)"]
    else:
        verb = "Created" if entry.action is FileAction.CREATE else "Updated"
        lines = [f"  {verb} {shown}"]
    if entry.detail:
        lines.append(f"          {entry.detail}")
    return lines


def _kept_messages(entry: PlannedFile, detail: str | None = None) -> list[str]:
    """The two-line report for a file left alone, naming where its content now belongs.

    *detail* overrides the row's own when the reason is about this run rather
    than about the row — a path that moved between the plan and the write has a
    reason the reconciliation table never saw.
    """
    lines = [f"  ! Kept  {_display(entry.path)}"]
    reason = detail if detail is not None else entry.detail
    if reason:
        lines.append(f"          {reason}")
    return lines


STALE_ROW = "changed since the plan was computed — re-run lore init"
"""Said of a path whose disk state moved between planning and applying."""


def _reject_unplannable_rows(plan: InitPlan, desired: dict[str, DesiredFile]) -> None:
    """Refuse a plan carrying a row `plan_init` could not have produced.

    ``apply_init`` takes an ``InitPlan``, and a frozen dataclass is a shape
    rather than a promise — ``dataclasses.replace`` builds one with any rows a
    caller likes. Write containment used to be *emergent* here: a fabricated
    row was stopped by a ``KeyError`` out of the ``desired`` lookup, which is a
    traceback rather than a refusal and covers only rows that would be written.
    Both halves are checked by name instead, before any I/O:

    * a path that leaves the project, which is the shape ``manifest`` refuses at
      parse time and ``safewrite`` refuses at the write;
    * a writing row naming a path this release does not produce, which has no
      bytes to write and no business in a plan;
    * a **removal** naming a path this release neither installs to nor removes
      from, which is the same question asked of the destructive half. It had no
      test at all, so a fabricated row unlinked any file in the project — the
      permissive side was the one that deletes.
    """
    for entry in plan.files:
        escape = manifest.escape_reason(entry.path)
        if escape is not None:
            raise ValueError(
                f"{entry.path}: plan row {escape} — every planned path is "
                "repo-root-relative and inside the project"
            )
        if (
            entry.action in _IN_PLACE_WRITES
            and entry.reported
            and entry.path not in desired
        ):
            raise ValueError(
                f"{entry.path}: plan row would write a path this release does not "
                "produce; recompute the plan with plan_init()"
            )
        if entry.action is FileAction.REMOVE:
            unownable = manifest.unownable_reason(entry.path)
            if unownable is not None:
                raise ValueError(
                    f"{entry.path}: plan row would remove a path this release "
                    f"never installs to or removes from — it {unownable}; "
                    "recompute the plan with plan_init()"
                )


def _reject_unwritable_paths(plan: InitPlan) -> None:
    """Refuse before the first byte when a path the run needs is not free.

    Every path an initialisation writes is known from the plan: the seeded
    `.lore/` tree, and every row the reconciliation table decided to write. So
    every one of them is checked here, with the same ``safewrite`` question the
    writer itself asks — just early enough for the answer to still mean
    "nothing happened".

    A directory sitting on a path the run writes used to stop it *after*
    `.lore/`, the instruction file and thirteen skills had landed, with no
    manifest written: nineteen files nothing had a record of, under a project
    whose tracking answer promised to hide them. Partial application with no
    record is the worst state a run can end in, and it is the one this removes.
    The path that found it was the root `.gitignore`, which this release no
    longer writes at all; `CLAUDE.md` and every skills root still reach here.

    Not a guarantee that the run will finish — a full disk, a revoked
    permission, a filesystem that goes away mid-write are all still possible,
    which is what ``apply_init`` writes a manifest for on the way out.
    """
    root = plan.project_root
    paths_to_check = list(plan.seeded)
    paths_to_check += [
        entry.path
        for entry in plan.files
        if entry.action in _IN_PLACE_WRITES and entry.reported
    ]
    for relative in paths_to_check:
        _reject_occupied_path(manifest.resolve_path(root, relative), root)


_SKILLS_GITIGNORE_REACH = {"none": 0, SKILLS_GITIGNORE_LORE_ONLY: 1, "all": 2}
"""How much each answer ignores. A run that moves *up* this ordering has to
say so: git keeps a committed file tracked whatever a later rule says."""


def _tracking_change_note(
    previous: manifest.Manifest | None, answers: InitAnswers, roots: tuple[str, ...]
) -> list[str]:
    """Warn when the new answer ignores something the old one tracked.

    An ignore rule decides what `git add` picks up. It has no say at all about
    a path already in the index, so switching from ``none`` after a commit left
    a project whose owner believed thirteen files were ignored and whose every
    future upgrade showed them as modified — with nothing in the output hinting
    at the one command that fixes it.

    Lore does not run git and does not read the index, so this does not claim
    the files *are* committed; it names the recipe for the case where they are.
    The two commands are answer-agnostic on purpose: clearing the roots and
    re-adding them lands on whatever the new listing says, whichever answer
    wrote it.
    """
    if previous is None or not roots:
        return []
    before = previous.answers.get("skills_gitignore")
    after = answers.skills_gitignore
    if not isinstance(before, str) or before == after:
        return []
    if _SKILLS_GITIGNORE_REACH.get(after, 0) <= _SKILLS_GITIGNORE_REACH.get(before, 0):
        return []
    listed = " ".join(roots)
    return [
        f"  ! Note  skills tracking: {before} -> {after}",
        "          git keeps a committed file tracked whatever a later ignore",
        "          rule says. If you have committed these, re-apply the answer",
        "          to the index with:",
        f"            git rm -r --cached --ignore-unmatch {listed}",
        f"            git add {listed}",
    ]


def _stale_rows(plan: InitPlan) -> dict[str, str]:
    """Every path whose disk state no longer matches what the plan saw.

    The third column of the reconciliation comparison, asked a second time. Each
    row's action was decided from what was at its path when the plan was
    computed, so a path that has moved since is a path this plan has no decision
    for — and writing it anyway destroys exactly the edit the conflict machinery
    exists to report. On the CLI the window is the length of the confirm prompt
    somebody is reading; on the API path it is however long the caller holds the
    plan.

    Computed before anything is written, so the answer is about the tree as the
    run found it and not about a tree the run has begun changing.
    """
    stale: dict[str, str] = {}
    for entry in plan.files:
        if entry.action not in WRITING_ACTIONS:
            continue
        state = reconcile.disk_state(
            plan.project_root, entry.path, entry.kind, _marker_pair
        )
        if state.refusal is not None:
            stale[entry.path] = state.refusal
        elif state.digest != entry.observed:
            stale[entry.path] = STALE_ROW
    return stale


def _perform_write(project_root: Path, entry: PlannedFile, content: bytes) -> None:
    """Write one planned row, by kind.

    This is where a repo-relative path from the reconciliation table becomes an
    absolute one, so it is where the project boundary is enforced — a row that
    resolves outside it never reaches a writer, whatever produced the path.
    """
    target = manifest.resolve_path(project_root, entry.path)
    _reject_occupied_path(target, project_root)
    if entry.kind == SECTION_KIND:
        write_marked_section(
            target,
            content.decode("utf-8"),
            markers=_marker_pair(entry.path),
            project_root=project_root,
        )
        return
    safewrite.atomic_write_bytes(target, content, project_root=project_root)


def _known_skills_roots() -> tuple[str, ...]:
    """Every directory a skill can ever install into, longest first.

    Pruning stops at whichever of these contains a removed path, so an empty
    chain is cleaned up without the root itself ever being removed.
    """
    roots = {skills.LORE_SKILLS_ROOT}
    roots.update(row.skills_dir for row in agent_registry.load_registry() if row.skills_dir)
    return tuple(sorted(roots, key=len, reverse=True))


def _prune_stop(project_root: Path, relative: str) -> Path:
    """The directory pruning must not pass when *relative* is removed.

    A removed path that sits under no skills root gets its own parent, which
    makes it unprunable — nothing outside a skills tree is ever tidied away.
    """
    for candidate in _known_skills_roots():
        if relative.startswith(f"{candidate}/"):
            return manifest.resolve_path(project_root, candidate)
    return manifest.resolve_path(project_root, relative).parent


def _remove_if_nothing_remains(target: Path) -> bool:
    """Delete *target* when Lore's block was all it held; say whether it went.

    "Never delete the user's file" is the rule, and a file that consisted
    solely of Lore's own block was never the user's: `lore init --agent claude`
    creates `CLAUDE.md` holding the block alone, and deselecting Claude Code
    would otherwise leave a zero-byte `CLAUDE.md` behind for good. A file
    carrying anything of its own outside the markers keeps every byte of it,
    and a link is never the file Lore created however empty its target reads.
    """
    if target.is_symlink() or not target.is_file():
        return False
    if manifest.read_text(target).strip():
        return False
    target.unlink()
    return True


def _apply_removals(
    project_root: Path, entries: list[PlannedFile]
) -> tuple[list[PlannedFile], list[PlannedFile], list[str]]:
    """Perform every removal; return (removed, kept, messages).

    A `section` removal deletes the marked block and leaves the file otherwise
    byte-identical — retiring an agent must never delete the user's `CLAUDE.md`
    — unless the block was the whole file, which is the file Lore itself
    created. An unlink that fails is reported and the run continues; the path
    stays in the next manifest, so the next run sees it and tries again.

    A removal is held to the same rule as a write: a path that is now a link,
    or that resolves outside the project, is reported and left alone. The
    reconciliation table already classifies those as ``CONFLICT``, so reaching
    one here means the tree changed under the run — which is precisely when a
    hard unlink must not be taken on trust.
    """
    removed: list[PlannedFile] = []
    kept: list[PlannedFile] = []
    messages: list[str] = []
    pruning: dict[Path, list[Path]] = {}

    for entry in entries:
        target = manifest.resolve_path(project_root, entry.path)
        shown = _display(entry.path)

        refusal = safewrite.link_or_escape_reason(target, project_root=project_root)
        if refusal is not None:
            kept.append(entry)
            messages.append(f"  ! Kept  {shown} — {refusal}")
            continue

        if entry.kind == SECTION_KIND:
            remove_marked_section(
                target, markers=_marker_pair(entry.path), project_root=project_root
            )
            removed.append(entry)
            if _remove_if_nothing_remains(target):
                messages.append(f"  Removed {shown} — held nothing but Lore's block")
            else:
                messages.append(f"  Updated {shown} (Lore section removed)")
            continue

        try:
            target.unlink()
        except OSError as exc:
            kept.append(entry)
            messages.append(f"  ! Kept  {shown} — could not remove: {exc}")
            continue

        removed.append(entry)
        reason = f" — {entry.detail}" if entry.detail else ""
        messages.append(f"  Removed {shown}{reason}")
        pruning.setdefault(_prune_stop(project_root, entry.path), []).append(target)

    for stop_at, paths_removed in pruning.items():
        # Tidying is the last thing an initialisation does and the least
        # important one. `prune_empty_dirs` skips the directories it cannot
        # remove; this is the other half of the same promise — whatever one
        # tree does, the others still get pruned.
        try:
            reconcile.prune_empty_dirs(paths_removed, stop_at)
        except OSError:
            continue

    return removed, kept, messages


def _manifest_rows(
    project_root: Path,
    applied: list[PlannedFile],
    failed_removals: list[PlannedFile],
    skipped: list[PlannedFile] | None = None,
    previous: manifest.Manifest | None = None,
) -> list[PlannedFile]:
    """The rows the next run compares against.

    What Lore actually wrote, plus any removal that failed, plus any row this
    run reported as a **conflict** that the *previous* manifest already
    recorded, carried across unchanged.

    That last part is the FR-28 property read the right way round. What FR-28
    forbids is *claiming* a file: recording a path Lore never installed, which
    a future release could then remove. It does not ask Lore to forget a path
    it did install. Dropping conflicted rows meant run 2 reported `.gitignore`
    as "edited since install", dropped it, and run 3 called the same file "not
    installed by Lore" — false, and about a file still carrying the markers
    Lore wrote into it. Only a path the previous manifest names is carried, and
    it keeps the hash Lore wrote rather than the bytes the user now has there,
    because that hash is exactly what the record has always meant.

    A removal declined because the path is now a link is not "a removal that
    failed": there is nothing of Lore's there to record, and hashing it would
    hash whatever the link points at and re-enter that path as Lore-owned.
    """
    rows = [entry for entry in applied if entry.digest is not None]
    if skipped and previous is not None:
        recorded = previous.by_path
        taken = {entry.path for entry in rows}
        for entry in skipped:
            if entry.action is not FileAction.CONFLICT or entry.path in taken:
                continue
            known = recorded.get(entry.path)
            if known is None:
                continue
            rows.append(
                PlannedFile(
                    path=known.path,
                    action=entry.action,
                    kind=known.kind,
                    source=known.source,
                    digest=known.hash,
                    detail=entry.detail,
                )
            )
            taken.add(entry.path)
    for entry in failed_removals:
        target = manifest.resolve_path(project_root, entry.path)
        if safewrite.link_or_escape_reason(target, project_root=project_root):
            continue
        if not target.is_file():
            continue
        rows.append(
            PlannedFile(
                path=entry.path,
                action=entry.action,
                kind=entry.kind,
                source=entry.source,
                digest=manifest.file_digest(target),
                detail=entry.detail,
            )
        )
    return rows


_PERSISTED_KEYS = (
    ("init-agents", "agents"),
    ("init-access-mode", "access_mode"),
    ("init-skill-families", "skill_families"),
    ("init-skills-gitignore", "skills_gitignore"),
)


def _persist_answers(project_root: Path, answers: InitAnswers) -> None:
    """Record the four persisted answers in `.lore/config.toml`.

    A key already present is rewritten in place; anything else in the file —
    values, ordering, blank lines, inline comments — is left byte-identical, so
    a project's own settings survive every run.
    """
    target = paths.config_path(project_root)
    _reject_occupied_path(target, project_root)
    lines = (
        manifest.read_text(target).splitlines(keepends=True) if target.is_file() else []
    )

    for key, field in _PERSISTED_KEYS:
        rendered = f"{key} = {render_toml_value(getattr(answers, field))}\n"
        for index, line in enumerate(lines):
            head = line.split("=", 1)[0].strip()
            if head == key:
                lines[index] = rendered
                break
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(rendered)

    safewrite.atomic_write_text(target, "".join(lines), project_root=project_root)


def apply_init(plan: InitPlan) -> InitResult:
    """Perform a previously computed initialisation.

    Writes in Tech Spec §6.7's order and puts the manifest **last**. An
    interrupted run therefore leaves the previous manifest on disk, and the next
    `lore init` reconciles against what is actually there: a file the
    interrupted run had written already holds this release's bytes and is left
    alone, one it had not reached still matches the old record and is written,
    and one the project edited in between is the conflict it always was. No
    branch of that silently overwrites an edit, which is what makes an
    interrupted run recoverable.

    The bytes are recomputed from the plan's own answers rather than carried on
    it — enumeration is deterministic, and an ``InitPlan`` a caller inspects
    stays a description rather than a payload.

    Two things are checked before the first byte is written: that every row is
    one `plan_init` could have produced, and that the tree still looks the way
    the plan found it. A row whose path has moved since is reported and left
    alone — a plan is a decision about a tree, so it is only an answer for the
    tree it was computed against.
    """
    if not isinstance(plan, InitPlan):
        raise TypeError(
            f"apply_init() takes an InitPlan, not {type(plan).__name__} — "
            "build one with plan_init()."
        )
    if plan.unstated_uninstall is not None:
        # The one plan that is refused for what it *does* rather than for how
        # it was built. Raised here rather than out of `plan_init` so a caller
        # can still look at the removals it covers before being told no.
        raise ValueError(plan.unstated_uninstall)
    root = plan.project_root
    answers = plan.answers

    desired = build_desired(project_root=root, targets=plan.targets, answers=answers)
    _reject_unplannable_rows(plan, desired)
    _reject_unwritable_paths(plan)
    stale = _stale_rows(plan)

    previous = manifest.load(root)
    manifest_existed = paths.install_manifest_path(root).is_file()
    roots = skills.install_roots(plan.targets)

    applied: list[PlannedFile] = []
    skipped: list[PlannedFile] = []
    removals: list[PlannedFile] = []
    failed: list[PlannedFile] = []

    def record() -> Path:
        """Write the manifest for whatever this run has done so far."""
        return manifest.write(
            root,
            answers={
                "agents": list(answers.agents),
                "access_mode": str(answers.access_mode),
                "skill_families": list(answers.skill_families),
                "skills_gitignore": answers.skills_gitignore,
            },
            targets={
                target.id: target.skills_dir or skills.LORE_SKILLS_ROOT
                for target in plan.targets
            },
            files=_manifest_rows(root, applied, failed, skipped, previous),
            lore_version=_lore_version(),
            catalogue_version=skills.load_catalogue()["version"],
        )

    try:
        messages = _seed_lore_directory(root)

        for entry in sorted(plan.files, key=lambda row: (_step(row), row.path)):
            if entry.path in stale:
                skipped.append(entry)
                messages.extend(_kept_messages(entry, detail=stale[entry.path]))
            elif entry.action is FileAction.REMOVE:
                removals.append(entry)
            elif entry.action in _IN_PLACE_WRITES:
                if entry.reported:
                    _perform_write(root, entry, desired[entry.path].content)
                    messages.extend(_write_messages(entry))
                applied.append(entry)
            else:
                # A CONFLICT reports what is in the way and touches nothing:
                # refused means untouched.
                skipped.append(entry)
                messages.extend(_kept_messages(entry))

        removed, failed, removal_messages = _apply_removals(root, removals)
        applied.extend(removed)
        skipped.extend(failed)
        messages.extend(removal_messages)

        _persist_answers(root, answers)
    except Exception:
        # Whatever stopped the run, the files it did write are on disk and the
        # next `lore init` has to know about them: an unrecorded install is one
        # nothing can reconcile, upgrade or remove. Best effort — if the
        # manifest cannot be written either, the original failure is the one
        # worth reporting.
        try:
            record()
        except Exception:  # pragma: no cover - the second failure of two
            pass
        raise

    manifest_path = record()
    verb = "Updated" if manifest_existed else "Created"
    messages.append(f"  {verb} {_display(MANIFEST_PATH)}")
    messages.extend(_tracking_change_note(previous, answers, roots))

    return InitResult(
        project_root=root,
        messages=tuple(messages),
        applied=tuple(applied),
        skipped=tuple(skipped),
        manifest_path=manifest_path,
    )


def _lore_version() -> str:
    """The installed package version, recorded in the manifest for diagnosis."""
    from lore import __version__

    return __version__


# ---------------------------------------------------------------------------
# Step 1 — the `.lore/` scaffolding, unchanged from before the plan/apply split
# ---------------------------------------------------------------------------


def _seed_lore_directory(project_root: Path) -> list[str]:
    """Create and refresh everything under `.lore/` that reconciliation does not manage.

    The database, the seeded ``default/`` trees, the copied docs and the
    user-tracked skeletons. These are overwritten in place on every run — they
    are Lore's own files inside Lore's own directory, and the manifest has no
    job to do for them.
    """
    lore_dir = paths.lore_dir(project_root)
    messages: list[str] = []

    safewrite.refuse_unsafe_directory(lore_dir, project_root=project_root)
    if lore_dir.is_dir():
        messages.append("  .lore/ directory already exists")
    else:
        lore_dir.mkdir(parents=True)
        messages.append("  Created .lore/ directory")

    messages.append(
        _write_lore_gitignore(lore_dir / ".gitignore", project_root=project_root)
    )
    db_path = paths.db_path(project_root)
    # SQLite opens the path it is handed and follows whatever link is on it, so
    # the one write `lore init` does not perform itself is checked before it.
    _reject_occupied_path(db_path, project_root)
    messages.extend(_format_db_status(init_database(db_path)))

    # Each tree is described once in ``SEEDED_TREES`` — the copy here, the prune
    # that follows it and the plan's listing all read the same row. The order is
    # the one the status lines have always arrived in, with the user-tracked
    # skeletons between `docs` and `watchers`.
    #
    # GETTING-STARTED.md is copied verbatim; LORE-AGENT.md is rendered from the
    # same tree and arrives with the plan, so `docs` excludes it.
    by_package = {spec.package: spec for spec in SEEDED_TREES}
    for package in ("doctrines", "knights", "artifacts", "docs"):
        messages.extend(_seed_tree(project_root, by_package[package]))

    messages.extend(_seed_user_tracked(project_root))
    messages.extend(_seed_tree(project_root, by_package["watchers"]))

    for subfolder in ("main", "shared"):
        (paths.rites_dir(project_root) / subfolder).mkdir(parents=True, exist_ok=True)

    return messages


def run_init() -> list[str]:
    """Run the full lore init sequence in the current working directory.

    Zero arguments, ``list[str]`` back — the pinned public contract. Every
    answer takes its recorded value or its built-in default, which on a project
    holding nothing of Lore's is the pre-feature behaviour: no agent, skills
    under `.lore/skills/`, every family. A project that already has Lore's
    skills in an agent's directory keeps them there instead of having them
    swept — an empty agent selection is an answer somebody gives, never one
    this function assumes.
    """
    return list(apply_init(plan_init()).messages)


def _write_lore_gitignore(target: Path, *, project_root: Path | None = None) -> str:
    """Write `.lore/.gitignore` from the seed template; return status message."""
    content = resources.files("lore.defaults").joinpath("gitignore").read_text()
    verb = "Updated" if target.is_file() else "Created"
    safewrite.atomic_write_text(target, content, project_root=project_root)
    return f"  {verb} .gitignore"


def _format_db_status(status: str) -> list[str]:
    """Render an `init_database` status code as a status-message list.

    Returns an empty list for unknown statuses (matching the original
    silent-fallthrough behaviour).
    """
    match status:
        case "created":
            return [f"  Created lore.db (schema version {SCHEMA_VERSION})"]
        case "existing":
            return ["  Skipped lore.db (already exists)"]
        case "reinitialized":
            return [
                "  Warning: Existing database appears corrupted. Reinitialized lore.db"
            ]
    return []
