"""
Runtime registry for managing available agent runtimes.
"""

from typing import Dict, Type
from .base import AgentRuntime


class RuntimeRegistry:
    """Registry for managing available agent runtimes."""

    def __init__(self):
        self._runtimes: Dict[str, Type[AgentRuntime]] = {}

    def register(self, runtime_class: Type[AgentRuntime]) -> None:
        """Register a new runtime class."""
        runtime_name = runtime_class().runtime_name
        self._runtimes[runtime_name] = runtime_class

    def get(self, runtime_name: str) -> Type[AgentRuntime]:
        """Get a runtime class by name."""
        return self._runtimes.get(runtime_name)

    def list_available(self) -> list[str]:
        """List all available runtime names."""
        return list(self._runtimes.keys())

    def has_runtime(self, runtime_name: str) -> bool:
        """Check if a runtime is available."""
        return runtime_name in self._runtimes

    def list_runtimes(self) -> list[str]:
        """List all available runtime names."""
        return list(self._runtimes.keys())

    def list_roles(self) -> list[str]:
        """List all available role names from runtimes."""
        # This is a simple implementation - in a real system, roles would come from a role registry
        # For now, return some common roles
        return ["scout", "builder", "developer", "tester"]


# Global registry instance
registry = RuntimeRegistry()

# Auto-register runtimes on import
from .echo import EchoRuntime
from .claude_code import ClaudeCodeRuntime
from .vibe import VibeRuntime
from .codex import CodexRuntime
from .gemini import GeminiRuntime
from .hermes import HermesRuntime
from .opencode import OpenCodeRuntime
from .openclaw import OpenClawRuntime

registry.register(EchoRuntime)
registry.register(ClaudeCodeRuntime)
registry.register(VibeRuntime)
registry.register(CodexRuntime)
registry.register(GeminiRuntime)
registry.register(HermesRuntime)
registry.register(OpenCodeRuntime)
registry.register(OpenClawRuntime)