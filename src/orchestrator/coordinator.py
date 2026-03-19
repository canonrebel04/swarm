"""
Coordinator for decomposing tasks and assigning agents.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import asyncio
import os
from ..runtimes.base import AgentConfig
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
    files_in_scope: List[str] = None
    acceptance_criteria: List[str] = None
    parent_agent: Optional[str] = None


class Coordinator:
    """Coordinate task decomposition and agent assignment."""

    def __init__(self):
        self._task_queue = asyncio.Queue()
        self._active_tasks = {}
        self._role_priority = {
            "scout": 1,      # First to explore
            "developer": 2,  # Complex implementation
            "builder": 3,    # Straightforward tasks
            "tester": 4,     # Validation
            "reviewer": 5    # Final review
        }
        self._on_task_assigned_callbacks = []
        self._on_handoff_callbacks = []

    def register_task_assigned_callback(self, callback):
        """Register a callback to be called when a task is assigned."""
        self._on_task_assigned_callbacks.append(callback)

    def register_handoff_callback(self, callback):
        """Register a callback to be called when a task is handed off."""
        self._on_handoff_callbacks.append(callback)
    
    def register_event_callback(self, callback):
        """Register a callback to push events to the event log."""
        self._push_event_callback = callback
    
    def trigger_handoff(self, from_agent: str, to_role: str, task_title: str):
        """Trigger handoff callbacks when a task is handed off."""
        for callback in self._on_handoff_callbacks:
            try:
                callback(from_agent, to_role, task_title)
            except Exception:
                pass  # Don't let callback failures break the coordinator
    
    async def handle_user_input(self, text: str):
        """
        Handle user input and decompose into tasks.
        
        Args:
            text: User input text
            
        Yields:
            Task decomposition result as streaming tokens
            
        Note: This is designed as an async generator for LLM streaming.
        """
        # Decompose the task
        tasks = await self.decompose_task(text)
        
        # Format the response
        task_titles = [task.title for task in tasks]
        result = f"Decomposed into {len(tasks)} tasks: {', '.join(task_titles)}"
        
        # Push event about task dispatch
        if hasattr(self, '_push_event_callback') and self._push_event_callback:
            self._push_event_callback("info", "coordinator", f"dispatched {len(tasks)} tasks")
        
        # Yield the response as tokens (stub-compatible with real LLM streaming)
        yield result

    async def decompose_task(self, task_description: str) -> List[TaskPacket]:
        """
        Decompose a high-level task into sub-tasks.
        
        Args:
            task_description: High-level task description
            
        Returns:
            List of decomposed task packets
        """
        # This is a simple decomposition strategy
        # In a real implementation, this would use more sophisticated logic
        
        tasks = []
        
        # Always start with exploration
        scout_task = TaskPacket(
            id=f"task-{len(tasks)+1}",
            title="Explore codebase and requirements",
            description=f"Analyze the codebase to understand how to implement: {task_description}",
            role_required="scout",
            runtime_preference=["echo", "mistral-vibe"],
            priority="high"
        )
        tasks.append(scout_task)
        
        # Add implementation task
        impl_task = TaskPacket(
            id=f"task-{len(tasks)+1}",
            title="Implement feature",
            description=f"Implement the feature: {task_description}",
            role_required="developer",
            runtime_preference=["echo", "codex", "claude-code"],
            priority="high"
        )
        tasks.append(impl_task)
        
        # Add testing task
        test_task = TaskPacket(
            id=f"task-{len(tasks)+1}",
            title="Test implementation",
            description=f"Validate the implementation of: {task_description}",
            role_required="tester",
            runtime_preference=["echo", "aider"],
            priority="medium"
        )
        tasks.append(test_task)
        
        return tasks

    async def assign_task(self, task: TaskPacket) -> Optional[str]:
        """
        Assign a task to an appropriate agent.
        
        Args:
            task: Task packet to assign
            
        Returns:
            session_id if successfully assigned, None otherwise
        """
        # Check if role is available
        if not role_registry.has_role(task.role_required):
            return None
        
        # Create agent configuration
        # Check if the role definition file exists, otherwise use a default
        prompt_path = f"src/agents/definitions/{task.role_required}.md"
        if not os.path.exists(prompt_path):
            prompt_path = "src/agents/definitions/scout.md"  # Fallback to scout
            
        config = AgentConfig(
            name=f"agent-{task.role_required}-{task.id}",
            role=task.role_required,
            task=task.description,
            worktree_path=".swarm/worktrees",
            model="default",
            runtime=task.runtime_preference[0] if task.runtime_preference else "echo",
            system_prompt_path=prompt_path
        )
        
        try:
            # Spawn the agent
            session_id = await agent_manager.spawn_agent(config)
            
            # Track the task
            self._active_tasks[session_id] = task
            
            return session_id
        except Exception as e:
            print(f"Failed to assign task {task.id}: {e}")
            return None

    async def process_task_queue(self):
        """Process tasks from the queue continuously."""
        while True:
            task = await self._task_queue.get()
            
            try:
                session_id = await self.assign_task(task)
                if session_id:
                    print(f"Assigned task {task.id} to agent {session_id}")
                else:
                    print(f"Could not assign task {task.id}")
            except Exception as e:
                print(f"Error processing task {task.id}: {e}")
            finally:
                self._task_queue.task_done()

    async def add_task(self, task: TaskPacket):
        """Add a task to the queue."""
        await self._task_queue.put(task)

    async def get_task_status(self, session_id: str) -> Optional[TaskPacket]:
        """Get the task associated with an agent."""
        return self._active_tasks.get(session_id)

    async def complete_task(self, session_id: str):
        """Mark a task as completed."""
        if session_id in self._active_tasks:
            del self._active_tasks[session_id]

    def get_role_priority(self, role: str) -> int:
        """Get the priority order for a role."""
        return self._role_priority.get(role, 999)

    async def get_next_role_in_workflow(self, current_role: str) -> Optional[str]:
        """Get the next role in the typical workflow."""
        # Define typical workflow order
        workflow = ["scout", "developer", "builder", "tester", "reviewer", "merger"]
        
        try:
            current_index = workflow.index(current_role)
            if current_index < len(workflow) - 1:
                return workflow[current_index + 1]
            return None
        except ValueError:
            return None


# Global coordinator instance
coordinator = Coordinator()