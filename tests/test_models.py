from datetime import datetime
from gitten.models import CommitInfo, BranchInfo


def test_commit_info_summary_line():
    c = CommitInfo(
        hash="abc1234def5678",
        short_hash="abc1234",
        message="fix: correct null pointer issue",
        author="Alice",
        date=datetime(2026, 4, 1, 12, 0, 0),
        is_pushed=True,
        changed_files=["src/main.py"],
    )
    line = c.summary_line
    assert "abc1234" in line       # short hash
    assert "fix: correct" in line  # message content
    assert "Alice" in line         # author


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
    assert "●" in b.display_name
    assert "main" in b.display_name

    b2 = BranchInfo(name="origin/feature", is_local=False, is_current=False, remote="origin")
    assert "●" not in b2.display_name
    assert "origin/feature" in b2.display_name
