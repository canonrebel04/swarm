"""
Overseer — LLM-backed goal decomposition.

The Overseer is the "brain" of the Swarm. It takes a high-level objective
from the user and decomposes it into a directed acyclic graph (DAG) of
TaskPackets that the Coordinator can dispatch to the agent fleet.

When no LLM runtime is available, the Overseer falls back to a rule-based
heuristic decomposition so the system remains functional.
"""

from __future__ import annotations
import json
import asyncio
import os
import shutil
from typing import List, Optional
from dataclasses import dataclass

from ..messaging.event_bus import event_bus

OVERSEER_SYSTEM_PROMPT = """\
You are the Overseer of a multi-agent coding system called Swarm.

Your job is to decompose a high-level objective into a list of tasks.
Each task must specify:
- title: short descriptive title
- description: what the agent should do (be specific and actionable)
- role: one of [scout, developer, builder, tester, reviewer, merger]
- runtime: one of [claude-code, codex, gemini, vibe, opencode, hermes, echo]
- priority: high | medium | low
- depends_on: list of task titles this task depends on (empty list if independent)
- files_in_scope: list of file paths this task may touch (empty if unknown)

Rules:
1. ALWAYS start with a scout task to explore the codebase.
2. Implementation tasks should depend on the scout task.
3. Testing tasks should depend on implementation tasks.
4. Review should happen after implementation.
5. Keep tasks small and atomic — each task should be completable by one agent.
6. Return ONLY a JSON array of task objects, no other text.

Example output:
[
  {
    "title": "Scout codebase for auth module",
    "description": "Explore the src/auth/ directory and related tests to understand the current authentication architecture.",
    "role": "scout",
    "runtime": "gemini",
    "priority": "medium",
    "depends_on": [],
    "files_in_scope": ["src/auth/"]
  },
  {
    "title": "Implement OAuth2 support",
    "description": "Add OAuth2 authentication flow to the existing auth module. Create src/auth/oauth2.py with the provider integration.",
    "role": "developer",
    "runtime": "claude-code",
    "priority": "high",
    "depends_on": ["Scout codebase for auth module"],
    "files_in_scope": ["src/auth/oauth2.py", "src/auth/__init__.py"]
  }
]
"""


class Overseer:
    """
    LLM-backed goal decomposer.

    Falls back to heuristic decomposition when no LLM is configured.
    """

    def __init__(self, runtime_name: str = "vibe", model: str = "mistral-large-latest"):
        self.runtime_name = runtime_name
        self.model = model
        self._llm_available = self._check_llm_availability()

    def _check_llm_availability(self) -> bool:
        """Check if the configured runtime binary is available."""
        binary_map = {
            "claude-code": "claude",
            "codex": "codex",
            "gemini": "gemini",
            "vibe": "vibe",
            "opencode": "opencode",
            "hermes": "hermes",
        }
        binary = binary_map.get(self.runtime_name, self.runtime_name)
        return shutil.which(binary) is not None

    async def decompose(self, objective: str) -> List[dict]:
        """
        Decompose a high-level objective into task dictionaries.

        Returns a list of dicts compatible with TaskPacket construction.
        """
        if self._llm_available:
            try:
                tasks = await self._llm_decompose(objective)
                if tasks:
                    await event_bus.emit(
                        "info",
                        "overseer",
                        {"message": f"LLM decomposition produced {len(tasks)} tasks"},
                    )
                    return tasks
            except Exception as e:
                await event_bus.emit(
                    "warning",
                    "overseer",
                    {
                        "message": f"LLM decomposition failed ({e}), falling back to heuristic"
                    },
                )

        return self._heuristic_decompose(objective)

    async def _llm_decompose(self, objective: str) -> List[dict]:
        """Call the configured LLM runtime to decompose the objective."""
        prompt = f"Objective: {objective}\n\nDecompose this into a JSON array of tasks."

        if self.runtime_name == "claude-code":
            return await self._call_claude(prompt)
        elif self.runtime_name == "vibe":
            return await self._call_cli("vibe", ["-p", prompt, "-m", self.model])
        elif self.runtime_name == "codex":
            return await self._call_cli("codex", ["exec", prompt])
        elif self.runtime_name == "gemini":
            return await self._call_cli("gemini", ["-p", prompt])
        else:
            return await self._call_cli(self.runtime_name, [prompt])

    async def _call_claude(self, prompt: str) -> List[dict]:
        """Call Claude Code CLI."""
        cmd = [
            "claude",
            "--print",
            "--system-prompt",
            OVERSEER_SYSTEM_PROMPT,
            "--model",
            self.model or "sonnet",
            prompt,
        ]
        return await self._run_and_parse(cmd)

    async def _call_cli(self, binary: str, args: List[str]) -> List[dict]:
        """Generic CLI call."""
        cmd = [binary] + args
        return await self._run_and_parse(cmd)

    async def _run_and_parse(self, cmd: List[str]) -> List[dict]:
        """Run a CLI command and parse the JSON task array from output."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        output = stdout.decode(errors="replace").strip()
        if not output:
            return []

        # Try to extract JSON array from output
        return self._extract_task_list(output)

    def _extract_task_list(self, output: str) -> List[dict]:
        """Extract a JSON array of task dicts from LLM output."""
        # Try last line first
        for line in reversed(output.splitlines()):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    tasks = json.loads(stripped)
                    if isinstance(tasks, list) and tasks:
                        return tasks
                except json.JSONDecodeError:
                    continue

        # Try to find array in code fence
        import re

        match = re.search(r"```(?:json)?\s*\n(\[.*?\])\s*```", output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        return []

    def _heuristic_decompose(self, objective: str) -> List[dict]:
        """
        Rule-based decomposition fallback.

        Creates a scout → developer → tester pipeline.
        """
        return [
            {
                "title": "Scout codebase",
                "description": f"Explore the codebase to understand the current state relevant to: {objective}",
                "role": "scout",
                "runtime": "gemini",
                "priority": "medium",
                "depends_on": [],
                "files_in_scope": [],
            },
            {
                "title": "Implement changes",
                "description": f"Implement the changes required for: {objective}",
                "role": "developer",
                "runtime": "claude-code",
                "priority": "high",
                "depends_on": ["Scout codebase"],
                "files_in_scope": [],
            },
            {
                "title": "Test implementation",
                "description": f"Run tests and validate the implementation of: {objective}",
                "role": "tester",
                "runtime": "gemini",
                "priority": "medium",
                "depends_on": ["Implement changes"],
                "files_in_scope": [],
            },
        ]


def create_overseer(config: Optional[dict] = None) -> Overseer:
    """
    Factory function to create an Overseer from config.yaml settings.

    Args:
        config: Optional config dict. If None, reads from config.yaml.
    """
    if config is None:
        config = _read_config()

    overseer_cfg = config.get("overseer", {})
    return Overseer(
        runtime_name=overseer_cfg.get("runtime", "vibe"),
        model=overseer_cfg.get("model", "mistral-large-latest"),
    )


def _read_config() -> dict:
    """Read config.yaml if it exists."""
    try:
        import yaml

        config_path = os.path.join(os.getcwd(), "config.yaml")
        if os.path.exists(config_path):
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}
