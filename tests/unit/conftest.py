import pytest
from pathlib import Path


@pytest.fixture()
def bare_lore_dir(tmp_path):
    """Minimal .lore/ directory without running lore init.

    Use this for testing file-system modules (frontmatter, codex, knight,
    doctrine, artifact) in isolation from the full init sequence.
    """
    lore = tmp_path / ".lore"
    for d in ["knights", "doctrines", "codex", "artifacts"]:
        (lore / d).mkdir(parents=True)
    return tmp_path
