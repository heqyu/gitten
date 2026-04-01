from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Static


HELP_TEXT = """
 gitten — keyboard shortcuts

  Navigation
  ──────────────────────────────────────
  ↑ / k          Move up
  ↓ / j          Move down
  Enter          Open diff (in file list)
  [              Toggle left panel

  Actions
  ──────────────────────────────────────
  m / right-click  Open context menu
  c                Copy commit log
  r                Refresh
  q                Quit
  ?                This help screen
  Esc              Close modal

  Context menu operations
  ──────────────────────────────────────
  Revert           Create reverse commit
  Drop             Delete unpushed commit
  Squash           Merge all unpushed into one
  Push to remote   Push current branch
  Cherry-pick      Apply commit to current branch
  Copy hash        Copy commit SHA
"""


class HelpModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close"), ("question_mark", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        yield Static(HELP_TEXT, id="help-body")
        yield Button("Close  [Esc]", id="help-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()
