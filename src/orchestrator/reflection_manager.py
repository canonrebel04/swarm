"""
Reflection manager for meta-learning and self-improvement.
"""

import asyncio
import json
from typing import List, Optional
from ..messaging.db import db
from ..runtimes.base import AgentConfig
from .agent_manager import agent_manager


class ReflectionManager:
    """Manages the reflection cycle to synthesize lessons from past failures."""

    def __init__(self, coordinator=None):
        self.coordinator = coordinator

    async def run_reflection(self, role: Optional[str] = None) -> int:
        """
        Run a reflection session to synthesize lessons.
        Returns the number of new lessons learned.
        """
        # 1. Fetch recent critiques that haven't been reflected upon yet
        critiques = await db.get_recent_critiques(role=role, limit=20)
        if not critiques:
            return 0

        # 2. Format critiques for the reflection agent
        formatted_history = "\n".join([
            f"- Role: {r}, Task: {t}, Status: {s}\n  Critique: {c}"
            for r, t, s, c in critiques
        ])

        # 3. Spawn reflection agent
        config = AgentConfig(
            name="reflection-agent",
            role="reflection",
            task=f"Analyze the following recent critiques and synthesize actionable lessons learned:\n\n{formatted_history}",
            worktree_path=".swarm/worktrees",
            model="default", # Ideally a high-reasoning model
            runtime="vibe",  # Default to vibe for fast execution
            system_prompt_path="src/agents/definitions/reflection.md",
            read_only=True
        )

        session_id = await agent_manager.spawn_agent(config)
        
        # 4. Wait for agent to finish and capture output
        # In a real MAS, we'd use events. For this implementation, we'll poll or wait.
        output = ""
        while True:
            status = await agent_manager.get_agent_status(session_id)
            if status.state in ["done", "error"]:
                output = status.last_output
                break
            await asyncio.sleep(1.0)

        if status.state == "error":
            return 0

        # 5. Parse lessons from output
        lessons = self._parse_lessons(output)
        
        # 6. Store lessons in DB
        for lesson_data in lessons:
            target_role = lesson_data.get("role")
            lesson_text = lesson_data.get("lesson")
            if target_role and lesson_text:
                await db.add_experience_log(
                    role=target_role,
                    task_title="Reflection Synthesis",
                    status="learned",
                    lessons_learned=lesson_text
                )

        await agent_manager.kill_agent(session_id)
        return len(lessons)

    def _parse_lessons(self, output: str) -> List[dict]:
        """Extract JSON lessons from agent output."""
        try:
            # Look for JSON array in output
            start = output.find("[")
            end = output.rfind("]") + 1
            if start != -1 and end > start:
                return json.loads(output[start:end])
        except Exception:
            pass
        return []


# Global instance
reflection_manager = ReflectionManager()
