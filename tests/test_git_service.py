import pytest
import git
from pathlib import Path
from gitten.git_service import GitService
from gitten.models import CommitInfo


def test_list_branches_includes_local(sample_repo):
    svc = GitService(sample_repo.working_dir)
    branches = svc.list_branches()
    names = [b.name for b in branches]
    assert any("master" in n or "main" in n for n in names)


def test_list_branches_marks_current(sample_repo):
    svc = GitService(sample_repo.working_dir)
    branches = svc.list_branches()
    current = [b for b in branches if b.is_current]
    assert len(current) == 1


def test_list_commits_returns_commit_info(sample_repo):
    svc = GitService(sample_repo.working_dir)
    commits = svc.list_commits(branch=None)  # current branch
    assert len(commits) >= 2
    assert all(isinstance(c, CommitInfo) for c in commits)


def test_list_commits_author_filter(sample_repo):
    svc = GitService(sample_repo.working_dir)
    commits = svc.list_commits(branch=None, author="Test User")
    assert len(commits) >= 2
    assert all(c.author == "Test User" for c in commits)


def test_list_commits_author_filter_no_match(sample_repo):
    svc = GitService(sample_repo.working_dir)
    commits = svc.list_commits(branch=None, author="Nobody")
    assert commits == []


def test_get_current_user(sample_repo):
    svc = GitService(sample_repo.working_dir)
    assert svc.get_current_user() == "Test User"


def test_changed_files_on_commit(sample_repo):
    svc = GitService(sample_repo.working_dir)
    commits = svc.list_commits(branch=None)
    # latest commit added extra.py
    latest = commits[0]
    assert "extra.py" in latest.changed_files


def test_get_file_diff_returns_string(sample_repo):
    svc = GitService(sample_repo.working_dir)
    commits = svc.list_commits(branch=None)
    latest = commits[0]
    diff = svc.get_file_diff(commit_hash=latest.hash, file_path=latest.changed_files[0])
    assert isinstance(diff, str)
    assert len(diff) > 0


def test_revert_creates_new_commit(sample_repo):
    svc = GitService(sample_repo.working_dir)
    commits_before = svc.list_commits(branch=None)
    count_before = len(commits_before)
    target = commits_before[0]  # latest commit

    svc.revert(commit_hash=target.hash)

    commits_after = svc.list_commits(branch=None)
    assert len(commits_after) == count_before + 1
    assert "revert" in commits_after[0].message.lower()


def test_drop_removes_commit(sample_repo):
    svc = GitService(sample_repo.working_dir)
    commits_before = svc.list_commits(branch=None)
    target_hash = commits_before[0].hash  # latest (unpushed)

    svc.drop(commit_hash=target_hash)

    commits_after = svc.list_commits(branch=None)
    hashes_after = [c.hash for c in commits_after]
    assert target_hash not in hashes_after
    assert len(commits_after) == len(commits_before) - 1


def test_squash_unpushed_reduces_to_one(sample_repo):
    """Squash merges the latest unpushed commit and all preceding unpushed into one."""
    svc = GitService(sample_repo.working_dir)
    # sample_repo has 3 commits, all unpushed (no remote)
    commits_before = svc.list_commits(branch=None)
    target = commits_before[0]  # latest

    svc.squash(commit_hash=target.hash, message="squash: combined")

    commits_after = svc.list_commits(branch=None)
    assert len(commits_after) == 1
    assert commits_after[0].message == "squash: combined"


def test_cherry_pick_applies_commit(sample_repo, tmp_path):
    """Cherry-pick a commit from another branch onto current."""
    repo = sample_repo
    # Remember the original branch before creating feature branch
    original_branch = repo.active_branch

    # Create a new branch with an extra commit
    new_branch = repo.create_head("feature")
    new_branch.checkout()
    (Path(repo.working_dir) / "feature.py").write_text("feature = True")
    repo.index.add(["feature.py"])
    pick_commit = repo.index.commit("feat: add feature.py")

    # Switch back to original branch
    original_branch.checkout()

    svc = GitService(repo.working_dir)
    svc.cherry_pick(commit_hash=pick_commit.hexsha)

    commits = svc.list_commits(branch=None)
    assert any("feature.py" in f for c in commits for f in c.changed_files)
