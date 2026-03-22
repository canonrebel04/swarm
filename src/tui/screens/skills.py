"""
Skill Browser Modal Screen
Modal dialog for browsing available agent skills.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import (
    Static, ListView, ListItem, Label,
    TabbedContent, TabPane, Markdown, Button
)
from textual.containers import Vertical, Horizontal
from rich.syntax import Syntax
from ...skills.registry import skill_registry


class SkillBrowserModal(ModalScreen[None]):
    """Modal dialog for browsing available agent skills."""
    
    CSS = """
        SkillBrowserModal {
            align: center middle;
        }

        #skill-container {
            width: 90%;
            height: 90%;
            background: $surface;
            border: thick $primary;
            padding: 1;
        }
        
        #skill-title {
            width: 100%;
            text-align: center;
            text-style: bold;
            color: $accent;
            margin-bottom: 1;
        }
        
        #skill-layout {
            layout: horizontal;
            height: 1fr;
        }

        #skill-list {
            width: 30;
            height: 100%;
            border: solid $primary 10%;
            background: $surface-darken-1;
        }

        #skill-details {
            width: 1fr;
            height: 100%;
            padding-left: 1;
        }

        TabbedContent {
            height: 1fr;
        }

        .yaml-view {
            width: 100%;
            height: 100%;
            overflow-y: auto;
            background: $surface-darken-1;
            padding: 1;
        }

        #skill-footer {
            height: 3;
            align: center middle;
            margin-top: 1;
        }
    """
    
    def __init__(self):
        super().__init__()
        self._skills = skill_registry.get_all_skills()
        self._selected_skill = self._skills[0] if self._skills else None

    def compose(self) -> ComposeResult:
        with Vertical(id="skill-container"):
            yield Static("🛠  SWARM SKILL BROWSER", id="skill-title")
            
            with Horizontal(id="skill-layout"):
                # Left side: Skill list
                skill_items = []
                for s in self._skills:
                    item = ListItem(Static(f" {s.name}"))
                    item.data = s
                    skill_items.append(item)
                
                yield ListView(*skill_items, id="skill-list")
                
                # Right side: Details
                with Vertical(id="skill-details"):
                    with TabbedContent(id="skill-tabs"):
                        with TabPane("Mission & Guidelines", id="md-tab"):
                            yield Markdown(id="skill-md")
                        with TabPane("Configuration (YAML)", id="yaml-tab"):
                            yield Static(id="skill-yaml", classes="yaml-view")
            
            with Horizontal(id="skill-footer"):
                yield Button("Close (Esc)", id="btn-close", variant="primary")

    def on_mount(self) -> None:
        if self._selected_skill:
            self._update_details(self._selected_skill)
        self.query_one("#skill-list").focus()

    def _update_details(self, skill) -> None:
        # Update Markdown
        md_widget = self.query_one("#skill-md", Markdown)
        md_widget.update(skill.instructions or f"# {skill.name}\n\n{skill.description}")
        
        # Update YAML (simulated from definition)
        yaml_data = {
            "name": skill.name,
            "description": skill.description,
            "version": skill.version,
            "may": skill.allowed_tools,
            "may_not": skill.blocked_tools,
            "metadata": skill.metadata
        }
        yaml_str = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)
        yaml_syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=True)
        
        yaml_widget = self.query_one("#skill-yaml", Static)
        yaml_widget.update(yaml_syntax)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and hasattr(event.item, "data"):
            self._selected_skill = event.item.data
            self._update_details(self._selected_skill)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()

    def on_key(self, event: str) -> None:
        self.dismiss()
