from __future__ import annotations
from textual.widget import Widget
from textual.app import ComposeResult
from textual.widgets import Label
from gitten.git_service import GitService


class BranchPanel(Widget):
    def __init__(self, git: GitService, **kwargs) -> None:
        super().__init__(**kwargs)
        self.git = git

    def compose(self) -> ComposeResult:
        yield Label("Branch Panel (stub)")

    def refresh_data(self) -> None:
        pass
