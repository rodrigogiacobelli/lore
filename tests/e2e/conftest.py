"""E2E test fixtures.

Scenario-level fixtures for pre-populating quests and missions.
Base fixtures (runner, project_dir, db_conn, insert_*, assert_exit_*)
are in the root tests/conftest.py.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner

from lore.cli import main

# ---------------------------------------------------------------------------
# The codex-index E2E fixture
#
# Spec: codex-index-spec — Part 4 "The E2E fixture". One definition, shared by
# tests/e2e/test_index.py, test_health_index.py and test_api_parity_index.py,
# so the three files cannot drift apart on the corpus every expected output in
# the feature is a function of.
# ---------------------------------------------------------------------------


# Each document's `related` list. The partition of this graph is exactly four
# clusters: three of five, hubs `alpha-hub`, `beta-hub` and `gamma-hub`, plus
# the one-member `solo` cluster, which is kept because it has no edge to be
# absorbed along (R12).
INDEX_FIXTURE_RELATED: dict[str, list[str]] = {
    "alpha-hub": ["alpha-a", "alpha-b", "alpha-c", "alpha-d"],
    "alpha-a": ["alpha-b"],
    "alpha-b": [],
    "alpha-c": ["alpha-d"],
    "alpha-d": ["beta-d"],
    "beta-hub": ["beta-a", "beta-b", "beta-c", "beta-d"],
    "beta-a": ["beta-b"],
    "beta-b": [],
    "beta-c": ["beta-d"],
    "beta-d": ["gamma-d"],
    "gamma-hub": ["gamma-a", "gamma-b", "gamma-c", "gamma-d"],
    "gamma-a": ["gamma-b"],
    "gamma-b": [],
    "gamma-c": ["gamma-d"],
    "gamma-d": [],
    "solo": [],
}


# The digest `beta-hub`'s entry is authored against. Well-formed under the
# schema and matching no cluster, so the entry is reliably `drifted` without a
# test ever hard-coding a real digest. Written quoted, because YAML reads a
# bare run of sixty-four zeros as the integer 0.
DRIFTED_DIGEST = '"' + "0" * 64 + '"'


def write_codex_document(
    project_dir: Path, doc_id: str, related: list[str] | None = None
) -> Path:
    """Write `.lore/codex/<doc_id>.md` in the fixture's own shape.

    `title` is the id title-cased with hyphens as spaces, `summary` is
    "The <id> document." and the body is "Body of <id>." — every field a value
    this spec owns, so no expected output anywhere depends on a seeded default
    (`decisions-006-no-seed-content-tests`).
    """
    related = related if related is not None else []
    related_block = ""
    if related:
        related_block = "related:\n" + "".join(f"  - {r}\n" for r in related)
    text = (
        "---\n"
        f"id: {doc_id}\n"
        f"title: {doc_id.replace('-', ' ').title()}\n"
        f"summary: The {doc_id} document.\n"
        f"{related_block}"
        "---\n\n"
        f"Body of {doc_id}.\n"
    )
    codex_dir = project_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    path = codex_dir / f"{doc_id}.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_index_fixture(project_dir: Path) -> None:
    """Add the sixteen fixture documents and remove the one `lore init` seeds.

    The seeded `.lore/codex/codex.md` goes because every expected output in
    this feature is asserted character for character, and a table row derived
    from it would pin that file's `id` value and the absence of its `related`
    list — field values of a seeded default. The practice is established:
    the nested-projects fixture already unlinks the same file after each
    `lore init` (tests/conftest.py).
    """
    for doc_id, related in INDEX_FIXTURE_RELATED.items():
        write_codex_document(project_dir, doc_id, related)
    (project_dir / ".lore" / "codex" / "codex.md").unlink(missing_ok=True)


def render_digest(project_dir: Path, hub: str) -> str:
    """The digest the render records for the cluster headed by *hub*.

    A test never hard-codes a digest: the `alpha-hub` entry is authored against
    whatever `lore index build` just wrote, so the entry reads `ok` whatever the
    fixture's bytes are.
    """
    payload = json.loads(
        (project_dir / ".lore" / "index" / "codex.json").read_text(encoding="utf-8")
    )
    return next(c["digest"] for c in payload["clusters"] if c["hub"] == hub)


def write_authored_yaml(project_dir: Path, body: str) -> Path:
    """Write `.lore/index/authored.yaml` with *body* as its `entries:` block."""
    path = project_dir / ".lore" / "index" / "authored.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"version: 1\nentries:\n{body}", encoding="utf-8")
    return path


def write_w1_authored(project_dir: Path) -> Path:
    """Write the W1 authored file: `alpha-hub` ok, `beta-hub` drifted.

    Requires a render on disk, so the caller runs `lore index build` first.
    """
    return write_authored_yaml(
        project_dir,
        f"""\
  alpha-hub:
    slug: alpha-theme
    name: Alpha Theme
    summary: Everything alpha, and the documents that explain it.
    authored_against: {render_digest(project_dir, "alpha-hub")}
  beta-hub:
    slug: beta-theme
    name: Beta Theme
    summary: Everything beta.
    authored_against: {DRIFTED_DIGEST}
""",
    )


# `tests/e2e/conftest.py` is not importable by name under pytest's import mode,
# so the one shared definition Part 4 asks for reaches the three test files as
# fixtures rather than as imports.


@pytest.fixture()
def index_project(project_dir: Path) -> Path:
    """A `lore init` project holding the sixteen codex-index fixture documents."""
    write_index_fixture(project_dir)
    return project_dir


@pytest.fixture()
def w1_project(index_project: Path, runner: CliRunner) -> Path:
    """`index_project` built once, then authored the W1 way.

    `alpha-hub` reads `ok`, `beta-hub` `drifted`, and `gamma-hub` and `solo`
    `unauthored` — the one state W1, the first W3 block and W8 all describe,
    and the state most scenarios in this feature start from.
    """
    assert runner.invoke(main, ["index", "build"]).exit_code == 0
    write_w1_authored(index_project)
    return index_project


@pytest.fixture()
def write_document() -> Callable[..., Path]:
    """Write one codex document in the fixture's shape."""
    return write_codex_document


@pytest.fixture()
def write_authored() -> Callable[[Path, str], Path]:
    """Write `.lore/index/authored.yaml` from an `entries:` block."""
    return write_authored_yaml


# ---------------------------------------------------------------------------
# A route-sensitive world for the tests about what a changed answer rewrites
#
# The shipped blocks are interim placeholders until the content lane lands, and
# no test may depend on their prose (decisions-006-no-seed-content-tests). A test
# that asks "does flipping the Memory route rewrite every installed skill?" needs
# a text that depends on the route, so this fixture supplies one: two
# test-authored blocks, one per route, added to every skill and to
# the instruction document, each gated exactly like the first body block of the
# file it joins plus the route. They can only survive where that block does, so
# no profile installs a skill it did not install before. The legacy-hash table is
# extended with every rendering of the new world, as the release script would.
# ---------------------------------------------------------------------------


@pytest.fixture()
def route_sensitive_text():
    """Make every installed skill and the instruction text differ by route."""
    from lore import blocklint, reconcile
    from lore import blocks as blocks_module
    from lore import skills as skills_module
    from lore.manifest import bytes_digest

    real_files = blocks_module._read_block_files
    real_catalogue = skills_module._read_catalogue_payload
    real_legacy = reconcile._read_legacy_payload
    routes = ("harness", "cli")

    def variant_text(block_id: str, base: blocks_module.Block, route: str) -> str:
        tags = [f"id: {block_id}", f"feature: {base.feature}", f"route: {route}"]
        if base.capabilities:
            tags.append(f"capabilities: [{', '.join(base.capabilities)}]")
        if base.requires:
            tags.append(f"requires: [{', '.join(base.requires)}]")
        if base.unless:
            tags.append(f"unless: [{', '.join(base.unless)}]")
        return (
            "---\n" + "\n".join(tags) + "\n---\n"
            f"Test-authored text for the {route} route.\n"
        )

    def plan_of_variants() -> list[tuple[str, str, str]]:
        """``(new block id, base block id, route)`` for every file that gains a pair."""
        payload = real_catalogue()
        wanted = [
            (f"zz-{entry['id']}", entry["files"][0]["blocks"][0]) for entry in payload["skills"]
        ]
        wanted.append(("zz-lore-agent", payload["documents"]["lore-agent"]["blocks"][0]))
        return [(f"{new}-{route}", base, route) for new, base in wanted for route in routes]

    def files():
        found = dict(real_files())
        parsed = {
            path: blocks_module.parse_block(text, source=path) for path, text in found.items()
        }
        by_id = {block.id: block for block in parsed.values()}
        for block_id, base_id, route in plan_of_variants():
            base = by_id[base_id]
            found[f"{base.feature}/{block_id}.md"] = variant_text(block_id, base, route)
        return found

    def catalogue():
        payload = real_catalogue()
        for entry in payload["skills"]:
            entry["files"][0]["blocks"] += [f"zz-{entry['id']}-{route}" for route in routes]
        payload["documents"]["lore-agent"]["blocks"] += [f"zz-lore-agent-{route}" for route in routes]
        return payload

    def legacy():
        payload = real_legacy()
        table = payload["files"]
        for entry in skills_module.load_catalogue()["skills"]:
            for row in entry["files"]:
                key = f".lore/skills/{entry['id']}/{row['path']}"
                digests = {
                    bytes_digest(text.encode("utf-8"))
                    for text in blocklint.distinct_renders(entry["id"], row["path"])
                }
                table[key] = sorted({*table.get(key, []), *digests})
        return payload

    def clear_caches():
        blocks_module.load_blocks.cache_clear()
        skills_module.load_catalogue.cache_clear()
        skills_module.family_ids.cache_clear()
        reconcile.load_legacy_hashes.cache_clear()

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(blocks_module, "_read_block_files", files)
        patch.setattr(skills_module, "_read_catalogue_payload", catalogue)
        clear_caches()
        patch.setattr(reconcile, "_read_legacy_payload", legacy)
        yield
    clear_caches()
