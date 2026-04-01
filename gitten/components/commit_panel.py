from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Click, Key
from textual.widget import Widget
from textual.widgets import Input, ListView, ListItem, Label, LoadingIndicator
from textual.message import Message
from textual import work

from gitten.git_service import GitService
from gitten.models import CommitInfo


class CommitPanel(Widget):
    """Middle panel: current branch commits with author filter."""

    class CommitSelected(Message):
        def __init__(self, commit: CommitInfo) -> None:
            super().__init__()
            self.commit = commit

    def __init__(self, git: GitService, **kwargs) -> None:
        super().__init__(**kwargs)
        self.git = git
        self._commits: list[CommitInfo] = []

    def compose(self) -> ComposeResult:
        current = self.git.get_current_user()
        branch_name = self.git.get_current_branch_name()
        yield Label(f" {branch_name}", id="middle-branch-label")
        yield Input(
            value=current,
            placeholder="Filter by author (blank = all)",
            id="middle-author-filter",
        )
        yield LoadingIndicator(id="middle-loading")
        yield ListView(id="middle-commit-list")

    def on_mount(self) -> None:
        self.refresh_commits()

    def refresh_commits(self) -> None:
        author = self.query_one("#middle-author-filter", Input).value.strip() or None
        loading = self.query_one("#middle-loading", LoadingIndicator)
        loading.display = True
        self._load_commits_worker(author)

    @work(thread=True)
    def _load_commits_worker(self, author: str | None) -> None:
        commits = self.git.list_commits(branch=None, author=author)
        self.app.call_from_thread(self._on_commits_loaded, commits)

    def _on_commits_loaded(self, commits: list[CommitInfo]) -> None:
        self._commits = commits
        loading = self.query_one("#middle-loading", LoadingIndicator)
        loading.display = False
        self._render_list()

    def _render_list(self) -> None:
        lv = self.query_one("#middle-commit-list", ListView)
        lv.clear()
        for commit in self._commits:
            item = ListItem(Label(commit.summary_line), classes="commit-row")
            if not commit.is_pushed:
                item.add_class("unpushed")
            lv.append(item)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "middle-author-filter":
            self.refresh_commits()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one("#middle-commit-list", ListView).index
        if idx is not None and 0 <= idx < len(self._commits):
            self.post_message(self.CommitSelected(self._commits[idx]))

    def get_selected_commit(self) -> CommitInfo | None:
        idx = self.query_one("#middle-commit-list", ListView).index
        if idx is not None and 0 <= idx < len(self._commits):
            return self._commits[idx]
        return None

    def on_key(self, event: Key) -> None:
        if event.key == "m":
            commit = self.get_selected_commit()
            if commit:
                self._open_context_menu(commit)

    def _open_context_menu(self, commit: CommitInfo) -> None:
        from gitten.components.context_menu import ContextMenu
        has_remote = self.git.has_remote_tracking()
        items = []
        items.append(("Revert", "revert"))
        if not commit.is_pushed:
            items.append(("Drop", "drop"))
            items.append(("Squash (all unpushed)", "squash"))
        if has_remote:
            items.append(("Push to remote", "push"))
        items.append(("Copy hash", "copy_hash"))
        self.app.push_screen(ContextMenu(items=items, commit=commit, source="middle"))

    def on_click(self, event: Click) -> None:
        if event.button == 3:
            commit = self.get_selected_commit()
            if commit:
                self._open_context_menu(commit)
