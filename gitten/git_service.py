from __future__ import annotations

import os
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import git

from gitten.models import BranchInfo, CommitInfo


class DirtyWorkdirError(Exception):
    """Raised when a git mutation requires a clean working directory."""


class RebaseConflictError(Exception):
    """Raised when an interactive rebase fails mid-way (conflict or error)."""


# Field separator (ASCII Unit Separator) — extremely unlikely in commit messages.
# Used last so split(..., 4) puts any stray \x1f chars in the message field.
_SEP = "\x1f"


class GitService:
    def __init__(self, repo_path: str | Path) -> None:
        self._repo = git.Repo(repo_path)
        self._git_dir = Path(self._repo.git_dir)

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
        current_name = self._head_branch_name()  # "HEAD" if detached

        # Local branches
        try:
            out = self._repo.git.branch("--format=%(refname:short)")
            for name in (ln.strip() for ln in out.splitlines()):
                if name:
                    results.append(BranchInfo(
                        name=name, is_local=True,
                        is_current=(name == current_name), remote=None,
                    ))
        except Exception:
            pass

        # Remote branches
        try:
            out = self._repo.git.branch("-r", "--format=%(refname:short)")
            for name in (ln.strip() for ln in out.splitlines()):
                if not name or name.endswith("/HEAD"):
                    continue
                remote = name.split("/")[0]
                results.append(BranchInfo(
                    name=name, is_local=False, is_current=False, remote=remote,
                ))
        except Exception:
            pass

        return results

    def _head_branch_name(self) -> str:
        """Return current branch name, or 'HEAD' if in detached HEAD state."""
        try:
            return self._repo.git.rev_parse("--abbrev-ref", "HEAD").strip()
        except Exception:
            return "HEAD"

    def get_current_branch_name(self) -> str:
        """Human-readable name for UI display."""
        name = self._head_branch_name()
        if name == "HEAD":
            try:
                hexsha = self._repo.git.rev_parse("HEAD").strip()
                return f"HEAD ({hexsha[:7]})"
            except Exception:
                return "HEAD (detached)"
        return name

    def _current_rev(self) -> str:
        """Git-parseable rev for current HEAD (safe in detached HEAD)."""
        name = self._head_branch_name()
        if name == "HEAD":
            try:
                return self._repo.git.rev_parse("HEAD").strip()
            except Exception:
                return "HEAD"
        return name

    def list_commits(
        self,
        branch: str | None,
        author: str | None = None,
        max_count: int = 200,
    ) -> list[CommitInfo]:
        rev = branch if branch else self._current_rev()
        unpushed_hashes = self._get_unpushed_hashes(branch=branch)

        # Records terminated by NUL (\x00); fields by \x1f.
        # Message is last so any stray \x1f in the body stays in parts[4].
        fmt = f"%H{_SEP}%h{_SEP}%aN{_SEP}%aI{_SEP}%B%x00"
        args = [rev, f"--format={fmt}", f"--max-count={max_count}"]
        if author:
            args.append(f"--author={author}")

        try:
            raw = self._repo.git.log(*args)
        except Exception:
            return []

        commits: list[CommitInfo] = []
        for record in raw.split("\x00"):
            record = record.strip()
            if not record:
                continue
            parts = record.split(_SEP, 4)
            if len(parts) < 5:
                continue
            full_hash, short_hash, author_name, date_str = (p.strip() for p in parts[:4])
            message = parts[4].strip()
            if not full_hash:
                continue
            try:
                date = datetime.fromisoformat(date_str)
            except Exception:
                date = datetime.now(timezone.utc)
            commits.append(CommitInfo(
                hash=full_hash,
                short_hash=short_hash,
                message=message,
                author=author_name,
                date=date,
                is_pushed=full_hash not in unpushed_hashes,
                changed_files=[],  # lazy — fetched on demand
            ))
        return commits

    def get_changed_files(self, commit_hash: str) -> list[str]:
        """Fetch changed files for a single commit (lazy, called from detail panel)."""
        parent_line = self._repo.git.log("--format=%P", "-1", commit_hash).strip()
        if not parent_line:
            # Initial commit — diff against empty tree
            output = self._repo.git.diff_tree(
                "--no-commit-id", "-r", "--name-only", commit_hash
            )
        else:
            first_parent = parent_line.split()[0]
            output = self._repo.git.diff_tree(
                "--no-commit-id", "-r", "--name-only", first_parent, commit_hash,
            )
        return [f for f in output.splitlines() if f]

    def get_file_diff(self, commit_hash: str, file_path: str) -> str:
        parent_line = self._repo.git.log("--format=%P", "-1", commit_hash).strip()
        if not parent_line:
            return self._repo.git.diff(git.NULL_TREE, commit_hash, "--", file_path)
        first_parent = parent_line.split()[0]
        return self._repo.git.diff(first_parent, commit_hash, "--", file_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_unpushed_hashes(self, branch: str | None = None) -> set[str]:
        """Return full hashes of commits not yet pushed to the tracking remote."""
        try:
            ref_name = branch if branch else self._head_branch_name()

            # Resolve tracking branch name via rev-parse
            try:
                tracking = self._repo.git.rev_parse(
                    "--abbrev-ref", f"{ref_name}@{{upstream}}"
                ).strip()
            except git.GitCommandError:
                # No upstream configured — treat everything as unpushed
                out = self._repo.git.log("--format=%H", ref_name)
                return set(out.splitlines())

            out = self._repo.git.log("--format=%H", f"{tracking}..{ref_name}")
            return set(out.splitlines())
        except Exception:
            return set()

    def _require_clean_workdir(self) -> None:
        """Raise DirtyWorkdirError if there are uncommitted changes (staged or unstaged)."""
        out = self._repo.git.status("--porcelain")
        dirty = [ln[3:] for ln in out.splitlines()
                 if ln.strip() and ln[:2] not in ("??", "  ")]
        if dirty:
            files = ", ".join(dirty[:5])
            if len(dirty) > 5:
                files += f" (+{len(dirty) - 5} more)"
            raise DirtyWorkdirError(
                f"You have uncommitted changes: {files}\n"
                "Please commit or stash them before proceeding."
            )

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def revert(self, commit_hash: str) -> None:
        self._require_clean_workdir()
        self._repo.git.revert(commit_hash, "--no-edit")

    def drop(self, commit_hash: str) -> None:
        """Remove a commit using interactive rebase. Works on Windows and Unix."""
        self._require_clean_workdir()

        try:
            depth = int(self._repo.git.rev_list("--count", "HEAD").strip())
        except Exception:
            depth = 0
        if depth < 2:
            raise ValueError("Cannot drop the only commit in the repository.")

        # Write the sequence editor as a plain Python script — no shell required,
        # works identically on Windows and Unix.
        py_script = (
            "import sys\n"
            f"target = {commit_hash!r}\n"
            "lines = open(sys.argv[1]).readlines()\n"
            "out = []\n"
            "for line in lines:\n"
            "    parts = line.split()\n"
            "    if len(parts) >= 2 and parts[0] == 'pick' and target.startswith(parts[1]):\n"
            "        out.append('drop ' + ' '.join(parts[1:]) + '\\n')\n"
            "    else:\n"
            "        out.append(line)\n"
            "open(sys.argv[1], 'w').writelines(out)\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as pf:
            pf.write(py_script)
            py_path = pf.name

        # GIT_SEQUENCE_EDITOR must be an executable command; wrap in a launcher.
        if sys.platform == "win32":
            launcher_content = f'@echo off\n"{sys.executable}" "{py_path}" %*\n'
            launcher_suffix = ".bat"
        else:
            launcher_content = f'#!/bin/sh\nexec "{sys.executable}" "{py_path}" "$@"\n'
            launcher_suffix = ".sh"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=launcher_suffix, delete=False, encoding="utf-8"
        ) as lf:
            lf.write(launcher_content)
            launcher_path = lf.name

        if sys.platform != "win32":
            os.chmod(launcher_path, os.stat(launcher_path).st_mode | stat.S_IEXEC)

        try:
            env = os.environ.copy()
            env["GIT_SEQUENCE_EDITOR"] = launcher_path
            rebase_range = f"HEAD~{min(50, depth - 1)}"
            self._repo.git.rebase("-i", rebase_range, env=env)
        except git.GitCommandError as e:
            if (self._git_dir / "rebase-merge").exists() \
                    or (self._git_dir / "rebase-apply").exists():
                raise RebaseConflictError(str(e)) from e
            raise
        finally:
            for path in (py_path, launcher_path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def abort_rebase(self) -> None:
        self._repo.git.rebase("--abort")

    def squash(self, commit_hash: str, message: str) -> None:
        """Squash all unpushed commits into one commit with the given message."""
        unpushed = self._get_unpushed_hashes()
        if commit_hash not in unpushed:
            raise ValueError(
                f"Commit {commit_hash[:7]} is already pushed and cannot be squashed."
            )

        # All hashes on current branch, newest-first
        all_hashes = self._repo.git.log(
            "--format=%H", self._head_branch_name()
        ).splitlines()
        unpushed_ordered = [h for h in reversed(all_hashes) if h in unpushed]
        if not unpushed_ordered:
            return
        oldest_hash = unpushed_ordered[0]

        parent_line = self._repo.git.log("--format=%P", "-1", oldest_hash).strip()
        if not parent_line:
            # Entire branch is unpushed — orphan it
            self._repo.git.update_ref("-d", "HEAD")
        else:
            self._repo.git.reset("--soft", parent_line.split()[0])

        self._repo.git.commit("-m", message)

    def cherry_pick(self, commit_hash: str) -> None:
        self._repo.git.cherry_pick(commit_hash)

    def push(self) -> None:
        branch_name = self._head_branch_name()
        if branch_name == "HEAD":
            raise ValueError("Cannot push in detached HEAD state.")
        try:
            upstream = self._repo.git.rev_parse(
                "--abbrev-ref", f"{branch_name}@{{upstream}}"
            ).strip()
            remote_name = upstream.split("/")[0]
        except git.GitCommandError:
            raise ValueError(f"Branch '{branch_name}' has no remote tracking branch.")
        self._repo.git.push(remote_name, branch_name)

    def has_remote_tracking(self) -> bool:
        try:
            branch_name = self._head_branch_name()
            if branch_name == "HEAD":
                return False
            self._repo.git.rev_parse("--abbrev-ref", f"{branch_name}@{{upstream}}")
            return True
        except Exception:
            return False

    def abort_cherry_pick(self) -> None:
        self._repo.git.cherry_pick("--abort")

    def abort_revert(self) -> None:
        self._repo.git.revert("--abort")
