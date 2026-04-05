"""
Runtime verification utilities for Swarm.

Checks binary presence, connectivity, and API keys for each registered runtime.
Provides actionable installation hints for missing dependencies.
"""

import shutil
import os
import sys
import subprocess
import asyncio
import aiohttp
from typing import Optional, Dict, Any

from src.runtimes.registry import registry


# Mapping from runtime name to binary name (if applicable)
RUNTIME_BINARIES: Dict[str, Optional[str]] = {
    "claude-code": "claude",
    "vibe": "vibe",
    "codex": "codex",
    "gemini": "gemini",
    "opencode": "opencode",
    "hermes": "hermes",
    "goose": "goose",
    "cline": "cline",
    "qodo": "qodo",
    "openclaw": "openclaw",
    "ssh": "ssh",  # OpenSSH client
    "docker": "docker",
    "echo": None,  # Built-in, no binary
    "openai": None,  # HTTP-based, no binary
    "openai-compatible": None,  # HTTP-based, no binary
}

# Installation hints for missing binaries
INSTALL_HINTS: Dict[str, str] = {
    "claude": "Install Claude Code CLI: https://claude-code.com/install",
    "vibe": "Install Mistral Vibe CLI: https://github.com/mistralai/vibe",
    "codex": "Install Codex CLI: https://github.com/opencode-co/codex",
    "gemini": "Install Gemini CLI: https://geminicli.com/install",
    "opencode": "Install OpenCode CLI: https://github.com/opencode-co/opencode",
    "hermes": "Install Hermes CLI: https://github.com/opencode-co/hermes",
    "goose": "Install Goose CLI: https://github.com/opencode-co/goose",
    "cline": "Install Cline CLI: https://github.com/opencode-co/cline",
    "qodo": "Install Qodo CLI: https://github.com/opencode-co/qodo",
    "openclaw": "Install OpenClaw CLI: https://github.com/opencode-co/openclaw",
    "ssh": "Install OpenSSH client (usually pre-installed)",
    "docker": "Install Docker Engine: https://docs.docker.com/engine/install/",
}


async def check_runtime(runtime_name: str) -> Dict[str, Any]:
    """
    Check a single runtime's availability and connectivity.
    
    Returns a dict with keys:
      - runtime: runtime name
      - binary_installed: bool
      - binary_path: Optional[str]
      - install_hint: Optional[str]
      - connectivity: "unknown", "reachable", "unreachable", "skipped"
      - error: Optional[str]
    """
    result: Dict[str, Any] = {
        "runtime": runtime_name,
        "binary_installed": False,
        "binary_path": None,
        "install_hint": None,
        "connectivity": "unknown",
        "error": None,
    }
    
    # 1. Check binary presence
    binary = RUNTIME_BINARIES.get(runtime_name)
    if binary is None:
        # No binary required (echo, openai, openai-compatible)
        result["binary_installed"] = True
        result["connectivity"] = "skipped"
    else:
        path = shutil.which(binary)
        if path:
            result["binary_installed"] = True
            result["binary_path"] = path
        else:
            result["binary_installed"] = False
            result["install_hint"] = INSTALL_HINTS.get(binary)
            result["connectivity"] = "unreachable"  # can't connect without binary
            return result
    
    # 2. Check connectivity (for runtimes that have a binary and support it)
    # For now, we only check openai-compatible connectivity via HTTP.
    # Other runtimes require actual CLI execution which may be heavy;
    # we'll do a simple version check or ping if possible.
    if runtime_name == "openai-compatible":
        # Check that we can at least import aiohttp (already done)
        # No endpoint to test without configuration; we'll skip connectivity check
        result["connectivity"] = "skipped"
    elif runtime_name == "openai":
        # OpenAI runtime doesn't have a built-in connectivity test,
        # unless extra_env provides OPENAI_BASE_URL and OPENAI_API_KEY.
        base_url = os.environ.get("OPENAI_BASE_URL")
        api_key = os.environ.get("OPENAI_API_KEY")

        if base_url and api_key:
            try:
                headers = {"Authorization": f"Bearer {api_key}"}
                endpoint = f"{base_url.rstrip('/')}/models"
                timeout = aiohttp.ClientTimeout(total=5.0)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(endpoint, headers=headers) as response:
                        if response.status == 200:
                            result["connectivity"] = "reachable"
                        else:
                            result["connectivity"] = "unreachable"
                            result["error"] = f"HTTP {response.status}"
            except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                result["connectivity"] = "unreachable"
                result["error"] = str(e)
        else:
            result["connectivity"] = "skipped"
    elif runtime_name == "echo":
        result["connectivity"] = "reachable"  # always works
    elif binary and result["binary_installed"]:
        # Try to run a simple version check
        try:
            # Use a timeout to avoid hanging
            proc = await asyncio.create_subprocess_exec(
                binary, "--version" if runtime_name != "docker" else "version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                result["connectivity"] = "reachable"
            else:
                result["connectivity"] = "unreachable"
                result["error"] = f"Binary returned non-zero exit code: {proc.returncode}"
        except (asyncio.TimeoutError, subprocess.SubprocessError, OSError) as e:
            result["connectivity"] = "unreachable"
            result["error"] = str(e)
    else:
        result["connectivity"] = "skipped"
    
    return result


async def verify_all_runtimes() -> Dict[str, Dict[str, Any]]:
    """Run verification for all registered runtimes."""
    runtime_names = registry.list_available()
    results = {}
    for name in runtime_names:
        try:
            # Timeout each runtime check to avoid hanging
            results[name] = await asyncio.wait_for(check_runtime(name), timeout=10.0)
        except asyncio.TimeoutError:
            results[name] = {
                "runtime": name,
                "binary_installed": False,
                "binary_path": None,
                "install_hint": None,
                "connectivity": "unreachable",
                "error": "Timeout checking runtime",
            }
    return results


def format_verification_table(results: Dict[str, Dict[str, Any]]) -> str:
    """Format verification results as a rich table (plain text for now)."""
    lines = []
    lines.append("Runtime Verification Results")
    lines.append("=" * 50)
    lines.append(f"{'Runtime':<20} {'Binary':<10} {'Connectivity':<15} {'Status':<10}")
    lines.append("-" * 50)
    
    for runtime, data in sorted(results.items()):
        binary_status = "✅" if data["binary_installed"] else "❌"
        conn = data["connectivity"]
        if conn == "reachable":
            conn_icon = "✅"
        elif conn == "unreachable":
            conn_icon = "❌"
        else:
            conn_icon = "⏭️"
        status = "Ready" if data["binary_installed"] and conn != "unreachable" else "Issues"
        lines.append(f"{runtime:<20} {binary_status:<10} {conn_icon} {conn:<12} {status:<10}")
    
    lines.append("")
    # Add hints for missing binaries
    missing = [(rt, data) for rt, data in results.items() 
               if not data["binary_installed"] and data["install_hint"]]
    if missing:
        lines.append("Installation hints for missing binaries:")
        for rt, data in missing:
            lines.append(f"  • {rt}: {data['install_hint']}")
    
    return "\n".join(lines)


async def verify_and_print() -> None:
    """Run verification and print formatted results."""
    print("[DEBUG] Starting verification...", file=sys.stderr)
    results = await verify_all_runtimes()
    print("[DEBUG] Verification complete.", file=sys.stderr)
    print(format_verification_table(results))


if __name__ == "__main__":
    try:
        asyncio.run(verify_and_print())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)