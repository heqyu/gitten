from __future__ import annotations

import pyperclip
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import ListView, ListItem, Label

from gitten.models import CommitInfo


class ContextMenu(ModalScreen):
    """Dynamic context menu for commit operations."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(
        self,
        items: list[tuple[str, str]],
        commit: CommitInfo,
        source: str,  # "middle" or "left"
    ) -> None:
        super().__init__()
        self._items = items  # [(label, action_key), ...]
        self._commit = commit
        self._source = source

    def compose(self) -> ComposeResult:
        yield Label(f" {self._commit.short_hash}  {self._commit.message.splitlines()[0][:50]}")
        lv = ListView(id="menu-list")
        for label, _ in self._items:
            lv.append(ListItem(Label(f"  {label}")))
        yield lv

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one("#menu-list", ListView).index
        if idx is None or idx >= len(self._items):
            return
        _, action = self._items[idx]
        self.dismiss()
        self._execute(action)

    def _execute(self, action: str) -> None:
        git = self.app.git
        commit = self._commit
        try:
            if action == "revert":
                git.revert(commit.hash)
                self.app.show_status(f"Reverted {commit.short_hash}")
                self.app.action_refresh()
            elif action == "drop":
                git.drop(commit.hash)
                self.app.show_status(f"Dropped {commit.short_hash}")
                self.app.action_refresh()
            elif action == "squash":
                self.app.push_screen(
                    _SquashMessageModal(commit=commit, git=git, app_ref=self.app)
                )
            elif action == "push":
                git.push()
                self.app.show_status("Pushed to remote successfully.")
                self.app.action_refresh()
            elif action == "cherry_pick":
                git.cherry_pick(commit.hash)
                self.app.show_status(f"Cherry-picked {commit.short_hash}")
                self.app.action_refresh()
            elif action == "copy_hash":
                pyperclip.copy(commit.hash)
                self.app.show_status(f"Copied {commit.hash}")
        except Exception as e:
            error_msg = str(e)
            is_conflict = "conflict" in error_msg.lower() or "cherry-pick" in error_msg.lower()
            abort_fn = None
            if action == "cherry_pick":
                abort_fn = git.abort_cherry_pick
            elif action == "revert":
                abort_fn = git.abort_revert
            self.app.show_error(
                message=error_msg,
                allow_abort=is_conflict and abort_fn is not None,
                abort_fn=abort_fn,
            )


class _SquashMessageModal(ModalScreen):
    """Simple input modal to get the squash commit message."""

    BINDINGS = [("escape", "dismiss", "Cancel")]

    def __init__(self, commit: CommitInfo, git, app_ref) -> None:
        super().__init__()
        self._commit = commit
        self._git = git
        self._app_ref = app_ref

    def compose(self) -> ComposeResult:
        from textual.widgets import Input
        yield Label("Squash message:")
        yield Input(
            value=f"squash: {self._commit.message.splitlines()[0]}",
            id="squash-input",
        )

    def on_input_submitted(self, event) -> None:
        message = event.value.strip()
        if message:
            self.dismiss()
            try:
                self._git.squash(self._commit.hash, message)
                self._app_ref.show_status("Squash complete.")
                self._app_ref.action_refresh()
            except Exception as e:
                self._app_ref.show_error(str(e))
