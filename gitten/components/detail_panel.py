from __future__ import annotations

import pyperclip
from textual.app import ComposeResult
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Label, ListView, ListItem, Static

from gitten.git_service import GitService
from gitten.models import CommitInfo


class DetailPanel(Widget):
    """Right panel: commit metadata + changed files list."""

    def __init__(self, git: GitService, **kwargs) -> None:
        super().__init__(**kwargs)
        self.git = git
        self._commit: CommitInfo | None = None

    def compose(self) -> ComposeResult:
        yield Static("Select a commit to view details.", id="detail-meta")
        yield ListView(id="detail-files")
        yield Label("[c] Copy log", id="detail-hint")

    def show_commit(self, commit: CommitInfo) -> None:
        self._commit = commit
        meta = self.query_one("#detail-meta", Static)
        meta.update(
            f"commit  {commit.hash}\n"
            f"Author  {commit.author}\n"
            f"Date    {commit.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"\n{commit.message}\n"
            f"\nChanges:"
        )
        lv = self.query_one("#detail-files", ListView)
        lv.clear()
        for f in commit.changed_files:
            lv.append(ListItem(Label(f"  > {f}")))

    def on_key(self, event: Key) -> None:
        if event.key == "c" and self._commit:
            text = (
                f"commit {self._commit.hash}\n"
                f"Author: {self._commit.author}\n"
                f"Date:   {self._commit.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"\n    {self._commit.message}\n"
            )
            pyperclip.copy(text)
            self.app.show_status("Commit log copied to clipboard.")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not self._commit:
            return
        idx = self.query_one("#detail-files", ListView).index
        if idx is not None and 0 <= idx < len(self._commit.changed_files):
            file_path = self._commit.changed_files[idx]
            diff = self.git.get_file_diff(self._commit.hash, file_path)
            from gitten.components.diff_modal import DiffModal
            self.app.push_screen(DiffModal(
                diff_text=diff,
                file_path=file_path,
                all_files=self._commit.changed_files,
                commit_hash=self._commit.hash,
                git=self.git,
            ))
