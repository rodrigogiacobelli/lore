import dataclasses
from pathlib import Path

import pytest


@pytest.fixture()
def bare_lore_dir(tmp_path):
    """Minimal .lore/ directory without running lore init.

    Use this for testing file-system modules (frontmatter, codex, doctrine,
    artifact) in isolation from the full init sequence.
    """
    lore = tmp_path / ".lore"
    for d in ["doctrines", "codex", "artifacts"]:
        (lore / d).mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# Nested-projects fixtures
#
# Spec: nested-projects-spec (lore codex show nested-projects-spec) — Part 4
# "Conventions". These build a real tree on disk; nothing here mocks a walk,
# ``tomllib`` or ``fnmatch``.
# ---------------------------------------------------------------------------


_ENTITY_DIRS = (
    "codex",
    "codex/transient",
    "codex/sources",
    "doctrines",
    "artifacts",
    "watchers",
    "rites/main",
    "rites/shared",
)


@dataclasses.dataclass(frozen=True)
class NestedTree:
    """Three nested Lore projects: ``camelot`` > ``lore`` > ``realm``.

    Each is a real project directory holding a real ``.lore/`` tree. No
    ``lore init`` runs: these tests exercise the entity modules, not the
    installer, and a seeded ``default/`` subtree would put content into
    assertions that ``adr-no-default-content-tests`` rules out.
    """

    camelot: Path
    lore: Path
    realm: Path

    def configure(self, project: Path, text: str) -> None:
        """Write ``project``'s ``.lore/config.toml``."""
        (project / ".lore" / "config.toml").write_text(text, encoding="utf-8")

    def write(self, project: Path, relative: str, text: str) -> Path:
        """Write ``text`` to ``project/.lore/<relative>``, creating parents."""
        target = project / ".lore" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def doc(
        self,
        project: Path,
        doc_id: str,
        *,
        group: str = "",
        title: str | None = None,
        summary: str = "A document.",
        related: tuple[str, ...] = (),
        binds: tuple[str, ...] = (),
        body: str = "Body text.",
    ) -> Path:
        """Write one codex document and return its path."""
        lines = [
            "---",
            f"id: {doc_id}",
            f"title: {title if title is not None else doc_id}",
            f"summary: {summary}",
        ]
        for field, values in (("related", related), ("binds", binds)):
            if values:
                lines.append(f"{field}:")
                lines.extend(f"  - {value}" for value in values)
        lines.extend(["---", "", body, ""])
        prefix = f"codex/{group}/" if group else "codex/"
        return self.write(project, f"{prefix}{doc_id}.md", "\n".join(lines))

    def entity(
        self,
        project: Path,
        kind: str,
        entity_id: str,
        *,
        group: str = "",
        summary: str = "An entity.",
    ) -> Path:
        """Write one frontmatter-backed entity."""
        directory = {"artifact": "artifacts"}[kind]
        prefix = f"{directory}/{group}/" if group else f"{directory}/"
        return self.write(
            project,
            f"{prefix}{entity_id}.md",
            f"---\nid: {entity_id}\ntitle: {entity_id}\nsummary: {summary}\n---\n\nBody.\n",
        )

    def doctrine(
        self,
        project: Path,
        doctrine_id: str,
        *,
        group: str = "",
        missions: tuple[str, ...] = ("only",),
    ) -> None:
        """Write one doctrine directory — its design document plus its missions."""
        prefix = f"doctrines/{group}/" if group else "doctrines/"
        directory = f"{prefix}{doctrine_id}"
        self.write(
            project,
            f"{directory}/{doctrine_id}.design.md",
            f"---\nid: {doctrine_id}\ntitle: {doctrine_id}\nsummary: A doctrine.\n---\n\nDesign.\n",
        )
        for mission_id in missions:
            self.write(
                project,
                f"{directory}/missions/{mission_id}.md",
                f"---\nid: {mission_id}\ntitle: {mission_id}\nsummary: A mission.\n"
                f"---\n\nDo {mission_id}.\n",
            )

    def watcher(self, project: Path, watcher_id: str, *, group: str = "") -> None:
        """Write one watcher YAML."""
        prefix = f"watchers/{group}/" if group else "watchers/"
        self.write(
            project,
            f"{prefix}{watcher_id}.yaml",
            f"id: {watcher_id}\ntitle: {watcher_id}\nsummary: A watcher.\n",
        )

    def rite(
        self, project: Path, rite_id: str, *, group: str = "", shared: bool = False
    ) -> None:
        """Write one rite YAML under ``main/`` or ``shared/``."""
        kind = "shared" if shared else "main"
        prefix = f"rites/{kind}/{group}/" if group else f"rites/{kind}/"
        if shared:
            text = (
                f"id: {rite_id}\ntitle: {rite_id}\nsummary: A shared step.\n"
                "do: Do the shared thing.\n"
            )
        else:
            text = (
                f"id: {rite_id}\ntitle: {rite_id}\nsummary: A rite.\n"
                "trigger: Something happens.\n"
                "nodes:\n  - id: only\n    do: Do it.\n    then: done\n"
                "conclusions:\n  done:\n    audience: team\n    response: Finished.\n"
            )
        self.write(project, f"{prefix}{rite_id}.yaml", text)

    def glossary(self, project: Path, items: tuple[tuple[str, str], ...]) -> None:
        """Write ``project``'s glossary from ``(keyword, definition)`` pairs."""
        lines = ["items:"]
        for keyword, definition in items:
            lines.append(f"  - keyword: {keyword}")
            lines.append(f"    definition: {definition}")
        self.write(project, "codex/glossary.yaml", "\n".join(lines) + "\n")


@pytest.fixture()
def tree(tmp_path):
    """Build ``camelot/lore/realm`` and reset the config warning latch.

    ``lore.config`` warns at most once per process; a test reading stderr or
    a second malformed config needs the latch open.
    """
    import lore.config as config_module

    config_module._warned = False

    camelot = tmp_path / "camelot"
    lore_project = camelot / "lore"
    realm = lore_project / "realm"
    for project in (camelot, lore_project, realm):
        for entity_dir in _ENTITY_DIRS:
            (project / ".lore" / entity_dir).mkdir(parents=True, exist_ok=True)
    yield NestedTree(camelot=camelot, lore=lore_project, realm=realm)
    config_module._warned = False
