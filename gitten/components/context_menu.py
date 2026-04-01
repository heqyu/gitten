from __future__ import annotations

from typing import Any

import pyperclip
from textual import work
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import ListView, ListItem, Label, Input, LoadingIndicator

from gitten.git_service import GitService, DirtyWorkdirError, RebaseConflictError
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
        with ListView(id="menu-list"):
            for label, _ in self._items:
                yield ListItem(Label(f"  {label}"))
        yield LoadingIndicator(id="menu-loading")

    def on_mount(self) -> None:
        self.query_one("#menu-loading", LoadingIndicator).display = False

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one("#menu-list", ListView).index
        if idx is None or idx >= len(self._items):
            return
        _, action = self._items[idx]
        if action == "squash":
            # squash needs a message first — open modal synchronously
            self.dismiss()
            git = self.app.git
            commit = self._commit
            self.app.push_screen(
                _SquashMessageModal(commit=commit, git=git, app_ref=self.app)
            )
        elif action == "copy_hash":
            pyperclip.copy(self._commit.hash)
            self.app.show_status(f"Copied {self._commit.hash}")
            self.dismiss()
        else:
            # Run blocking git operations in background thread
            self.query_one("#menu-list", ListView).display = False
            self.query_one("#menu-loading", LoadingIndicator).display = True
            self._run_action(action)

    @work(thread=True)
    def _run_action(self, action: str) -> None:
        git = self.app.git
        commit = self._commit
        try:
            if action == "revert":
                git.revert(commit.hash)
                self.app.call_from_thread(self._on_success, f"Reverted {commit.short_hash}")
            elif action == "drop":
                git.drop(commit.hash)
                self.app.call_from_thread(self._on_success, f"Dropped {commit.short_hash}")
            elif action == "push":
                git.push()
                self.app.call_from_thread(self._on_success, "Pushed to remote successfully.")
            elif action == "cherry_pick":
                git.cherry_pick(commit.hash)
                self.app.call_from_thread(self._on_success, f"Cherry-picked {commit.short_hash}")
        except DirtyWorkdirError as e:
            self.app.call_from_thread(self._on_error, str(e), allow_abort=False, abort_fn=None)
        except RebaseConflictError as e:
            self.app.call_from_thread(
                self._on_error, str(e),
                allow_abort=True,
                abort_fn=git.abort_rebase,
            )
        except Exception as e:
            error_msg = str(e)
            abort_fn = None
            allow_abort = False
            if action == "cherry_pick" and ("conflict" in error_msg.lower() or "cherry-pick" in error_msg.lower()):
                abort_fn = git.abort_cherry_pick
                allow_abort = True
            elif action == "revert" and "conflict" in error_msg.lower():
                abort_fn = git.abort_revert
                allow_abort = True
            self.app.call_from_thread(self._on_error, error_msg, allow_abort=allow_abort, abort_fn=abort_fn)

    def _on_success(self, message: str) -> None:
        self.dismiss()
        self.app.show_status(message)
        self.app.action_refresh()

    def _on_error(self, message: str, allow_abort: bool, abort_fn: Any) -> None:
        self.dismiss()
        self.app.show_error(message=message, allow_abort=allow_abort, abort_fn=abort_fn)


class _SquashMessageModal(ModalScreen):
    """Simple input modal to get the squash commit message."""

    BINDINGS = [("escape", "dismiss", "Cancel")]

    def __init__(self, commit: CommitInfo, git: GitService, app_ref: Any) -> None:
        super().__init__()
        self._commit = commit
        self._git = git
        self._app_ref = app_ref

    def compose(self) -> ComposeResult:
        yield Label("Squash message:")
        yield Input(
            value=f"squash: {self._commit.message.splitlines()[0]}",
            id="squash-input",
        )
        yield LoadingIndicator(id="squash-loading")

    def on_mount(self) -> None:
        self.query_one("#squash-loading", LoadingIndicator).display = False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return
        self.query_one("#squash-input", Input).display = False
        self.query_one("#squash-loading", LoadingIndicator).display = True
        self._run_squash(message)

    @work(thread=True)
    def _run_squash(self, message: str) -> None:
        try:
            self._git.squash(self._commit.hash, message)
            self.app.call_from_thread(self._on_squash_done)
        except DirtyWorkdirError as e:
            self.app.call_from_thread(self._on_squash_error, str(e))
        except Exception as e:
            self.app.call_from_thread(self._on_squash_error, str(e))

    def _on_squash_done(self) -> None:
        self.dismiss()
        self._app_ref.show_status("Squash complete.")
        self._app_ref.action_refresh()

    def _on_squash_error(self, message: str) -> None:
        self.dismiss()
        self._app_ref.show_error(message)
