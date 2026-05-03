"""
Coordinator for decomposing tasks and assigning agents.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..roles.prompts import ROLE_READ_ONLY, ROLE_TOOL_POLICY
from ..roles.registry import role_registry
from ..runtimes.base import AgentConfig, AgentStatus
from .agent_manager import agent_manager


@dataclass
class TaskPacket:
    """A task to be assigned to an agent."""

    id: str
    title: str
    description: str
    role_required: str
    runtime_preference: List[str]
    priority: str = "medium"
    status: str = "pending"  # pending, blocked, ready, active, completed, failed
    potential_conflict: bool = False
    conflict_details: str = ""
    files_in_scope: List[str] = field(default_factory=list)
    acceptance_criteria: Optional[List[str]] = None
    parent_agent: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)


class Coordinator:
    """Coordinate task decomposition and agent assignment."""

    def __init__(self):
        self._active_tasks: Dict[str, TaskPacket] = {}
        self._task_queue: List[TaskPacket] = []
        self._task_history: List[TaskPacket] = []
        self._push_event_callback = None
        self._role_priority = {
            "scout": 1,  # First to explore
            "developer": 2,  # Complex implementation
            "builder": 3,  # Straightforward tasks
            "tester": 4,  # Validation
            "reviewer": 5,  # Final review
            "merger": 6,  # Merge resolution
        }
        # Use centralized policies from src/roles/prompts.py
        self._role_tool_policy = ROLE_TOOL_POLICY
        self._role_read_only = ROLE_READ_ONLY
        self._on_task_assigned_callbacks = []
        self._on_handoff_callbacks = []
        self._merge_manager = None  # Will be initialized when coordinator is ready

    def register_task_assigned_callback(self, callback):
        """Register a callback to be called when a task is assigned."""
        self._on_task_assigned_callbacks.append(callback)

    def register_handoff_callback(self, callback):
        """Register a callback to be called when a handoff is triggered."""
        self._on_handoff_callbacks.append(callback)

    def register_event_callback(self, callback):
        """Register a callback for system events."""
        self._push_event_callback = callback

    async def decompose_goal(self, objective: str) -> List[TaskPacket]:
        """
        Use the Overseer to decompose a high-level goal into tasks.

        Falls back to heuristic decomposition when no LLM is available.

        Args:
            objective: High-level goal string

        Returns:
            List of TaskPacket objects
        """
        if hasattr(self, "_push_event_callback") and self._push_event_callback:
            self._push_event_callback(
                "info", "coordinator", f"decomposing goal: {objective[:50]}..."
            )

        from .overseer import create_overseer

        overseer = create_overseer()

        raw_tasks = await overseer.decompose(objective)

        tasks: List[TaskPacket] = []
        for i, t in enumerate(raw_tasks):
            task = TaskPacket(
                id=t.get("id", f"task-{i + 1}"),
                title=t.get("title", f"Task {i + 1}"),
                description=t.get("description", objective),
                role_required=t.get("role", "developer"),
                runtime_preference=[t.get("runtime", "echo")]
                if t.get("runtime")
                else ["echo"],
                priority=t.get("priority", "medium"),
                depends_on=t.get("depends_on", []),
                files_in_scope=t.get("files_in_scope", []),
            )
            tasks.append(task)

        return tasks

    async def assign_task(self, task: TaskPacket) -> Optional[str]:
        """
        Assign a task to an appropriate agent.

        Returns:
            session_id if successfully assigned, None otherwise
        """
        # Check if role is available
        if not role_registry.has_role(task.role_required):
            if hasattr(self, "_push_event_callback") and self._push_event_callback:
                self._push_event_callback(
                    "warning",
                    "coordinator",
                    f"Role '{task.role_required}' not available",
                )
            return None

        # Check if any runtimes are available
        from ..runtimes.registry import registry

        available_runtimes = registry.list_available()
        if not available_runtimes:
            if hasattr(self, "_push_event_callback") and self._push_event_callback:
                self._push_event_callback(
                    "error", "coordinator", "No runtimes available."
                )
            return None

        requested_runtime = (
            task.runtime_preference[0] if task.runtime_preference else "echo"
        )
        if requested_runtime not in available_runtimes:
            requested_runtime = available_runtimes[0]

        prompt_path = f"src/agents/definitions/{task.role_required}.md"
        if not os.path.exists(prompt_path):
            prompt_path = "src/agents/definitions/scout.md"

        policy = self._role_tool_policy.get(task.role_required, {})
        attached_skills = getattr(task, "skills", [])
        allowed_tools = list(policy.get("allowed", []))
        blocked_tools = list(policy.get("blocked", []))
        extra_instructions = []

        from ..skills.registry import skill_registry

        for skill_name in attached_skills:
            skill_def = skill_registry.get_skill(skill_name)
            if skill_def:
                allowed_tools.extend(skill_def.allowed_tools)
                blocked_tools.extend(skill_def.blocked_tools)
                if skill_def.instructions:
                    extra_instructions.append(
                        f"\n--- SKILL: {skill_name} ---\n{skill_def.instructions}"
                    )

        from ..messaging.db import db as swarm_db

        # Best-effort: fetch past lessons to enrich the agent's task context.
        # If the database isn't connected (e.g. in tests), skip silently.
        past_lessons: list[str] = []
        try:
            past_lessons = await swarm_db.get_lessons_for_role(task.role_required)
        except RuntimeError:
            # DB not connected — proceed without lesson context
            pass
        experience_context = ""
        if past_lessons:
            lessons_text = "\n".join([f"- {l}" for l in past_lessons])
            experience_context = (
                f"\n\n## PAST EXPERIENCE & LESSONS LEARNED\n{lessons_text}\n"
            )

        config = AgentConfig(
            name=f"agent-{task.role_required}-{task.id}",
            role=task.role_required,
            task=task.description + experience_context,
            worktree_path=".swarm/worktrees",
            model="default",
            runtime=requested_runtime,
            system_prompt_path=prompt_path,
            allowed_tools=allowed_tools,
            blocked_tools=blocked_tools,
            read_only=self._role_read_only.get(task.role_required, False),
            skills=attached_skills,
        )

        try:
            session_id = await agent_manager.spawn_agent(config)
            self._active_tasks[session_id] = task
            task.status = "active"

            for callback in self._on_task_assigned_callbacks:
                callback(session_id, task)

            return session_id
        except Exception as e:
            if self._push_event_callback:
                self._push_event_callback(
                    "error", "coordinator", f"Failed to spawn agent: {e}"
                )
            return None

    async def get_task_status(self, session_id: str) -> Optional[TaskPacket]:
        """Get the task associated with an agent."""
        return self._active_tasks.get(session_id)

    async def process_task_queue(self):
        """Find and spawn all tasks that are ready for execution."""
        await self._scan_for_overlaps()

        if any(
            t.potential_conflict
            for t in self._task_queue
            if t.status not in ["completed", "active"]
        ):
            asyncio.create_task(self.resolve_conflicts())

        ready_tasks = self._get_ready_tasks()

        current_count = await agent_manager.get_agent_count()

        for task in ready_tasks:
            if task.potential_conflict:
                continue

            if current_count >= 5:
                break

            task.status = "active"
            asyncio.create_task(self.assign_task(task))
            current_count += 1

            if hasattr(self, "_push_event_callback") and self._push_event_callback:
                self._push_event_callback(
                    "info", "coordinator", f"launched parallel task: {task.title}"
                )

    async def complete_task(self, session_id: str):
        """Mark a task as completed with output validation."""
        if session_id not in self._active_tasks:
            return

        status = await agent_manager.get_agent_status(session_id)
        if not status:
            return

        handoff = self._parse_handoff_json(status.last_output)

        if not handoff and status.state == "done":
            if hasattr(self, "_push_event_callback") and self._push_event_callback:
                self._push_event_callback(
                    "info",
                    "coordinator",
                    f"nudging {session_id} for missing handoff JSON",
                )

            nudge_msg = "Task appears complete but handoff JSON is missing. Please output the structured JSON handoff block."
            await agent_manager.send_message(session_id, nudge_msg)
            return

        if session_id in self._active_tasks:
            task = self._active_tasks.pop(session_id)

            if status.role == "arbiter" and handoff:
                self._apply_arbiter_resolution(handoff)
                return

            task.status = "completed"
            self._task_history.append(task)

            if handoff and handoff.get("critique"):
                from ..messaging.db import db as swarm_db

                asyncio.create_task(
                    swarm_db.add_experience_log(
                        role=status.role,
                        task_title=task.title,
                        status=handoff.get("status", "done"),
                        critique=handoff.get("critique"),
                    )
                )

            asyncio.create_task(self.process_task_queue())

            if handoff and handoff.get("handoff_to"):
                self.trigger_handoff(
                    from_agent=session_id,
                    to_role=handoff["handoff_to"],
                    task_title=task.title,
                    status="done",
                )

    def _apply_arbiter_resolution(self, resolution: dict):
        """Apply the changes dictated by the Arbiter to the task queue."""
        updates = resolution.get("updated_tasks", [])
        for update in updates:
            title = update.get("title")
            for task in self._task_queue:
                if task.title == title:
                    if "status" in update:
                        task.status = update["status"]
                    if "depends_on" in update:
                        task.depends_on = update["depends_on"]
                    if task.status != "blocked":
                        task.potential_conflict = False

        if hasattr(self, "_push_event_callback") and self._push_event_callback:
            self._push_event_callback(
                "done", "coordinator", "Arbiter resolution applied"
            )

        asyncio.create_task(self.process_task_queue())

    def _parse_handoff_json(self, output: str) -> Optional[dict]:
        """Extract and validate the JSON handoff block from agent output."""
        if not output:
            return None
        try:
            lines = output.strip().split("\n")
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i].strip()
                if line.startswith("{") and line.endswith("}"):
                    data = json.loads(line)
                    required = {"role", "status", "summary"}
                    if all(k in data for k in required):
                        return data
        except Exception:
            pass
        return None

    def get_role_priority(self, role: str) -> int:
        return self._role_priority.get(role, 999)

    async def _scan_for_overlaps(self):
        """Identify tasks that target the same files and flag them as conflicting."""
        # 1. Check for cross-swarm locks
        try:
            from ..messaging.db import db as swarm_db

            # ⚡ Bolt Optimization: Await directly instead of using run_coroutine_threadsafe.
            # Using run_coroutine_threadsafe inside an already running event loop returns a Future,
            # which wasn't being awaited, causing a TypeError when trying to iterate over it
            # and blocking the event loop unnecessarily.
            locked_resources = await swarm_db.get_locked_resources()
        except RuntimeError:
            locked_resources = []  # DB not ready or running in different context

        locked_set = set(locked_resources)

        # 2. Local queue scan using O(N) inverted index instead of O(N^2) nested loop
        # Maps file path to the list of tasks modifying it
        # ⚡ Bolt Optimization: Cache the set of files for each task to avoid redundant instantiations
        file_to_tasks: Dict[str, List[tuple[TaskPacket, set[str]]]] = {}

        for task in self._task_queue:
            if task.status in ["completed", "failed"]:
                continue

            task_files = set(task.files_in_scope or [])
            if not task_files:
                continue

            # Check against global locks
            external_overlap = task_files.intersection(locked_set)
            if external_overlap:
                task.potential_conflict = True
                task.conflict_details = (
                    f"File locked by external swarm: {', '.join(external_overlap)}"
                )
                if hasattr(self, "_push_event_callback") and self._push_event_callback:
                    self._push_event_callback(
                        "warn",
                        "coordinator",
                        f"External lock conflict on '{task.title}'",
                    )
                continue

            checked_against = set()
            for f in task_files:
                if f in file_to_tasks:
                    for other_task, other_task_files in file_to_tasks[f]:
                        if id(other_task) in checked_against:
                            continue
                        checked_against.add(id(other_task))

                        overlap = task_files.intersection(other_task_files)
                        if overlap:
                            task.potential_conflict = True
                            other_task.potential_conflict = True
                            details = f"Overlap detected on files: {', '.join(overlap)}"
                            task.conflict_details = details
                            other_task.conflict_details = details
                            if (
                                hasattr(self, "_push_event_callback")
                                and self._push_event_callback
                            ):
                                # Log with other_task first to match original ordering
                                self._push_event_callback(
                                    "warn",
                                    "coordinator",
                                    f"Conflict: '{other_task.title}' vs '{task.title}'",
                                )

                file_to_tasks.setdefault(f, []).append((task, task_files))

    def _get_ready_tasks(self) -> List[TaskPacket]:
        ready = []
        completed_titles = {
            t.title for t in self._task_history if t.status == "completed"
        }
        for task in self._task_queue:
            if task.status in ["completed", "active", "failed"]:
                continue
            all_met = True
            for dep_title in task.depends_on:
                if dep_title not in completed_titles:
                    all_met = False
                    break
            if all_met:
                task.status = "ready"
                ready.append(task)
            else:
                task.status = "blocked"
        return ready

    def _check_circular_dependencies(self, tasks: List[TaskPacket]) -> bool:
        # ⚡ Bolt Optimization: Replace recursive DFS with iterative DFS to check for cycles.
        # This prevents RecursionError on deeply nested dependency graphs and improves performance
        # by eliminating function call overhead.
        adj = {t.title: t.depends_on for t in tasks}
        visited = set()

        for start_node in adj:
            if start_node in visited:
                continue

            stack = [(start_node, False)]
            path: set[str] = set()

            while stack:
                node, is_backtracking = stack.pop()

                if is_backtracking:
                    path.remove(node)
                    continue

                if node in visited:
                    continue

                visited.add(node)
                path.add(node)
                stack.append((node, True))

                for neighbor in adj.get(node, []):
                    if neighbor not in visited:
                        stack.append((neighbor, False))
                    elif neighbor in path:
                        return True

        return False

    async def resolve_conflicts(self):
        """Identify flagged conflicts and spawn an Arbiter to resolve them."""
        conflicting = [
            t for t in self._task_queue if t.potential_conflict and t.status != "active"
        ]
        if not conflicting:
            return
        if hasattr(self, "_push_event_callback") and self._push_event_callback:
            self._push_event_callback(
                "info",
                "coordinator",
                f"spawning Arbiter to resolve {len(conflicting)} conflicts",
            )
        conflict_report = "\n".join(
            [
                f"- Task: {t.title}, Files: {t.files_in_scope}, Goal: {t.description}"
                for t in conflicting
            ]
        )
        config = AgentConfig(
            name="system-arbiter",
            role="arbiter",
            task=f"The following tasks have overlapping scope. Decide on a resolution strategy:\n\n{conflict_report}",
            worktree_path=".",
            model="default",
            runtime="vibe",
            system_prompt_path="src/agents/definitions/arbiter.md",
            read_only=True,
        )
        await agent_manager.spawn_agent(config)

    async def get_next_role_in_workflow(self, current_role: str) -> Optional[str]:
        workflow = ["scout", "developer", "builder", "tester", "reviewer", "merger"]
        try:
            current_index = workflow.index(current_role)
            if current_index < len(workflow) - 1:
                return workflow[current_index + 1]
            return None
        except ValueError:
            return None

    def trigger_handoff(
        self, from_agent: str, to_role: str, task_title: str, status: str
    ):
        for callback in self._on_handoff_callbacks:
            try:
                callback(from_agent, to_role, task_title, status)
            except Exception:
                pass


# Global coordinator instance
coordinator = Coordinator()
