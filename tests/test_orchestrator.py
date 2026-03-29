"""
Test orchestrator components.
"""

import pytest
import asyncio
from src.orchestrator.agent_manager import AgentManager, AgentInfo
from src.orchestrator.coordinator import Coordinator, TaskPacket
from src.orchestrator.watchdog import Watchdog
from src.runtimes.base import AgentConfig, AgentStatus


@pytest.mark.asyncio
async def test_agent_manager_initialization():
    """Test agent manager initialization."""
    manager = AgentManager()
    assert manager._agents == {}
    assert hasattr(manager, "_lock")


@pytest.mark.asyncio
async def test_agent_manager_spawn_echo():
    """Test spawning an agent with echo runtime."""
    manager = AgentManager()

    config = AgentConfig(
        name="test-agent",
        role="builder",
        task="test task",
        worktree_path="/tmp/test",
        model="echo",
        runtime="echo",
        system_prompt_path="test.md",
    )

    session_id = await manager.spawn_agent(config)
    assert session_id is not None

    # Verify agent is tracked
    agents = await manager.list_agents()
    assert len(agents) == 1
    assert agents[0].name == "test-agent"

    # Clean up
    await manager.kill_agent(session_id)


@pytest.mark.asyncio
async def test_agent_manager_status():
    """Test getting agent status."""
    manager = AgentManager()

    config = AgentConfig(
        name="test-agent",
        role="scout",
        task="explore",
        worktree_path="/tmp/test",
        model="echo",
        runtime="echo",
        system_prompt_path="test.md",
    )

    session_id = await manager.spawn_agent(config)

    # Get status
    status = await manager.get_agent_status(session_id)
    assert status is not None
    assert status.name == "test-agent"
    assert status.role == "scout"

    # Clean up
    await manager.kill_agent(session_id)


@pytest.mark.asyncio
async def test_agent_manager_messages():
    """Test sending messages to agents."""
    manager = AgentManager()

    config = AgentConfig(
        name="test-agent",
        role="developer",
        task="develop",
        worktree_path="/tmp/test",
        model="echo",
        runtime="echo",
        system_prompt_path="test.md",
    )

    session_id = await manager.spawn_agent(config)

    # Send message
    result = await manager.send_message(session_id, "Hello from test!")
    assert result == True

    # Verify status was updated
    status = await manager.get_agent_status(session_id)
    assert "Echo: Hello from test!" in status.last_output

    # Clean up
    await manager.kill_agent(session_id)


@pytest.mark.asyncio
async def test_agent_manager_kill():
    """Test killing agents."""
    manager = AgentManager()

    config = AgentConfig(
        name="test-agent",
        role="tester",
        task="test",
        worktree_path="/tmp/test",
        model="echo",
        runtime="echo",
        system_prompt_path="test.md",
    )

    session_id = await manager.spawn_agent(config)

    # Kill agent
    result = await manager.kill_agent(session_id)
    assert result == True

    # Verify agent is gone
    agents = await manager.list_agents()
    assert len(agents) == 0

    # Verify status returns None for killed agent
    status = await manager.get_agent_status(session_id)
    assert status is None


@pytest.mark.asyncio
async def test_agent_manager_cleanup():
    """Test cleanup functionality."""
    manager = AgentManager()

    # Spawn multiple agents
    configs = [
        AgentConfig(
            name=f"test-agent-{i}",
            role="builder",
            task=f"task-{i}",
            worktree_path="/tmp/test",
            model="echo",
            runtime="echo",
            system_prompt_path="test.md",
        )
        for i in range(3)
    ]

    session_ids = []
    for config in configs:
        session_id = await manager.spawn_agent(config)
        session_ids.append(session_id)

    # Verify agents are active
    agents = await manager.list_agents()
    assert len(agents) == 3

    # Cleanup all
    await manager.cleanup_all()

    # Verify all agents are gone
    agents = await manager.list_agents()
    assert len(agents) == 0


def test_coordinator_initialization():
    """Test coordinator initialization."""
    coordinator = Coordinator()
    assert coordinator._task_queue == []
    assert coordinator._active_tasks == {}


def test_coordinator_task_decomposition():
    """Test task decomposition."""
    coordinator = Coordinator()

    tasks = asyncio.run(coordinator.decompose_goal("Implement user authentication"))

    assert len(tasks) >= 3
    assert tasks[0].role_required == "scout"
    assert tasks[1].role_required == "developer"
    assert tasks[2].role_required == "tester"

    # Check task descriptions
    assert "Implement user authentication" in tasks[0].description
    assert "Implement user authentication" in tasks[1].description
    assert "Implement user authentication" in tasks[2].description


@pytest.mark.asyncio
async def test_coordinator_workflow():
    """Test coordinator workflow management."""
    coordinator = Coordinator()

    # Test next role in workflow
    next_role = await coordinator.get_next_role_in_workflow("scout")
    assert next_role == "developer"

    next_role = await coordinator.get_next_role_in_workflow("developer")
    assert next_role == "builder"

    next_role = await coordinator.get_next_role_in_workflow("tester")
    assert next_role == "reviewer"

    # Test end of workflow
    next_role = await coordinator.get_next_role_in_workflow("merger")
    assert next_role is None

    # Test unknown role
    next_role = await coordinator.get_next_role_in_workflow("unknown")
    assert next_role is None


def test_watchdog_initialization():
    """Test watchdog initialization."""
    watchdog = Watchdog()
    assert watchdog.stall_timeout == 120.0
    assert watchdog.check_interval == 10.0
    assert watchdog._agent_states == {}
    assert watchdog._monitoring == False


@pytest.mark.asyncio
async def test_watchdog_monitoring():
    """Test watchdog monitoring functionality."""
    watchdog = Watchdog(stall_timeout=1.0, check_interval=0.1)

    # Start monitoring
    await watchdog.start_monitoring()
    assert watchdog._monitoring == True

    # Register some activity
    await watchdog.register_agent_activity("test-agent-1")
    await watchdog.register_agent_activity("test-agent-2")

    # Test stalled agent detection directly
    # Wait for agents to be considered stalled
    await asyncio.sleep(1.2)

    # Check for stalled agents (this checks last_activity directly)
    stalled = await watchdog.get_stalled_agents()
    assert "test-agent-1" in stalled
    assert "test-agent-2" in stalled

    # Test activity registration
    assert "test-agent-1" in watchdog._agent_states
    assert "test-agent-2" in watchdog._agent_states

    # Stop monitoring
    await watchdog.stop_monitoring()
    assert watchdog._monitoring == False


@pytest.mark.asyncio
async def test_integration_agent_manager_coordinator():
    """Test integration between agent manager and coordinator."""
    # Use the global instances to ensure they share state
    from src.orchestrator.agent_manager import agent_manager
    from src.orchestrator.coordinator import coordinator

    # Clear any existing agents
    await agent_manager.cleanup_all()

    # Create a task
    task = TaskPacket(
        id="test-task-1",
        title="Test integration task",
        description="Test the integration between components",
        role_required="scout",
        runtime_preference=["echo"],
        priority="high",
        files_in_scope=[],
        acceptance_criteria=[],
    )

    # Assign the task
    session_id = await coordinator.assign_task(task)
    assert session_id is not None

    # Verify agent was spawned
    agents = await agent_manager.list_agents()
    assert len(agents) == 1
    assert agents[0].role == "scout"

    # Verify task is tracked
    active_task = await coordinator.get_task_status(session_id)
    assert active_task is not None
    assert active_task.id == "test-task-1"

    # Clean up
    await agent_manager.kill_agent(session_id)
    await coordinator.complete_task(session_id)


@pytest.mark.asyncio
async def test_global_instances():
    """Test global instances."""
    from src.orchestrator.agent_manager import agent_manager
    from src.orchestrator.coordinator import coordinator
    from src.orchestrator.watchdog import watchdog

    # Verify global instances exist
    assert hasattr(agent_manager, "spawn_agent")
    assert hasattr(coordinator, "decompose_goal")
    assert hasattr(watchdog, "start_monitoring")
