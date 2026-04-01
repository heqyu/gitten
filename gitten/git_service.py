from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
import git

from gitten.models import BranchInfo, CommitInfo


class GitService:
    def __init__(self, repo_path: str | Path) -> None:
        self._repo = git.Repo(repo_path)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_current_user(self) -> str:
        try:
            return self._repo.config_reader().get_value("user", "name", "")
        except Exception:
            return ""

    def list_branches(self) -> list[BranchInfo]:
        results: list[BranchInfo] = []
        current = self._repo.active_branch.name if not self._repo.head.is_detached else ""

        for branch in self._repo.branches:
            results.append(BranchInfo(
                name=branch.name,
                is_local=True,
                is_current=(branch.name == current),
                remote=None,
            ))

        for remote in self._repo.remotes:
            for ref in remote.refs:
                # Skip HEAD pointers like origin/HEAD
                if ref.remote_head == "HEAD":
                    continue
                results.append(BranchInfo(
                    name=ref.name,
                    is_local=False,
                    is_current=False,
                    remote=ref.remote_name,
                ))

        return results

    def get_current_branch_name(self) -> str:
        try:
            return self._repo.active_branch.name
        except TypeError:
            return f"HEAD ({self._repo.head.commit.hexsha[:7]})"

    def list_commits(
        self,
        branch: str | None,
        author: str | None = None,
        max_count: int = 200,
    ) -> list[CommitInfo]:
        rev = branch if branch else self.get_current_branch_name()
        unpushed_hashes = self._get_unpushed_hashes(branch=branch)

        commits = []
        for commit in self._repo.iter_commits(rev, max_count=max_count):
            if author and author.lower() not in commit.author.name.lower():
                continue
            commits.append(CommitInfo(
                hash=commit.hexsha,
                short_hash=commit.hexsha[:7],
                message=commit.message.strip(),
                author=commit.author.name,
                date=commit.authored_datetime,
                is_pushed=commit.hexsha not in unpushed_hashes,
                changed_files=[],  # lazy — fetched on demand via get_changed_files()
            ))
        return commits

    def get_changed_files(self, commit_hash: str) -> list[str]:
        """Fetch changed files for a single commit (called lazily on detail view)."""
        commit = self._repo.commit(commit_hash)
        return self._get_changed_files(commit)

    def get_file_diff(self, commit_hash: str, file_path: str) -> str:
        commit = self._repo.commit(commit_hash)
        if not commit.parents:
            # Initial commit: diff against empty tree
            diff = self._repo.git.diff(
                git.NULL_TREE, commit.hexsha, "--", file_path
            )
        else:
            diff = self._repo.git.diff(
                commit.parents[0].hexsha, commit.hexsha, "--", file_path
            )
        return diff

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_unpushed_hashes(self, branch: str | None = None) -> set[str]:
        """Returns hashes of commits not yet pushed to remote."""
        try:
            ref = self._repo.active_branch if branch is None else self._repo.heads[branch]
            tracking = ref.tracking_branch()
            if tracking is None:
                # No remote tracking branch — all commits are "unpushed"
                return {c.hexsha for c in self._repo.iter_commits(ref)}
            return {
                c.hexsha
                for c in self._repo.iter_commits(f"{tracking.name}..{ref.name}")
            }
        except Exception:
            return set()

    def _get_changed_files(self, commit: git.Commit) -> list[str]:
        if not commit.parents:
            return list(commit.stats.files.keys())
        parent = commit.parents[0]
        diffs = parent.diff(commit)
        return [d.b_path or d.a_path for d in diffs]

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def revert(self, commit_hash: str) -> None:
        """Create a new commit that reverts the given commit."""
        self._repo.git.revert(commit_hash, "--no-edit")

    def drop(self, commit_hash: str) -> None:
        """Remove a commit from history using interactive rebase (drop).

        Note: Relies on /bin/sh and Python being available.
        The GIT_SEQUENCE_EDITOR script drops the target commit by its full hash
        prefix-matching the abbreviated hash used by git in the rebase todo file.
        """
        script = f"""#!/bin/sh
python3 - "$1" << 'PYEOF'
import sys
target = "{commit_hash}"
path = sys.argv[1]
with open(path) as f:
    lines = f.readlines()
out = []
for line in lines:
    parts = line.split()
    if len(parts) >= 2 and parts[0] == "pick" and target.startswith(parts[1]):
        out.append("drop " + " ".join(parts[1:]) + "\\n")
    else:
        out.append(line)
with open(path, "w") as f:
    f.writelines(out)
PYEOF
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script)
            script_path = f.name
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)
        try:
            env = os.environ.copy()
            env["GIT_SEQUENCE_EDITOR"] = script_path
            # Count commits to determine safe rebase range
            all_commits = list(self._repo.iter_commits(
                self._repo.active_branch.name, max_count=51
            ))
            depth = len(all_commits)
            if depth < 2:
                # Only one commit — nothing to rebase onto
                raise ValueError("Cannot drop the only commit in the repository.")
            # Use HEAD~N where N = min(50, depth-1) to avoid going before initial commit
            rebase_range = f"HEAD~{min(50, depth - 1)}"
            self._repo.git.rebase("-i", rebase_range, env=env)
        finally:
            os.unlink(script_path)

    def squash(self, commit_hash: str, message: str) -> None:
        """Squash all unpushed commits up to and including commit_hash into one.

        Note: For repos where all commits are unpushed (no tracking branch),
        uses git update-ref -d HEAD to orphan the branch before recommitting.
        """
        unpushed = self._get_unpushed_hashes()
        all_commits = list(self._repo.iter_commits(
            self._repo.active_branch.name, max_count=500
        ))

        # Find commits to squash: from oldest unpushed up to commit_hash
        unpushed_commits = [c for c in all_commits if c.hexsha in unpushed]
        if not unpushed_commits:
            return

        # Verify commit_hash is in the unpushed set
        if commit_hash not in unpushed:
            raise ValueError(f"Commit {commit_hash[:7]} is already pushed and cannot be squashed.")

        oldest_unpushed = unpushed_commits[-1]  # last in list = oldest commit

        # Reset to the parent of the oldest unpushed commit
        if not oldest_unpushed.parents:
            # All commits are unpushed — orphan the branch
            self._repo.git.update_ref("-d", "HEAD")
        else:
            root = oldest_unpushed.parents[0].hexsha
            self._repo.git.reset("--soft", root)

        self._repo.index.commit(message)

    def cherry_pick(self, commit_hash: str) -> None:
        """Apply a commit from another branch onto the current branch."""
        self._repo.git.cherry_pick(commit_hash)

    def push(self) -> None:
        """Push current branch to its tracking remote. Raises git.GitCommandError on failure."""
        branch = self._repo.active_branch
        tracking = branch.tracking_branch()
        if tracking is None:
            raise ValueError(f"Branch '{branch.name}' has no remote tracking branch.")
        remote_name = tracking.remote_name
        self._repo.remote(remote_name).push(branch.name)

    def has_remote_tracking(self) -> bool:
        """Returns True if current branch has a remote tracking branch."""
        try:
            return self._repo.active_branch.tracking_branch() is not None
        except Exception:
            return False

    def abort_cherry_pick(self) -> None:
        self._repo.git.cherry_pick("--abort")

    def abort_revert(self) -> None:
        self._repo.git.revert("--abort")
