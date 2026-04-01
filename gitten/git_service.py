from __future__ import annotations

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

    def list_commits(
        self,
        branch: str | None,
        author: str | None = None,
        max_count: int = 200,
    ) -> list[CommitInfo]:
        rev = branch if branch else self._repo.active_branch.name
        unpushed_hashes = self._get_unpushed_hashes()

        commits = []
        for commit in self._repo.iter_commits(rev, max_count=max_count):
            if author and author.lower() not in commit.author.name.lower():
                continue
            changed = self._get_changed_files(commit)
            commits.append(CommitInfo(
                hash=commit.hexsha,
                short_hash=commit.hexsha[:7],
                message=commit.message.strip(),
                author=commit.author.name,
                date=commit.authored_datetime,
                is_pushed=commit.hexsha not in unpushed_hashes,
                changed_files=changed,
            ))
        return commits

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

    def _get_unpushed_hashes(self) -> set[str]:
        """Returns hashes of commits not yet pushed to remote.
        Always checks the currently active branch, regardless of what
        branch is being listed in list_commits().
        """
        try:
            branch = self._repo.active_branch
            tracking = branch.tracking_branch()
            if tracking is None:
                # No remote tracking branch — all commits are "unpushed"
                return {c.hexsha for c in self._repo.iter_commits(branch.name, max_count=500)}
            commits = self._repo.iter_commits(f"{tracking}..{branch.name}")
            return {c.hexsha for c in commits}
        except Exception:
            return set()

    def _get_changed_files(self, commit: git.Commit) -> list[str]:
        if not commit.parents:
            return list(commit.stats.files.keys())
        parent = commit.parents[0]
        diffs = parent.diff(commit)
        return [d.b_path or d.a_path for d in diffs]
