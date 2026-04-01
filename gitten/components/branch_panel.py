from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Click, Key
from textual.widget import Widget
from textual.widgets import Input, ListView, ListItem, Label, Select, LoadingIndicator
from textual.message import Message
from textual import work

from gitten.git_service import GitService
from gitten.models import CommitInfo, BranchInfo


class BranchPanel(Widget):
    """Left panel: collapsible branch selector + commit list."""

    class CommitSelected(Message):
        def __init__(self, commit: CommitInfo) -> None:
            super().__init__()
            self.commit = commit

    def __init__(self, git: GitService, **kwargs) -> None:
        super().__init__(**kwargs)
        self.git = git
        self._commits: list[CommitInfo] = []
        self._branches: list[BranchInfo] = []
        self._selected_branch: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("≡", id="left-toggle-icon")
        yield Select([], id="branch-select", prompt="Select branch…")
        yield Input(placeholder="Filter by author", id="left-author-filter")
        yield LoadingIndicator(id="left-loading")
        yield ListView(id="left-commit-list")

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        self._branches = self.git.list_branches()
        options = [(b.display_name, b.name) for b in self._branches]
        sel = self.query_one("#branch-select", Select)
        sel.set_options(options)

    def _load_commits(self) -> None:
        if not self._selected_branch:
            return
        author = self.query_one("#left-author-filter", Input).value.strip() or None
        loading = self.query_one("#left-loading", LoadingIndicator)
        loading.display = True
        self._load_commits_worker(self._selected_branch, author)

    @work(thread=True)
    def _load_commits_worker(self, branch: str, author: str | None) -> None:
        commits = self.git.list_commits(branch=branch, author=author)
        self.app.call_from_thread(self._on_commits_loaded, commits)

    def _on_commits_loaded(self, commits: list[CommitInfo]) -> None:
        self._commits = commits
        loading = self.query_one("#left-loading", LoadingIndicator)
        loading.display = False
        lv = self.query_one("#left-commit-list", ListView)
        lv.clear()
        for commit in self._commits:
            item = ListItem(Label(commit.summary_line), classes="commit-row")
            if not commit.is_pushed:
                item.add_class("unpushed")
            lv.append(item)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "branch-select":
            if event.value is Select.BLANK:
                return
            self._selected_branch = event.value
            self._load_commits()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "left-author-filter":
            self._load_commits()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one("#left-commit-list", ListView).index
        if idx is not None and 0 <= idx < len(self._commits):
            commit = self._commits[idx]
            self.post_message(self.CommitSelected(commit))

    def get_selected_commit(self) -> CommitInfo | None:
        idx = self.query_one("#left-commit-list", ListView).index
        if idx is not None and 0 <= idx < len(self._commits):
            return self._commits[idx]
        return None

    def _open_context_menu(self, commit: CommitInfo) -> None:
        from gitten.components.context_menu import ContextMenu
        items = []
        items.append(("Cherry-pick to current branch", "cherry_pick"))
        items.append(("Copy hash", "copy_hash"))
        self.app.push_screen(ContextMenu(items=items, commit=commit, source="left"))

    def on_key(self, event: Key) -> None:
        if event.key == "m":
            commit = self.get_selected_commit()
            if commit:
                self._open_context_menu(commit)

    def on_click(self, event: Click) -> None:
        if event.button == 3:
            commit = self.get_selected_commit()
            if commit:
                self._open_context_menu(commit)
