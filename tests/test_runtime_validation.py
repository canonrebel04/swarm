"""
Test suite for runtime validation and availability checks.
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.orchestrator.coordinator import Coordinator, TaskPacket
from src.runtimes.base import AgentConfig


@pytest.fixture
def coordinator():
    return Coordinator()


def test_runtime_validation_on_init(coordinator):
    """Test that coordinator can check runtime availability."""
    # Initially should have echo runtime at least
    from src.runtimes.registry import registry
    available = registry.list_available()
    assert len(available) > 0, "Should have at least echo runtime"


@pytest.mark.asyncio
async def test_handle_user_input_no_runtimes(coordinator):
    """Test that handle_user_input provides feedback when no runtimes available."""
    # Mock the registry to return empty list
    with patch("src.runtimes.registry.registry.list_available", return_value=[]):
        # Collect the streaming output
        outputs = []
        async for token in coordinator.handle_user_input("test task"):
            outputs.append(token)
        
        # Should get error message
        assert len(outputs) == 1
        assert "No runtimes available" in outputs[0]
        assert "configure at least one runtime" in outputs[0]


@pytest.mark.asyncio
async def test_handle_user_input_with_runtimes(coordinator):
    """Test that handle_user_input works normally when runtimes are available."""
    # This should work normally since we have runtimes
    outputs = []
    async for token in coordinator.handle_user_input("test task"):
        outputs.append(token)
        if len(outputs) >= 1:  # Just get first token
            break
    
    # Should get normal decomposition response
    assert len(outputs) == 1
    assert "Decomposed into" in outputs[0]


@pytest.mark.asyncio
async def test_assign_task_no_runtimes(coordinator):
    """Test that assign_task handles missing runtimes gracefully."""
    # Create a test task
    task = TaskPacket(
        id="test-1",
        title="Test Task",
        description="Test description",
        role_required="scout",
        runtime_preference=["nonexistent-runtime"],
        priority="high"
    )
    
    # Mock registry to return empty list
    with patch("src.runtimes.registry.registry.list_available", return_value=[]):
        result = await coordinator.assign_task(task)
        assert result is None


@pytest.mark.asyncio
async def test_assign_task_runtime_fallback(coordinator):
    """Test that assign_task falls back to available runtime."""
    from src.runtimes.registry import registry
    from src.orchestrator.agent_manager import agent_manager
    
    # Create a test task with non-existent runtime
    task = TaskPacket(
        id="test-1",
        title="Test Task",
        description="Test description",
        role_required="scout",
        runtime_preference=["nonexistent-runtime"],
        priority="high"
    )
    
    # Mock registry to return only echo
    available_runtimes = ["echo"]
    with patch("src.runtimes.registry.registry.list_available", return_value=available_runtimes), \
         patch.object(agent_manager, "spawn_agent", return_value="mock-session-id"):
        
        result = await coordinator.assign_task(task)
        
        # Should succeed with fallback to echo
        assert result is not None


@pytest.mark.asyncio
async def test_assign_task_role_not_available(coordinator):
    """Test that assign_task handles missing roles gracefully."""
    # Create a task with non-existent role
    task = TaskPacket(
        id="test-1",
        title="Test Task",
        description="Test description",
        role_required="nonexistent-role",
        runtime_preference=["echo"],
        priority="high"
    )
    
    result = await coordinator.assign_task(task)
    assert result is None


@pytest.mark.asyncio
async def test_coordinator_event_callbacks(coordinator):
    """Test that coordinator pushes appropriate events."""
    # Set up event callback
    events = []
    def mock_callback(event_type, source, message):
        events.append((event_type, source, message))
    
    coordinator._push_event_callback = mock_callback
    
    # Test with no runtimes
    with patch("src.runtimes.registry.registry.list_available", return_value=[]):
        async for _ in coordinator.handle_user_input("test"):
            break
        
        # Should have pushed error event
        assert len(events) == 1
        assert events[0][0] == "error"
        assert events[0][1] == "coordinator"
        assert "No runtimes available" in events[0][2]


def test_runtime_registry_integration():
    """Test that runtime registry is properly integrated."""
    from src.runtimes.registry import registry
    
    # Should have multiple runtimes available
    available = registry.list_available()
    assert len(available) > 0
    
    # Check that we can get runtime instances
    for runtime_name in available:
        runtime_class = registry.get(runtime_name)
        assert runtime_class is not None
        
        # Should be able to instantiate
        runtime = runtime_class()
        assert hasattr(runtime, 'runtime_name')
        assert runtime.runtime_name == runtime_name


@pytest.mark.asyncio
async def test_coordinator_task_decomposition_with_runtimes():
    """Test that task decomposition works when runtimes are available."""
    coordinator = Coordinator()
    
    # This should work since we have runtimes
    tasks = await coordinator.decompose_goal("Implement feature X")
    
    assert len(tasks) > 0
    assert tasks[0].role_required == "scout"
    assert tasks[1].role_required == "developer"
    assert tasks[2].role_required == "tester"


@pytest.mark.asyncio
async def test_coordinator_full_workflow():
    """Test the full coordinator workflow with runtime validation."""
    coordinator = Coordinator()
    from src.orchestrator.agent_manager import agent_manager
    
    # Mock agent spawning to avoid actual process creation
    with patch.object(agent_manager, "spawn_agent", return_value="test-session-id"):
        # Test user input handling
        outputs = []
        async for token in coordinator.handle_user_input("Implement new feature"):
            outputs.append(token)
        
        # Should get successful decomposition
        assert len(outputs) > 0
        assert "Decomposed into" in outputs[0]
        
        # Manually assign a task to test the full workflow
        task = TaskPacket(
            id="test-1",
            title="Test Task",
            description="Test description",
            role_required="scout",
            runtime_preference=["echo"],
            priority="high"
        )
        session_id = await coordinator.assign_task(task)
        
        # Check that tasks were created
        assert session_id is not None
        assert len(coordinator._active_tasks) > 0
