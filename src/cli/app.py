"""
Main CLI application for Swarm.
"""

import typer
import asyncio
import os
import shutil
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.status import Status
from rich import print as rprint

from ..messaging.db import init_db, close_db, db
from ..roles.registry import role_registry
from ..runtimes.registry import registry

app = typer.Typer(help="Swarm CLI — Orchestrate a fleet of AI coding agents.")
console = Console()


@app.command()
def init():
    """Initialize a new Swarm project in the current directory."""
    rprint("[bold cyan]Initializing Swarm project...[/bold cyan]")
    
    # Create necessary directories
    directories = [".swarm", ".swarm/worktrees", ".polyglot", "src/agents/definitions", "src/roles/contracts"]
    for d in directories:
        os.makedirs(d, exist_ok=True)
        rprint(f"  [dim]Created directory: {d}[/dim]")
    
    # Initialize database
    asyncio.run(init_db())
    rprint("  [dim]Initialized SQLite database[/dim]")
    
    # Template config.yaml if missing
    config_path = Path("config.yaml")
    if not config_path.exists():
        default_config = """# Swarm Configuration
overseer:
  runtime: vibe
  model: mistral-large-latest

roles:
  enabled:
    - scout
    - developer
    - builder
    - tester
    - reviewer
    - merger
    - monitor
"""
        config_path.write_text(default_config)
        rprint("  [dim]Created default config.yaml[/dim]")
    
    rprint("\n[bold green]✅ Swarm project initialized![/bold green]")
    rprint("Run [bold]swarm setup[/bold] to configure your LLM providers.")


@app.command()
def doctor():
    """Run diagnostic checks on your Swarm environment."""
    rprint("[bold cyan]Running Swarm Diagnostic Checks...[/bold cyan]\n")
    
    # 1. Check Core Dependencies
    table = Table(title="System Status")
    table.add_column("Check", style="cyan")
    table.add_column("Result", style="green")
    
    try:
        import textual
        import aiosqlite
        import yaml
        table.add_row("Python Dependencies", "✅ Installed")
    except ImportError as e:
        table.add_row("Python Dependencies", f"❌ Missing: {e}")

    if Path("config.yaml").exists():
        table.add_row("Configuration File", "✅ config.yaml found")
    else:
        table.add_row("Configuration File", "⚠️  config.yaml missing")

    console.print(table)

    # 2. Check Runtimes (Binaries)
    rt_table = Table(title="Runtime Binaries")
    rt_table.add_column("Runtime", style="cyan")
    rt_table.add_column("Binary", style="dim")
    rt_table.add_column("Status")

    runtime_binaries = {
        "claude-code": "claude",
        "vibe": "vibe",
        "codex": "codex",
        "gemini": "gemini",
        "opencode": "opencode",
        "hermes": "hermes",
        "goose": "goose",
        "cline": "cline",
        "qodo": "qodo"
    }

    for rt, bin_name in runtime_binaries.items():
        path = shutil.which(bin_name)
        status = "[green]Ready[/green]" if path else "[red]Missing[/red]"
        rt_table.add_row(rt, bin_name, status)
    
    console.print(rt_table)

    # 3. Check API Keys
    env_table = Table(title="Environment Variables")
    env_table.add_column("Variable", style="cyan")
    env_table.add_column("Status")

    keys = ["ANTHROPIC_API_KEY", "MISTRAL_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]
    for key in keys:
        status = "[green]Set[/green]" if os.environ.get(key) else "[yellow]Not Set[/yellow]"
        env_table.add_row(key, status)
    
    console.print(env_table)


@app.command()
def logs(limit: int = typer.Option(20, help="Number of logs to show")):
    """View recent Swarm events and agent activity."""
    async def _show_logs():
        await init_db()
        events = await db.get_recent_events(limit=limit)
        
        if not events:
            rprint("[yellow]No logs found.[/yellow]")
            await close_db()
            return

        table = Table(title=f"Recent Swarm Logs (Last {limit})")
        table.add_column("Timestamp", style="dim")
        table.add_column("Event", style="bold cyan")
        table.add_column("Agent", style="green")
        table.add_column("Data", style="white")

        for event in reversed(events):
            # (event_type, session_id, agent_name, data, timestamp)
            etype, sid, name, data, ts = event
            table.add_row(str(ts), etype, name or "system", str(data)[:100])
        
        console.print(table)
        await close_db()

    asyncio.run(_show_logs())


@app.command()
def roles():
    """List all available agent roles and their missions."""
    roles = role_registry.list_roles()
    
    table = Table(title="Available Swarm Roles")
    table.add_column("Role", style="bold magenta")
    table.add_column("Mission", style="cyan")
    
    for role in roles:
        # In a real app, we'd pull the mission from the contract or definition
        table.add_row(role, f"Mission for {role}")
    
    console.print(table)


@app.command()
def runtimes():
    """List all supported agent runtimes and their current status."""
    available = registry.list_available()
    
    table = Table(title="Supported Runtimes")
    table.add_column("Runtime", style="bold cyan")
    table.add_column("Status", style="green")
    table.add_column("Binary", style="dim")

    runtime_binaries = {
        "claude-code": "claude",
        "vibe": "vibe",
        "codex": "codex",
        "gemini": "gemini",
        "opencode": "opencode",
        "hermes": "hermes",
        "echo": "N/A",
        "goose": "goose",
        "cline": "cline",
        "qodo": "qodo",
        "openclaw": "openclaw"
    }

    for rt in sorted(runtime_binaries.keys()):
        bin_name = runtime_binaries.get(rt, "unknown")
        installed = shutil.which(bin_name) if bin_name != "N/A" else True
        status = "[green]Ready[/green]" if installed else "[red]Missing Binary[/red]"
        rt_table_name = f"[bold white]{rt}[/bold white]" if rt in available else rt
        table.add_row(rt_table_name, status, bin_name)
    
    console.print(table)


@app.command()
def tui():
    """Launch the Swarm Textual User Interface (TUI)."""
    from ..tui.app import SwarmApp
    
    rprint("[bold cyan]Launching Swarm TUI...[/bold cyan]")
    app = SwarmApp()
    app.run()


@app.command()
def cleanup():
    """Clean up active worktrees and temporary files."""
    from ..worktree.manager import worktree_manager
    
    worktrees = worktree_manager.list_worktrees()
    if not worktrees:
        rprint("[yellow]No worktrees to clean up.[/yellow]")
        return
        
    rprint(f"[bold yellow]Found {len(worktrees)} active worktrees.[/bold yellow]")
    if typer.confirm("Are you sure you want to remove all Swarm worktrees?"):
        with Status("Cleaning up...", console=console):
            worktree_manager.cleanup_all()
        rprint("[bold green]✅ All worktrees cleaned up.[/bold green]")


@app.command()
def setup():
    """Run the interactive model and provider setup wizard."""
    from .setup import run_setup
    run_setup()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development")
):
    """Launch the Swarm REST API and Control Plane server."""
    rprint(f"[bold cyan]Starting Swarm API server on {host}:{port}...[/bold cyan]")
    rprint("[dim]Visit http://localhost:8000/dashboard for the UI[/dim]")
    
    import uvicorn
    # Need to pass import string for reload to work
    uvicorn.run("src.api.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
