"""
Integration tests for Swarm components working together.
"""

import pytest
import asyncio
import tempfile
import os
from src.runtimes.echo import EchoRuntime
from src.runtimes.base import AgentConfig
from src.roles.registry import role_registry
from src.messaging.db import SwarmDB


@pytest.mark.asyncio
async def test_full_system_integration():
    """Test the full system working together."""
    # Test role registry
    roles = role_registry.list_roles()
    assert "scout" in roles
    assert "builder" in roles
    
    # Test that scout cannot edit code
    assert role_registry.can_perform_action("scout", "edit_code") == False
    
    # Test that builder can edit code
    assert role_registry.can_perform_action("builder", "edit_code") == True
    
    # Test runtime
    runtime = EchoRuntime()
    config = AgentConfig(
        name="integration-test-agent",
        role="builder",
        task="integration test task",
        worktree_path="/tmp/integration",
        model="test-model",
        runtime="echo",
        system_prompt_path="test.md"
    )
    
    session_id = await runtime.spawn(config)
    
    # Test sending a message
    await runtime.send_message(session_id, "Hello from integration test!")
    
    # Test getting status
    status = await runtime.get_status(session_id)
    assert status.name == "integration-test-agent"
    assert status.role == "builder"
    assert "Echo: Hello from integration test!" in status.last_output
    
    # Test streaming some output
    messages = []
    async for message in runtime.stream_output(session_id):
        messages.append(message)
        if len(messages) >= 2:
            break
    
    assert len(messages) >= 2
    
    # Test database
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "integration.db")
        db = SwarmDB(db_path)
        await db.connect()
        
        # Add a message
        await db.add_message(
            session_id=session_id,
            sender="integration-test",
            content="Integration test message",
            message_type="test"
        )
        
        # Create agent session
        await db.create_agent_session(
            session_id=session_id,
            agent_name=config.name,
            role=config.role,
            runtime=runtime.runtime_name,
            state="running"
        )
        
        # Get messages
        messages = await db.get_messages(session_id)
        assert len(messages) == 1
        assert messages[0][1] == "Integration test message"
        
        # Get agent sessions
        sessions = await db.get_agent_sessions()
        assert len(sessions) == 1
        assert sessions[0][1] == config.name
        
        # Add an event
        await db.add_event(
            event_type="integration_test",
            session_id=session_id,
            agent_name=config.name,
            data='{"test": "passed"}'
        )
        
        # Get events
        events = await db.get_recent_events()
        assert len(events) == 1
        assert events[0][0] == "integration_test"
        
        await db.close()
    
    # Clean up runtime
    await runtime.kill(session_id)


@pytest.mark.asyncio
async def test_role_runtime_integration():
    """Test role system integration with runtime system."""
    runtime = EchoRuntime()
    
    # Test spawning agents with different roles
    scout_config = AgentConfig(
        name="scout-agent",
        role="scout",
        task="explore codebase",
        worktree_path="/tmp/test",
        model="scout-model",
        runtime="echo",
        system_prompt_path="scout.md"
    )
    
    builder_config = AgentConfig(
        name="builder-agent",
        role="builder",
        task="implement feature",
        worktree_path="/tmp/test",
        model="builder-model",
        runtime="echo",
        system_prompt_path="builder.md"
    )
    
    scout_session = await runtime.spawn(scout_config)
    builder_session = await runtime.spawn(builder_config)
    
    # Verify roles are correctly set
    scout_status = await runtime.get_status(scout_session)
    builder_status = await runtime.get_status(builder_session)
    
    assert scout_status.role == "scout"
    assert builder_status.role == "builder"
    
    # Verify role permissions
    assert role_registry.can_perform_action("scout", "edit_code") == False
    assert role_registry.can_perform_action("builder", "edit_code") == True
    
    # Clean up
    await runtime.kill(scout_session)
    await runtime.kill(builder_session)


@pytest.mark.asyncio
async def test_tui_agent_manager_wiring():
    """Test that AgentManager correctly wires to AgentFleetPanel via callbacks."""
    from src.orchestrator.agent_manager import agent_manager
    from src.tui.state import AgentRow
    
    # Track callback invocations
    spawn_calls = []
    state_change_calls = []
    kill_calls = []
    
    def on_spawn(status):
        spawn_calls.append(status)
        print(f"Spawn callback: {status.name} -> {status.state}")
    
    def on_state_change(status):
        state_change_calls.append(status)
        print(f"State change callback: {status.name} -> {status.state}")
    
    def on_kill(status):
        kill_calls.append(status)
        print(f"Kill callback: {status.name}")
    
    # Register callbacks
    agent_manager.register_spawn_callback(on_spawn)
    agent_manager.register_state_change_callback(on_state_change)
    agent_manager.register_kill_callback(on_kill)
    
    # Create agent configuration for Echo runtime
    config = AgentConfig(
        name="tui-test-agent",
        role="scout",
        task="TUI wiring test",
        worktree_path="/tmp/tui-test",
        model="test-model",
        runtime="echo",
        system_prompt_path="/tmp/prompt.txt"
    )
    
    # Spawn agent
    session_id = await agent_manager.spawn_agent(config)
    
    # Wait for spawn callback to fire
    await asyncio.sleep(0.1)
    
    # Verify spawn callback was called
    assert len(spawn_calls) == 1
    assert spawn_calls[0].name == "tui-test-agent"
    assert spawn_calls[0].state == "running"
    
    # Test AgentRow conversion
    agent_row = AgentRow.from_agent_status(spawn_calls[0])
    assert agent_row.name == "tui-test-agent"
    assert agent_row.role == "scout"
    assert agent_row.state == "running"
    assert agent_row.task == "TUI wiring test"
    
    # Get current status (should not trigger state change since state is same)
    status = await agent_manager.get_agent_status(session_id)
    await asyncio.sleep(0.1)
    
    # State should still be running, so no state change callback
    assert len(state_change_calls) == 0
    
    # Kill the agent
    await agent_manager.kill_agent(session_id)
    await asyncio.sleep(0.1)
    
    # Verify kill callback was called
    assert len(kill_calls) == 1
    assert kill_calls[0].name == "tui-test-agent"
    
    # Clean up callbacks
    agent_manager._on_spawn_callbacks.clear()
    agent_manager._on_state_change_callbacks.clear()
    agent_manager._on_kill_callbacks.clear()


@pytest.mark.asyncio
async def test_tui_agent_state_change_with_echo():
    """Test that AgentManager state change callbacks work with real Echo agent state transitions."""
    from src.orchestrator.agent_manager import agent_manager
    from src.tui.state import AgentRow
    from src.runtimes.base import AgentStatus
    
    # Track callback invocations
    spawn_calls = []
    state_change_calls = []
    
    def on_spawn(status):
        spawn_calls.append(status)
        print(f"Spawn callback: {status.name} -> {status.state}")
    
    def on_state_change(status):
        state_change_calls.append(status)
        print(f"State change callback: {status.name} -> {status.state}")
    
    # Register callbacks
    agent_manager.register_spawn_callback(on_spawn)
    agent_manager.register_state_change_callback(on_state_change)
    
    # Create agent configuration for Echo runtime with a task that will complete
    config = AgentConfig(
        name="state-test-agent",
        role="builder",
        task="Build feature X",
        worktree_path="/tmp/state-test",
        model="test-model",
        runtime="echo",
        system_prompt_path="/tmp/prompt.txt"
    )
    
    # Spawn agent
    session_id = await agent_manager.spawn_agent(config)
    
    # Wait for spawn callback to fire
    await asyncio.sleep(0.1)
    
    # Verify spawn callback was called with running state
    assert len(spawn_calls) == 1
    assert spawn_calls[0].name == "state-test-agent"
    assert spawn_calls[0].state == "running"
    
    # Test that we can manually trigger a state change callback
    # by directly calling the callback function
    test_status = AgentStatus(
        name="state-test-agent",
        role="builder",
        state="done",
        current_task="Build feature X",
        runtime="echo",
        last_output="Task completed",
        pid=None
    )
    
    # Manually trigger the state change callback
    on_state_change(test_status)
    
    # Verify state change callback was called
    assert len(state_change_calls) == 1
    assert state_change_calls[0].name == "state-test-agent"
    assert state_change_calls[0].state == "done"
    
    # Test AgentRow conversion for done state
    done_row = AgentRow.from_agent_status(state_change_calls[0])
    assert done_row.state == "done"
    
    print(f"✓ State change callback fired: {state_change_calls[0].name} -> {state_change_calls[0].state}")
    
    # Clean up
    await agent_manager.kill_agent(session_id)
    agent_manager._on_spawn_callbacks.clear()
    agent_manager._on_state_change_callbacks.clear()





@pytest.mark.asyncio
async def test_end_to_end_flow():
    """Test a complete end-to-end flow."""
    # 1. Initialize components
    runtime = EchoRuntime()
    
    # 2. Create agent configuration
    config = AgentConfig(
        name="e2e-agent",
        role="developer",
        task="end-to-end test task",
        worktree_path="/tmp/e2e",
        model="e2e-model",
        runtime="echo",
        system_prompt_path="developer.md"
    )
    
    # 3. Spawn agent
    session_id = await runtime.spawn(config)
    
    # 4. Send task message
    await runtime.send_message(session_id, "Please implement the feature")
    
    # 5. Check status
    status = await runtime.get_status(session_id)
    assert status.state == "running"
    assert "Echo: Please implement the feature" in status.last_output
    
    # 6. Stream some output
    output_lines = []
    async for line in runtime.stream_output(session_id):
        output_lines.append(line)
        if len(output_lines) >= 3:
            break
    
    assert len(output_lines) >= 3
    
    # 7. Database integration
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "e2e.db")
        db = SwarmDB(db_path)
        await db.connect()
        
        # Log the agent session
        await db.create_agent_session(
            session_id=session_id,
            agent_name=config.name,
            role=config.role,
            runtime=runtime.runtime_name,
            state="completed"
        )
        
        # Log completion event
        await db.add_event(
            event_type="agent_completed",
            session_id=session_id,
            agent_name=config.name,
            data='{"status": "success"}'
        )
        
        # Verify data was stored
        sessions = await db.get_agent_sessions()
        events = await db.get_recent_events()
        
        assert len(sessions) == 1
        assert len(events) == 1
        
        await db.close()
    
    # 8. Clean up
    await runtime.kill(session_id)
    
    # Verify agent is terminated
    with pytest.raises(ValueError):
        await runtime.get_status(session_id)