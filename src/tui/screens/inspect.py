"""
Inspect Modal Screen
Modal dialog for inspecting agent roles and contracts with a tabbed interface.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import (
    Label, Markdown, TabbedContent, TabPane,
    Static, Button
)
from textual.containers import Vertical, Horizontal
from rich.syntax import Syntax


class InspectModal(ModalScreen[None]):
    """Modal dialog for inspecting agent roles and contracts."""
    
    CSS = """
        InspectModal {
            align: center middle;
        }

        #inspect-container {
            width: 85%;
            height: 85%;
            background: $surface;
            border: thick $primary;
            padding: 1;
        }
        
        #inspect-title {
            width: 100%;
            text-align: center;
            text-style: bold;
            color: $accent;
            margin-bottom: 1;
        }
        
        TabbedContent {
            height: 1fr;
        }

        TabPane {
            padding: 1;
        }

        .yaml-view {
            width: 100%;
            height: 100%;
            overflow-y: auto;
            background: $surface-darken-1;
            padding: 1;
        }

        #inspect-footer {
            height: 3;
            align: center middle;
            margin-top: 1;
        }

        #btn-close {
            background: $primary;
        }
    """
    
    def __init__(self, agent_name: str, role: str, yaml_content: str, md_content: str):
        super().__init__()
        self.agent_name = agent_name
        self.role = role
        self.yaml_content = yaml_content
        self.md_content = md_content
    
    def compose(self) -> ComposeResult:
        with Vertical(id="inspect-container"):
            yield Static(f"🔍 INSPECTING: {self.agent_name} [{self.role}]", id="inspect-title")
            
            with TabbedContent():
                with TabPane("Contract (YAML)", id="yaml-tab"):
                    # Use syntax highlighting for YAML
                    yaml_syntax = Syntax(
                        self.yaml_content, 
                        "yaml", 
                        theme="monokai", 
                        line_numbers=True,
                        word_wrap=True
                    )
                    yield Static(yaml_syntax, classes="yaml-view")
                
                with TabPane("Identity (Markdown)", id="md-tab"):
                    yield Markdown(self.md_content)
            
            with Horizontal(id="inspect-footer"):
                yield Button("Close (Esc)", id="btn-close", variant="primary")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()

    def on_key(self, event: str) -> None:
        """Close modal on any key press."""
        # Note: In recent Textual, Escape usually works by default or needs explicit binding
        # We'll allow any key to dismiss for maximum convenience as before
        self.dismiss()
