import pytest
import git
from pathlib import Path


@pytest.fixture
def sample_repo(tmp_path):
    """Creates a git repo with a few commits (no remote)."""
    repo = git.Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Initial commit
    (tmp_path / "README.md").write_text("# gitten test repo")
    repo.index.add(["README.md"])
    repo.index.commit("init: initial commit")

    # Second commit
    (tmp_path / "main.py").write_text("print('hello')")
    repo.index.add(["main.py"])
    repo.index.commit("feat: add main.py")

    # Third commit (will simulate as "unpushed")
    (tmp_path / "extra.py").write_text("x = 1")
    repo.index.add(["extra.py"])
    repo.index.commit("feat: add extra.py")

    return repo
