from __future__ import annotations

from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Label

from gitten.git_service import GitService
from gitten.components.branch_panel import BranchPanel
from gitten.components.commit_panel import CommitPanel
from gitten.components.detail_panel import DetailPanel


class GittenApp(App):
    """Main gitten application."""

    CSS_PATH = Path(__file__).parent / "styles.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("question_mark", "help", "Help"),
        ("[", "toggle_left", "Toggle left panel"),
    ]

    REFRESH_INTERVAL = 3600  # seconds

    def __init__(self, repo_path: Path) -> None:
        super().__init__()
        self.repo_path = repo_path
        self.git = GitService(repo_path)
        self._left_expanded = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield BranchPanel(git=self.git, id="left-panel")
        yield CommitPanel(git=self.git, id="middle-panel")
        yield DetailPanel(git=self.git, id="right-panel")
        yield Label("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"gitten  {self.repo_path}"
        self.action_refresh()
        self.set_interval(self.REFRESH_INTERVAL, self.action_refresh)

    def action_refresh(self) -> None:
        self.query_one(CommitPanel).refresh_commits()
        self.query_one(BranchPanel).refresh_data()

    def action_toggle_left(self) -> None:
        left = self.query_one("#left-panel")
        self._left_expanded = not self._left_expanded
        if self._left_expanded:
            left.add_class("expanded")
        else:
            left.remove_class("expanded")

    def action_help(self) -> None:
        from gitten.components.help_modal import HelpModal
        self.push_screen(HelpModal())

    def show_status(self, message: str, style: str = "success") -> None:
        bar = self.query_one("#status-bar", Label)
        bar.update(message)
        bar.set_classes(style)
        self.set_timer(3, lambda: bar.update(""))

    def show_error(self, message: str, allow_abort: bool = False, abort_fn=None) -> None:
        from gitten.components.error_modal import ErrorModal
        self.push_screen(ErrorModal(message=message, allow_abort=allow_abort, abort_fn=abort_fn))

    # ------------------------------------------------------------------
    # Cross-panel events
    # ------------------------------------------------------------------

    def on_commit_panel_commit_selected(self, event) -> None:
        self.query_one(DetailPanel).show_commit(event.commit)

    def on_branch_panel_commit_selected(self, event) -> None:
        self.query_one(DetailPanel).show_commit(event.commit)
