"""
Coordinator for decomposing tasks and assigning agents.
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
import asyncio
import os
import time
import json
from ..runtimes.base import AgentConfig, AgentStatus
from ..roles.registry import role_registry
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
    status: str = "pending" # pending, blocked, ready, active, completed, failed
    potential_conflict: bool = False
    conflict_details: str = ""
    files_in_scope: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = None
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
            "scout": 1,      # First to explore
            "developer": 2,  # Complex implementation
            "builder": 3,    # Straightforward tasks
            "tester": 4,     # Validation
            "reviewer": 5,   # Final review
            "merger": 6      # Merge resolution
        }
        self._role_tool_policy = {
            "scout": {
                "allowed": ["Read", "Bash(find:*)", "Bash(grep:*)", "Bash(cat:*)", "Bash(ls:*)"],
                "blocked": ["Edit", "Write", "Bash(git:commit:*)", "Bash(git:push:*)"]
            },
            "reviewer": {
                "allowed": ["Read", "Bash(git:diff:*)", "Bash(git:log:*)", "Bash(grep:*)"],
                "blocked": ["Edit", "Write", "Bash(git:commit:*)"]
            },
            "monitor": {
                "allowed": ["Read", "Bash(ps:*)", "Bash(ls:*)", "Bash(git:status:*)"],
                "blocked": ["Edit", "Write"]
            },
            "coordinator": {
                "allowed": ["Read", "Bash(ls:*)"],
                "blocked": ["Edit", "Write"]
            }
        }
        self._role_read_only = {
            "scout": True,
            "reviewer": True,
            "monitor": True,
            "coordinator": True,
            "orchestrator": True
        }
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
        
        Args:
            objective: High-level goal string
            
        Returns:
            List of TaskPacket objects
        """
        if hasattr(self, '_push_event_callback') and self._push_event_callback:
            self._push_event_callback("info", "coordinator", f"decomposing goal: {objective[:50]}...")

        # For Milestone 1, we use a simple rule-based decomposition if no LLM is ready
        # In a real implementation, this would call the Overseer runtime
        
        tasks = []
        
        # Add scout task
        scout_task = TaskPacket(
            id=f"task-{len(tasks)+1}",
            title="Scout codebase",
            description=f"Explore the codebase related to: {objective}",
            role_required="scout",
            runtime_preference=["echo", "gemini", "codex"],
            priority="medium"
        )
        tasks.append(scout_task)
        
        # Add implementation task
        impl_task = TaskPacket(
            id=f"task-{len(tasks)+1}",
            title="Implement feature",
            description=f"Implement the feature: {objective}",
            role_required="developer",
            runtime_preference=["echo", "codex", "claude-code"],
            priority="high"
        )
        tasks.append(impl_task)
        
        # Add testing task
        test_task = TaskPacket(
            id=f"task-{len(tasks)+1}",
            title="Test implementation",
            description=f"Validate the implementation of: {objective}",
            role_required="tester",
            runtime_preference=["echo", "gemini"],
            priority="medium"
        )
        tasks.append(test_task)
        
        return tasks

    async def assign_task(self, task: TaskPacket) -> Optional[str]:
        """
        Assign a task to an appropriate agent.
        
        Returns:
            session_id if successfully assigned, None otherwise
        """
        # Check if role is available
        if not role_registry.has_role(task.role_required):
            if hasattr(self, '_push_event_callback') and self._push_event_callback:
                self._push_event_callback("warning", "coordinator", 
                                        f"Role '{task.role_required}' not available")
            return None
        
        # Check if any runtimes are available
        from ..runtimes.registry import registry
        available_runtimes = registry.list_available()
        if not available_runtimes:
            if hasattr(self, '_push_event_callback') and self._push_event_callback:
                self._push_event_callback("error", "coordinator", 
                                        "No runtimes available.")
            return None
        
        requested_runtime = task.runtime_preference[0] if task.runtime_preference else "echo"
        if requested_runtime not in available_runtimes:
            requested_runtime = available_runtimes[0]
        
        prompt_path = f"src/agents/definitions/{task.role_required}.md"
        if not os.path.exists(prompt_path):
            prompt_path = "src/agents/definitions/scout.md"
            
        policy = self._role_tool_policy.get(task.role_required, {})
        attached_skills = getattr(task, 'skills', [])
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
                    extra_instructions.append(f"\n--- SKILL: {skill_name} ---\n{skill_def.instructions}")

        from ..messaging.db import db as swarm_db
        past_lessons = await swarm_db.get_lessons_for_role(task.role_required)
        experience_context = ""
        if past_lessons:
            lessons_text = "\n".join([f"- {l}" for l in past_lessons])
            experience_context = f"\n\n## PAST EXPERIENCE & LESSONS LEARNED\n{lessons_text}\n"

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
            skills=attached_skills
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
                self._push_event_callback("error", "coordinator", f"Failed to spawn agent: {e}")
            return None

    async def get_task_status(self, session_id: str) -> Optional[TaskPacket]:
        """Get the task associated with an agent."""
        return self._active_tasks.get(session_id)

    async def process_task_queue(self):
        """Find and spawn all tasks that are ready for execution."""
        self._scan_for_overlaps()
        
        if any(t.potential_conflict for t in self._task_queue if t.status not in ["completed", "active"]):
            asyncio.create_task(self.resolve_conflicts())

        ready_tasks = self._get_ready_tasks()
        
        for task in ready_tasks:
            if task.potential_conflict:
                continue
                
            current_count = await agent_manager.get_agent_count()
            if current_count >= 5:
                break
                
            task.status = "active"
            asyncio.create_task(self.assign_task(task))
            
            if hasattr(self, '_push_event_callback') and self._push_event_callback:
                self._push_event_callback("info", "coordinator", f"launched parallel task: {task.title}")

    async def complete_task(self, session_id: str):
        """Mark a task as completed with output validation."""
        if session_id not in self._active_tasks:
            return

        status = await agent_manager.get_agent_status(session_id)
        if not status:
            return

        handoff = self._parse_handoff_json(status.last_output)
        
        if not handoff and status.state == "done":
            if hasattr(self, '_push_event_callback') and self._push_event_callback:
                self._push_event_callback("info", "coordinator", f"nudging {session_id} for missing handoff JSON")
            
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
                asyncio.create_task(swarm_db.add_experience_log(
                    role=status.role,
                    task_title=task.title,
                    status=handoff.get("status", "done"),
                    critique=handoff.get("critique")
                ))

            asyncio.create_task(self.process_task_queue())

            if handoff and handoff.get("handoff_to"):
                self.trigger_handoff(
                    from_agent=session_id,
                    to_role=handoff["handoff_to"],
                    task_title=task.title,
                    status="done"
                )

    def _apply_arbiter_resolution(self, resolution: dict):
        """Apply the changes dictated by the Arbiter to the task queue."""
        updates = resolution.get("updated_tasks", [])
        for update in updates:
            title = update.get("title")
            for task in self._task_queue:
                if task.title == title:
                    if "status" in update: task.status = update["status"]
                    if "depends_on" in update: task.depends_on = update["depends_on"]
                    if task.status != "blocked":
                        task.potential_conflict = False
        
        if hasattr(self, '_push_event_callback') and self._push_event_callback:
            self._push_event_callback("done", "coordinator", "Arbiter resolution applied")
        
        asyncio.create_task(self.process_task_queue())

    def _parse_handoff_json(self, output: str) -> Optional[dict]:
        """Extract and validate the JSON handoff block from agent output."""
        if not output: return None
        try:
            lines = output.strip().split('\n')
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i].strip()
                if line.startswith('{') and line.endswith('}'):
                    data = json.loads(line)
                    required = {"role", "status", "summary"}
                    if all(k in data for k in required):
                        return data
        except Exception: pass
        return None

    def get_role_priority(self, role: str) -> int:
        return self._role_priority.get(role, 999)

    def _scan_for_overlaps(self):
        """Identify tasks that target the same files and flag them as conflicting."""
        # 1. Check for cross-swarm locks
        try:
            from ..messaging.db import db as swarm_db
            locked_resources = asyncio.run_coroutine_threadsafe(
                swarm_db.get_locked_resources(), 
                asyncio.get_event_loop()
            ) if asyncio.get_event_loop().is_running() else []
        except RuntimeError:
            locked_resources = [] # DB not ready or running in different context

        # 2. Local queue scan
        for i, task_a in enumerate(self._task_queue):
            if task_a.status in ["completed", "failed"]: continue
            
            a_files = set(task_a.files_in_scope or [])
            
            # Check against global locks
            external_overlap = a_files.intersection(set(locked_resources))
            if external_overlap:
                task_a.potential_conflict = True
                task_a.conflict_details = f"File locked by external swarm: {', '.join(external_overlap)}"
                if hasattr(self, '_push_event_callback') and self._push_event_callback:
                    self._push_event_callback("warn", "coordinator", f"External lock conflict on '{task_a.title}'")
                continue

            for task_b in self._task_queue[i+1:]:
                if task_b.status in ["completed", "failed"]: continue
                b_files = set(task_b.files_in_scope or [])
                overlap = a_files.intersection(b_files)
                if overlap:
                    task_a.potential_conflict = True
                    task_b.potential_conflict = True
                    details = f"Overlap detected on files: {', '.join(overlap)}"
                    task_a.conflict_details = details
                    task_b.conflict_details = details
                    if hasattr(self, '_push_event_callback') and self._push_event_callback:
                        self._push_event_callback("warn", "coordinator", f"Conflict: '{task_a.title}' vs '{task_b.title}'")

    def _get_ready_tasks(self) -> List[TaskPacket]:
        ready = []
        completed_titles = {t.title for t in self._task_history if t.status == "completed"}
        for task in self._task_queue:
            if task.status in ["completed", "active", "failed"]: continue
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
        adj = {t.title: t.depends_on for t in tasks}
        visited = set()
        path = set()
        def has_cycle(v):
            visited.add(v)
            path.add(v)
            for neighbor in adj.get(v, []):
                if neighbor not in visited:
                    if has_cycle(neighbor): return True
                elif neighbor in path: return True
            path.remove(v)
            return False
        for node in adj:
            if node not in visited:
                if has_cycle(node): return True
        return False

    async def resolve_conflicts(self):
        """Identify flagged conflicts and spawn an Arbiter to resolve them."""
        conflicting = [t for t in self._task_queue if t.potential_conflict and t.status != "active"]
        if not conflicting: return
        if hasattr(self, '_push_event_callback') and self._push_event_callback:
            self._push_event_callback("info", "coordinator", f"spawning Arbiter to resolve {len(conflicting)} conflicts")
        conflict_report = "\n".join([f"- Task: {t.title}, Files: {t.files_in_scope}, Goal: {t.description}" for t in conflicting])
        config = AgentConfig(
            name="system-arbiter", role="arbiter",
            task=f"The following tasks have overlapping scope. Decide on a resolution strategy:\n\n{conflict_report}",
            worktree_path=".", model="default", runtime="vibe",
            system_prompt_path="src/agents/definitions/arbiter.md", read_only=True
        )
        await agent_manager.spawn_agent(config)

    async def get_next_role_in_workflow(self, current_role: str) -> Optional[str]:
        workflow = ["scout", "developer", "builder", "tester", "reviewer", "merger"]
        try:
            current_index = workflow.index(current_role)
            if current_index < len(workflow) - 1:
                return workflow[current_index + 1]
            return None
        except ValueError: return None

    def trigger_handoff(self, from_agent: str, to_role: str, task_title: str, status: str):
        for callback in self._on_handoff_callbacks:
            try: callback(from_agent, to_role, task_title, status)
            except Exception: pass


# Global coordinator instance
coordinator = Coordinator()
