"""
Coordinator for decomposing tasks and assigning agents.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import asyncio
import os
import time
import json
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
            "reviewer": 5,   # Final review
            "merger": 6      # Merge resolution
        }
        self._on_task_assigned_callbacks = []
        self._on_handoff_callbacks = []
        self._merge_manager = None  # Will be initialized when coordinator is ready

    def register_task_assigned_callback(self, callback):
        """Register a callback to be called when a task is assigned."""
        self._on_task_assigned_callbacks.append(callback)

    def register_handoff_callback(self, callback):
        """Register a callback to be called when a task is handed off."""
        self._on_handoff_callbacks.append(callback)
    
    def register_event_callback(self, callback):
        """Register a callback to push events to the event log."""
        self._push_event_callback = callback
    
    def initialize_merge_manager(self):
        """Initialize the merge manager."""
        if self._merge_manager is None:
            from .merge_manager import MergeManager
            self._merge_manager = MergeManager(self)
        return self._merge_manager
    
    def trigger_handoff(self, from_agent: str, to_role: str, task_title: str, 
                       worktree_branch: str = "main", status: str = "done"):
        """Trigger handoff callbacks when a task is handed off."""
        # Emit handoff event for merge manager
        asyncio.create_task(self._emit_handoff_event(from_agent, to_role, task_title, worktree_branch, status))
        
        # Trigger regular callbacks
        for callback in self._on_handoff_callbacks:
            try:
                callback(from_agent, to_role, task_title)
            except Exception:
                pass  # Don't let callback failures break the coordinator
    
    async def _emit_handoff_event(self, from_agent: str, to_role: str, task_title: str, 
                                  worktree_branch: str, status: str) -> None:
        """Emit handoff event to event bus and merge manager."""
        # Initialize merge manager if not already done
        if self._merge_manager is None:
            self.initialize_merge_manager()
        
        # Emit event to event bus
        await event_bus.emit(
            "handoff", "coordinator",
            {
                "from_agent": from_agent,
                "to_agent": to_role,
                "status": status,
                "task_title": task_title,
                "worktree_branch": worktree_branch
            }
        )
    
    async def handle_user_input(self, text: str):
        """
        Handle user input and decompose into tasks.
        
        Args:
            text: User input text
            
        Yields:
            Task decomposition result as streaming tokens
            
        Note: This is designed as an async generator for LLM streaming.
        """
        # Check if any runtimes are available before proceeding
        from ..runtimes.registry import registry
        available_runtimes = registry.list_available()
        if not available_runtimes:
            error_msg = "No runtimes available. Please configure at least one runtime in config.yaml."
            if hasattr(self, '_push_event_callback') and self._push_event_callback:
                self._push_event_callback("error", "coordinator", error_msg)
            yield error_msg
            return
        
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

    def _get_swarm_state(self) -> dict:
        """Get current swarm state from agent manager."""
        from .agent_manager import agent_manager
        
        agents = agent_manager.get_all_agents()
        return {
            "active_agents": [{
                "name": agent.config.name,
                "role": agent.config.role,
                "status": agent.status.state,
                "runtime": agent.config.runtime
            } for agent in agents],
            "agent_count": len(agents),
            "timestamp": time.time()
        }
    
    def _get_codebase_context(self) -> dict:
        """Get codebase context for orchestrator."""
        # Try to get from CodebaseIndex if available
        try:
            from src.memory.codebase_index import CodebaseIndex
            index = CodebaseIndex()
            return index.mem_get_all("orchestrator", "orchestrator") or {}
        except ImportError:
            # Fallback to empty context if CodebaseIndex not available
            return {
                "recent_files": [],
                "key_symbols": [],
                "project_structure": "unknown"
            }
    
    def _build_overseer_prompt(self, user_input: str, swarm_state: dict, codebase_context: dict) -> str:
        """Build the overseer prompt with all context."""
        
        # Format swarm state
        agents_info = "\n".join([
            f"  - {agent['name']} ({agent['role']}): {agent['status']} on {agent['runtime']}"
            for agent in swarm_state['active_agents']
        ]) if swarm_state['active_agents'] else "  (no active agents)"
        
        # Format codebase context
        recent_files = "\n".join([
            f"  - {f}"
            for f in codebase_context.get('recent_files', [])[:5]
        ]) if codebase_context.get('recent_files') else "  (no recent files)"
        
        return f"""You are the Swarm Overseer. Your role is to decompose high-level tasks into specific sub-tasks for specialized agents.

CURRENT SWARM STATE:
Active Agents: {swarm_state['agent_count']}
{agents_info}

CODEBASE CONTEXT:
Recent Files:
{recent_files}

USER REQUEST:
{user_input}

RESPONSE FORMAT:
Return ONLY a valid JSON array of TaskPacket objects. Each TaskPacket must have:
- title: concise task title
- role_required: agent role (scout, developer, builder, tester, reviewer, merger)
- runtime_hint: preferred runtime or null
- task_description: detailed description
- depends_on: array of task titles this depends on (empty if none)
- priority: 1-5 (1=highest, 5=lowest)

EXAMPLE:
[
  {{
    "title": "Analyze authentication system",
    "role_required": "scout",
    "runtime_hint": "mistral-vibe",
    "task_description": "Explore the auth system to understand current implementation",
    "depends_on": [],
    "priority": 2
  }},
  {{
    "title": "Implement JWT validation",
    "role_required": "developer",
    "runtime_hint": "claude-code",
    "task_description": "Add JWT validation to the authentication system",
    "depends_on": ["Analyze authentication system"],
    "priority": 1
  }}
]

IMPORTANT: Your response MUST be valid JSON and ONLY JSON - no explanations or markdown.

NOTE: Prefer mistral-vibe runtime for orchestration tasks as it's optimized for this role."""
    
    def _select_orchestrator_runtime(self, available_runtimes: List[str]) -> str:
        """Select the best runtime for orchestrator role."""
        # Make Vibe the default runtime for orchestrator role
        if "mistral-vibe" in available_runtimes:
            return "mistral-vibe"
        
        # Prefer OpenClaw if Vibe not available
        if "openclaw" in available_runtimes:
            return "openclaw"
        
        # Fallback to other runtimes that can handle orchestration
        for runtime in ["hermes", "gemini", "claude-code"]:
            if runtime in available_runtimes:
                return runtime
        
        # Return first available as last resort
        return available_runtimes[0]
    
    async def _execute_llm_call(self, runtime_name: str, prompt: str):
        """Execute LLM call and stream results."""
        from ..runtimes.registry import registry
        from ..runtimes.base import AgentConfig
        
        try:
            # Get the runtime class
            runtime_class = registry.get(runtime_name)
            if not runtime_class:
                yield f"Error: Runtime {runtime_name} not found"
                return
            
            # Create a temporary config for the orchestrator
            config = AgentConfig(
                name="overseer",
                role="orchestrator",
                task=prompt,
                worktree_path=".",
                runtime=runtime_name,
                system_prompt_path=None
            )
            
            # Spawn the agent
            runtime_instance = runtime_class()
            session_id = await runtime_instance.spawn(config)
            
            # Stream the output
            output_tokens = []
            async for token in runtime_instance.stream_output(session_id):
                output_tokens.append(token)
                yield token
            
            # Clean up
            await runtime_instance.kill(session_id)
            
            # Parse the output and create tasks
            full_output = "".join(output_tokens)
            tasks = self._parse_llm_output(full_output)
            
            # Store tasks for later processing
            self._active_tasks.update({task.id: task for task in tasks})
            
        except Exception as e:
            error_msg = f"LLM call failed: {str(e)}"
            if hasattr(self, '_push_event_callback') and self._push_event_callback:
                self._push_event_callback("error", "coordinator", error_msg)
            yield error_msg
    
    def _parse_llm_output(self, output: str) -> List[TaskPacket]:
        """Parse LLM JSON output into TaskPacket objects."""
        import json
        
        try:
            # Try to parse as JSON
            task_data = json.loads(output)
            
            if not isinstance(task_data, list):
                raise ValueError("Expected JSON array")
            
            tasks = []
            for i, task_dict in enumerate(task_data):
                # Validate required fields
                required_fields = ['title', 'role_required', 'task_description', 'depends_on', 'priority']
                for field in required_fields:
                    if field not in task_dict:
                        raise ValueError(f"Missing required field: {field}")
                
                # Create TaskPacket
                task = TaskPacket(
                    id=f"task-{i+1}",
                    title=str(task_dict['title']),
                    description=str(task_dict['task_description']),
                    role_required=str(task_dict['role_required']),
                    runtime_preference=[task_dict.get('runtime_hint', 'echo')],
                    priority=str(task_dict.get('priority', '3')),
                    files_in_scope=None,
                    acceptance_criteria=None,
                    parent_agent=None
                )
                tasks.append(task)
            
            return tasks
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback to simple decomposition if JSON parsing fails
            print(f"Failed to parse LLM output: {e}")
            print(f"Output was: {output[:200]}...")
            return self.decompose_task(output)  # Fallback to original method
    
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
                                        "No runtimes available. Please configure at least one runtime.")
            return None
        
        # Check if the requested runtime is available
        requested_runtime = task.runtime_preference[0] if task.runtime_preference else "echo"
        if requested_runtime not in available_runtimes:
            if hasattr(self, '_push_event_callback') and self._push_event_callback:
                self._push_event_callback("warning", "coordinator", 
                                        f"Requested runtime '{requested_runtime}' not available. "
                                        f"Available: {', '.join(available_runtimes)}")
            # Fallback to first available runtime
            requested_runtime = available_runtimes[0]
        
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
            runtime=requested_runtime,
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

    def handle_overseer_input(self, text: str) -> None:
        """Handle overseer input from the TUI."""
        # Create a background task to process the input
        asyncio.create_task(self._process_overseer_input(text))

    async def _process_overseer_input(self, text: str) -> None:
        """Process overseer input asynchronously."""
        try:
            # Add to task queue for decomposition
            await self._task_queue.put(text)
            
            # Push event
            if self._push_event_callback:
                self._push_event_callback("info", "coordinator", f"queued: {text}")
            
            # Start processing if not already running
            if not hasattr(self, '_processing_task') or self._processing_task.done():
                self._processing_task = asyncio.create_task(self._process_task_queue())
        except Exception as e:
            if self._push_event_callback:
                self._push_event_callback("error", "coordinator", f"Failed to process input: {e}")


# Global coordinator instance
coordinator = Coordinator()