"""
TUI Command
CLI command to launch the Textual user interface
"""

import typer
from ...tui.app import PolyglotSwarmApp


tui_app = typer.Typer(name="tui", help="Launch the PolyglotSwarm TUI")


@tui_app.command("launch")
def launch_tui():
    """Launch the PolyglotSwarm Textual user interface"""
    typer.echo("Launching PolyglotSwarm TUI...")
    app = PolyglotSwarmApp()
    app.run()


def get_tui_app():
    """Get the TUI command group"""
    return tui_app