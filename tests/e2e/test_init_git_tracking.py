"""E2E tests for what a `lore init` project actually puts in git.

Spec: conceptual-workflows-lore-init (lore codex show conceptual-workflows-lore-init)

Every other init test asks what Lore wrote. This one asks the only question a
teammate cares about: **after `git add -A && git commit`, what arrives on their
machine?** So nothing here reads an ignore file and reasons about it — each
assertion runs `git ls-files` against a real repository and takes git's answer.

That distinction is the whole point. A 54-cell sweep of agents x
``--skills-gitignore`` x ``--access`` found that ``lore-only`` — which
documents itself as "Lore's skills ignored, the user's own skills tracked" —
ignored *everything* under `.lore/skills/`, because a blanket ``skills/`` line
in the seeded `.lore/.gitignore` decided all three answers before the answer was
consulted. Reading the generated listing would have said the feature worked.
Asking git said the user's own authored skill was never committed and gone on
clone.

The five agents with ``skills_dir: null`` install to `.lore/skills/`, so they
are the ones the seeded file used to decide for; ``claude`` is the control that
was always correct.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from lore import agents as agent_registry
from lore import skills as skills_mod
from lore.init import apply_init, plan_init


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="these tests ask git, so they need git"
)


FALLBACK_AGENTS = ("agents-md", "gemini", "qwen", "cursor", "none")
"""Every agent whose skills land in `.lore/skills/` — the broken half of the sweep."""

LORE_ROOT = skills_mod.LORE_SKILLS_ROOT
CLAUDE_ROOT = ".claude/skills"

FAMILY = "memory"
"""One family rather than all of them: the defect is per-root, not per-skill."""

OWN_SKILL = "my-own-skill"
"""A skill the *user* wrote, dropped beside Lore's. The file that used to vanish."""


# ---------------------------------------------------------------------------
# Asking git
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr}"
    return proc.stdout


def committable(root: Path) -> set[str]:
    """Every path `git add -A` would stage, plus everything already staged.

    The union is deliberate: "will a teammate get this file" is true for a file
    already in the index *and* for one an ordinary `git add -A` would put there.
    An ignored path is in neither list, which is the whole assertion.
    """
    listed = _git(root, "ls-files", "--others", "--exclude-standard") + _git(
        root, "ls-files"
    )
    return {line for line in listed.splitlines() if line}


@pytest.fixture()
def repo(tmp_path):
    """An empty git repository, ready for `lore init`."""
    _git(tmp_path, "init", "-q", ".")
    return tmp_path


def init(root: Path, **answers) -> None:
    """Run one initialisation at *root* through the same path the CLI uses."""
    answers.setdefault("skill_families", [FAMILY])
    apply_init(plan_init(project_root=root, **answers))


def author_own_skill(root: Path, install_root: str) -> str:
    """Drop a skill the user wrote into *install_root*; return its repo path."""
    path = f"{install_root}/{OWN_SKILL}/SKILL.md"
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# mine\n", encoding="utf-8")
    return path


def lore_skill_paths(install_root: str) -> list[str]:
    """Every file this release installs into *install_root* for ``FAMILY``."""
    return [
        f"{install_root}/{skill_id}/{relative}"
        for skill_id in skills_mod.skills_in_families((FAMILY,))
        for relative in skills_mod.skill_files(skill_id)
    ]


# ---------------------------------------------------------------------------
# F1 — the user's own skill under `.lore/skills/`
# ---------------------------------------------------------------------------


class TestLoreOnlyKeepsTheUsersOwnSkill:
    """`lore-only` promises exactly one thing; it has to hold in every root."""

    @pytest.mark.parametrize("agent", FALLBACK_AGENTS)
    def test_a_user_authored_skill_in_the_fallback_root_is_committable(
        self, repo, agent
    ):
        init(repo, agents=[agent], skills_gitignore="lore-only")
        mine = author_own_skill(repo, LORE_ROOT)
        assert mine in committable(repo)

    @pytest.mark.parametrize("agent", FALLBACK_AGENTS)
    def test_lores_own_skills_in_the_fallback_root_are_not(self, repo, agent):
        init(repo, agents=[agent], skills_gitignore="lore-only")
        installed = committable(repo)
        assert not [path for path in lore_skill_paths(LORE_ROOT) if path in installed]

    def test_the_generated_listing_is_itself_committed(self, repo):
        """The rule has to reach the clone, or it only ever holds locally."""
        init(repo, agents=["gemini"], skills_gitignore="lore-only")
        assert f"{LORE_ROOT}/.gitignore" in committable(repo)

    def test_the_native_root_still_behaves_the_way_it_always_did(self, repo):
        init(repo, agents=["claude"], skills_gitignore="lore-only")
        mine = author_own_skill(repo, CLAUDE_ROOT)
        installed = committable(repo)
        assert mine in installed
        assert not [path for path in lore_skill_paths(CLAUDE_ROOT) if path in installed]


# ---------------------------------------------------------------------------
# F2 — `none` was inert for `.lore/skills`
# ---------------------------------------------------------------------------


class TestNoneTracksEverything:
    """"Teammates get the skills without installing lore" — in every root."""

    @pytest.mark.parametrize("agent", FALLBACK_AGENTS)
    def test_every_installed_file_in_the_fallback_root_is_committable(
        self, repo, agent
    ):
        init(repo, agents=[agent], skills_gitignore="none")
        installed = committable(repo)
        assert [path for path in lore_skill_paths(LORE_ROOT) if path not in installed] == []

    def test_no_listing_file_is_written(self, repo):
        init(repo, agents=["gemini"], skills_gitignore="none")
        assert not (repo / LORE_ROOT / ".gitignore").exists()


# ---------------------------------------------------------------------------
# F3 — one answer, one meaning, however many roots
# ---------------------------------------------------------------------------


class TestOneAnswerGovernsEveryRoot:
    """A multi-agent selection used to run two tracking policies at once."""

    def test_none_tracks_both_roots(self, repo):
        init(repo, agents=["claude", "agents-md"], skills_gitignore="none")
        installed = committable(repo)
        wanted = lore_skill_paths(CLAUDE_ROOT) + lore_skill_paths(LORE_ROOT)
        assert [path for path in wanted if path not in installed] == []

    def test_lore_only_keeps_the_users_own_skill_in_both_roots(self, repo):
        init(repo, agents=["claude", "agents-md"], skills_gitignore="lore-only")
        mine = [author_own_skill(repo, root) for root in (CLAUDE_ROOT, LORE_ROOT)]
        installed = committable(repo)
        assert [path for path in mine if path not in installed] == []

    def test_all_ignores_both_roots(self, repo):
        init(repo, agents=["claude", "agents-md"], skills_gitignore="all")
        installed = committable(repo)
        skills_files = lore_skill_paths(CLAUDE_ROOT) + lore_skill_paths(LORE_ROOT)
        assert [path for path in skills_files if path in installed] == []


# ---------------------------------------------------------------------------
# F4 — `all` has to be honoured by the answer, not by a blanket line
# ---------------------------------------------------------------------------


class TestAllIsHonouredByTheAnswer:
    def test_the_fallback_root_is_ignored_including_the_users_own_skill(self, repo):
        init(repo, agents=["gemini"], skills_gitignore="all")
        mine = author_own_skill(repo, LORE_ROOT)
        installed = committable(repo)
        assert mine not in installed
        assert [path for path in lore_skill_paths(LORE_ROOT) if path in installed] == []

    def test_switching_to_none_makes_the_same_files_committable(self, repo):
        """Proof the answer decides: nothing else about the project changed."""
        init(repo, agents=["gemini"], skills_gitignore="all")
        assert lore_skill_paths(LORE_ROOT)[0] not in committable(repo)
        init(repo, agents=["gemini"], skills_gitignore="none")
        installed = committable(repo)
        assert [path for path in lore_skill_paths(LORE_ROOT) if path not in installed] == []


# ---------------------------------------------------------------------------
# The seeded `.lore/.gitignore` — the line that used to decide everything
# ---------------------------------------------------------------------------


class TestTheSeededLoreIgnoreDoesNotDecideSkillTracking:
    def test_it_no_longer_ignores_the_skills_tree_wholesale(self, repo):
        init(repo, agents=["none"], skills_gitignore="none")
        lines = (repo / ".lore" / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert "skills/" not in lines

    def test_every_other_user_authorable_lore_subtree_still_tracks(self, repo):
        """The negation pairs that already worked must keep working."""
        init(repo, agents=["none"], skills_gitignore="lore-only")
        authored = []
        for relative in (
            "knights/mine.md",
            "doctrines/mine.yaml",
            "artifacts/mine.md",
            "rites/mine.md",
            "watchers/mine.yaml",
            "codex/mine.md",
            "custom-schemas/mine.yaml",
        ):
            target = repo / ".lore" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("mine\n", encoding="utf-8")
            authored.append(f".lore/{relative}")
        installed = committable(repo)
        assert [path for path in authored if path not in installed] == []


# ---------------------------------------------------------------------------
# F10 — an ignore rule cannot untrack what is already in the index
# ---------------------------------------------------------------------------


def commit_everything(root: Path) -> None:
    _git(root, "add", "-A")
    _git(
        root,
        "-c",
        "user.email=t@example.invalid",
        "-c",
        "user.name=T",
        "commit",
        "-qm",
        "base",
    )


class TestSwitchingToATighterAnswerAfterACommit:
    """git keeps a committed file tracked whatever a later ignore rule says."""

    def _switch(self, root, before, after):
        init(root, agents=["claude"], skills_gitignore=before)
        commit_everything(root)
        result = apply_init(
            plan_init(
                project_root=root,
                agents=["claude"],
                skill_families=[FAMILY],
                skills_gitignore=after,
            )
        )
        return "\n".join(result.messages)

    def test_none_to_lore_only_says_the_committed_copies_stay_tracked(self, repo):
        report = self._switch(repo, "none", "lore-only")
        assert "none -> lore-only" in report or "none → lore-only" in report
        assert "git rm" in report

    def test_none_to_all_says_it_too(self, repo):
        report = self._switch(repo, "none", "all")
        assert "git rm" in report

    def test_the_named_command_actually_untracks_what_the_answer_ignores(self, repo):
        """The recipe in the message has to be the one that works."""
        self._switch(repo, "none", "lore-only")
        roots = list(skills_mod.install_roots(
            (agent_registry.get_agent("claude"),)
        ))
        _git(repo, "rm", "-r", "--cached", "--ignore-unmatch", "-q", *roots)
        _git(repo, "add", *roots)
        staged = set(_git(repo, "ls-files").splitlines())
        assert [path for path in lore_skill_paths(CLAUDE_ROOT) if path in staged] == []

    def test_a_loosening_switch_says_nothing(self, repo):
        """`lore-only` -> `none` needs no warning: nothing becomes ignored."""
        report = self._switch(repo, "lore-only", "none")
        assert "git rm" not in report

    def test_a_first_run_says_nothing(self, repo):
        result = apply_init(
            plan_init(
                project_root=repo,
                agents=["claude"],
                skill_families=[FAMILY],
                skills_gitignore="all",
            )
        )
        assert "git rm" not in "\n".join(result.messages)
