"""
Confirm Modal Screen
Modal dialog for confirming actions like kill, retry, etc.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmModal(ModalScreen[str]):
    """Modal dialog for confirming actions."""

    CSS = """
        ConfirmModal > Vertical {
            align: center middle;
            width: 60%;
            height: auto;
            max-width: 80;
            background: $surface;
            border: round $primary;
            padding: 1 2;
        }
        
        ConfirmModal Label {
            margin-bottom: 1;
            width: 100%;
            text-align: center;
        }
        
        ConfirmModal Horizontal {
            width: 100%;
            justify: center;
            margin-top: 1;
        }
        
        ConfirmModal Button {
            width: 12;
            margin: 0 1;
        }
        
        #yes-button {
            background: $error;
        }
        
        #no-button {
            background: $primary;
        }
    """

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.message)
            with Horizontal():
                yield Button("Yes", id="yes-button", variant="error")
                yield Button("No", id="no-button", variant="primary")

    def on_mount(self) -> None:
        """Focus the safe 'No' button by default to prevent accidental deletions."""
        try:
            self.query_one("#no-button").focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes-button":
            self.dismiss("yes")
        else:
            self.dismiss("no")
