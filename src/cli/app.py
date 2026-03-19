"""
Main CLI application for PolyglotSwarm.
"""

import typer
from typing import Optional
from ..messaging.db import init_db, close_db
import asyncio

app = typer.Typer()


@app.command()
def init():
    """Initialize a new swarm project."""
    typer.echo("Initializing PolyglotSwarm project...")
    # Create necessary directories
    import os
    os.makedirs(".swarm", exist_ok=True)
    os.makedirs(".swarm/worktrees", exist_ok=True)
    
    # Initialize database
    asyncio.run(init_db())
    
    typer.echo("✅ PolyglotSwarm project initialized!")


@app.command()
def run(
    task: Optional[str] = typer.Argument(None, help="Task to execute"),
    runtime: Optional[str] = typer.Option(None, help="Runtime to use")
):
    """Run the swarm with a specific task."""
    if not task:
        task = typer.prompt("Enter the task to execute")
    
    typer.echo(f"Running swarm with task: {task}")
    if runtime:
        typer.echo(f"Using runtime: {runtime}")
    
    # TODO: Implement actual swarm execution
    typer.echo("⚠️  Swarm execution not yet implemented")


@app.command()
def status():
    """Show current swarm status."""
    typer.echo("Current swarm status:")
    typer.echo("- Agents: 0 active")
    typer.echo("- Tasks: 0 queued")
    typer.echo("- Worktrees: 0 active")
    
    # TODO: Implement actual status reporting
    typer.echo("⚠️  Status reporting not yet fully implemented")


@app.command()
def stop():
    """Stop all running agents."""
    typer.echo("Stopping all agents...")
    # TODO: Implement agent stopping logic
    typer.echo("✅ All agents stopped (implementation pending)")


@app.command()
def doctor():
    """Run diagnostic checks."""
    import typer as typer_module
    
    typer_module.echo("Running diagnostic checks...")
    
    # Check dependencies
    try:
        import textual
        import aiosqlite
        typer_module.echo("✅ All core dependencies installed")
    except ImportError as e:
        typer_module.echo(f"❌ Missing dependency: {e}")
        return
    
    # Check configuration
    import os
    if os.path.exists("config.yaml"):
        typer_module.echo("✅ Configuration file found")
    else:
        typer_module.echo("⚠️  Configuration file not found")
    
    # Check agent definitions
    if os.path.exists("src/agents/definitions"):
        definitions = os.listdir("src/agents/definitions")
        typer_module.echo(f"✅ Found {len(definitions)} agent definitions")
    else:
        typer_module.echo("❌ Agent definitions directory not found")


@app.command()
def cleanup():
    """Clean up worktrees and temporary files."""
    from ..worktree.manager import worktree_manager
    
    typer.echo("Cleaning up worktrees...")
    worktrees = worktree_manager.list_worktrees()
    if worktrees:
        typer.echo(f"Found {len(worktrees)} worktrees")
        if typer.confirm("Remove all worktrees?"):
            worktree_manager.cleanup_all()
            typer.echo("✅ All worktrees cleaned up")
    else:
        typer.echo("No worktrees to clean up")


@app.command()
def roles():
    """List available agent roles."""
    from ..roles.registry import role_registry
    
    roles = role_registry.list_roles()
    if roles:
        typer.echo("Available roles:")
        for role in roles:
            typer.echo(f"  - {role}")
    else:
        typer.echo("No roles available")


@app.command()
def runtimes():
    """List available runtimes."""
    from ..runtimes.registry import registry
    
    runtimes = registry.list_available()
    if runtimes:
        typer.echo("Available runtimes:")
        for runtime in runtimes:
            typer.echo(f"  - {runtime}")
    else:
        typer.echo("No runtimes available")


@app.command()
def tui():
    """Launch the PolyglotSwarm Textual user interface."""
    from ..tui.app import PolyglotSwarmApp
    
    typer.echo("Launching PolyglotSwarm TUI...")
    app = PolyglotSwarmApp()
    app.run()


if __name__ == "__main__":
    app()