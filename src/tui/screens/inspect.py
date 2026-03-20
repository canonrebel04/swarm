"""
Inspect Modal Screen
Modal dialog for inspecting agent roles and contracts.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Markdown
from textual.containers import Vertical


class InspectModal(ModalScreen[None]):
    """Modal dialog for inspecting agent roles and contracts."""
    
    CSS = """
        InspectModal > Vertical {
            align: center middle;
            width: 80%;
            height: 80%;
            background: $surface;
            border: round $primary;
            padding: 1 2;
        }
        
        InspectModal Label {
            margin-bottom: 1;
            width: 100%;
            text-align: center;
            color: $text;
        }
        
        InspectModal Markdown {
            width: 100%;
            height: 100%;
            overflow-y: auto;
            background: $surface-darken-1;
            border: round $primary 10%;
            padding: 1;
        }
    """
    
    def __init__(self, agent_name: str, role: str, contract_md: str):
        super().__init__()
        self.agent_name = agent_name
        self.role = role
        self.contract_md = contract_md
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"🔍 Inspecting {self.agent_name} ({self.role})")
            yield Markdown(self.contract_md)
    
    def on_key(self, event: str) -> None:
        """Close modal on any key press."""
        self.dismiss()