from __future__ import annotations

from typing import Callable, Optional

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Button, Static
from textual.containers import Vertical


class ErrorModal(ModalScreen):
    """Shows git error output with optional Abort button."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(
        self,
        message: str,
        allow_abort: bool = False,
        abort_fn: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__()
        self._message = message
        self._allow_abort = allow_abort
        self._abort_fn = abort_fn

    def compose(self) -> ComposeResult:
        with Vertical(id="error-container"):
            yield Label(" Error", id="error-title")
            yield Static(self._message, id="error-body")
            if self._allow_abort:
                yield Button("Abort operation", id="abort-btn", variant="error")
            yield Button("Close", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "abort-btn" and self._abort_fn:
            try:
                self._abort_fn()
                self.app.show_status("Operation aborted.")
            except Exception:
                pass  # abort itself failed — nothing more we can do
        self.dismiss()
