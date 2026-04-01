from datetime import datetime
from gitten.models import CommitInfo, BranchInfo


def test_commit_info_fields():
    c = CommitInfo(
        hash="abc1234",
        short_hash="abc1234",
        message="fix: correct null pointer",
        author="Alice",
        date=datetime(2026, 4, 1, 12, 0, 0),
        is_pushed=False,
        changed_files=["src/main.py", "tests/test_main.py"],
    )
    assert c.hash == "abc1234"
    assert c.is_pushed is False
    assert len(c.changed_files) == 2


def test_commit_info_relative_time_recent():
    from datetime import timezone, timedelta
    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=2)
    c = CommitInfo(
        hash="abc1234",
        short_hash="abc1234",
        message="test",
        author="Alice",
        date=recent,
        is_pushed=True,
        changed_files=[],
    )
    assert "h" in c.relative_time  # e.g. "2h"


def test_branch_info_fields():
    b = BranchInfo(name="main", is_local=True, is_current=True, remote="origin")
    assert b.display_name == "main"
    b2 = BranchInfo(name="origin/feature", is_local=False, is_current=False, remote="origin")
    assert b2.display_name == "origin/feature"
