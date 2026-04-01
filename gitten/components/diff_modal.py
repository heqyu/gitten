from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Label
from textual.containers import ScrollableContainer

from gitten.git_service import GitService


class DiffModal(ModalScreen):
    """Full-screen modal for viewing file diffs."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("n", "next_file", "Next file"),
        ("p", "prev_file", "Prev file"),
        ("j", "scroll_down", "Scroll down"),
        ("k", "scroll_up", "Scroll up"),
    ]

    def __init__(
        self,
        diff_text: str,
        file_path: str,
        all_files: list[str],
        commit_hash: str,
        git: GitService,
    ) -> None:
        super().__init__()
        self._diff_text = diff_text
        self._file_path = file_path
        self._all_files = all_files
        self._commit_hash = commit_hash
        self._git = git
        self._file_index = all_files.index(file_path) if file_path in all_files else 0

    def compose(self) -> ComposeResult:
        yield Label("", id="diff-file-label")
        yield ScrollableContainer(Static("", id="diff-content"), id="diff-container")
        yield Label("n: next file  p: prev file  ↑↓/jk: scroll  Esc: close", id="diff-footer")

    def on_mount(self) -> None:
        self._render_diff()

    def _render_diff(self) -> None:
        self.query_one("#diff-file-label", Label).update(
            f"  {self._file_path}  [{self._file_index + 1}/{len(self._all_files)}]"
        )
        lines = []
        for line in self._diff_text.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                lines.append(f"[green]{line}[/green]")
            elif line.startswith("-") and not line.startswith("---"):
                lines.append(f"[red]{line}[/red]")
            else:
                lines.append(line)
        self.query_one("#diff-content", Static).update("\n".join(lines))

    def action_next_file(self) -> None:
        if self._file_index < len(self._all_files) - 1:
            self._file_index += 1
            self._file_path = self._all_files[self._file_index]
            self._diff_text = self._git.get_file_diff(self._commit_hash, self._file_path)
            self._render_diff()

    def action_prev_file(self) -> None:
        if self._file_index > 0:
            self._file_index -= 1
            self._file_path = self._all_files[self._file_index]
            self._diff_text = self._git.get_file_diff(self._commit_hash, self._file_path)
            self._render_diff()

    def action_scroll_down(self) -> None:
        self.query_one("#diff-container", ScrollableContainer).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#diff-container", ScrollableContainer).scroll_up()
