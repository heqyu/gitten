import pytest
import git
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
