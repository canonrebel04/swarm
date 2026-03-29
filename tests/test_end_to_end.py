"""
End-to-end test for the complete Swarm system.
"""

import pytest
import asyncio
from src.orchestrator.coordinator import coordinator
from src.orchestrator.agent_manager import agent_manager
from src.roles.registry import role_registry


@pytest.mark.asyncio
async def test_complete_workflow():
    """Test a complete workflow from task decomposition to execution."""
    # Clean up any existing agents
    await agent_manager.cleanup_all()
    
    # Verify we have the necessary roles
    available_roles = role_registry.list_roles()
    assert "scout" in available_roles
    assert "developer" in available_roles
    assert "tester" in available_roles
    
    # Decompose a task
    task_description = "Implement user authentication system"
    tasks = await coordinator.decompose_goal(task_description)
    
    assert len(tasks) == 3
    
    # Verify task order and roles
    assert tasks[0].role_required == "scout"
    assert tasks[1].role_required == "developer"
    assert tasks[2].role_required == "tester"
    
    # Assign and execute the first task (scout)
    scout_session = await coordinator.assign_task(tasks[0])
    assert scout_session is not None
    
    # Verify scout agent is running
    agents = await agent_manager.list_agents()
    assert len(agents) == 1
    assert agents[0].role == "scout"
    
    # Get scout status
    scout_status = await agent_manager.get_agent_status(scout_session)
    assert scout_status.state == "running"
    assert "scout" in scout_status.role
    
    # Send a message to the scout
    result = await agent_manager.send_message(scout_session, "Please analyze the codebase")
    assert result == True
    
    # Verify the message was processed
    updated_status = await agent_manager.get_agent_status(scout_session)
    assert "Echo: Please analyze the codebase" in updated_status.last_output
    
    # Test workflow progression
    next_role = await coordinator.get_next_role_in_workflow("scout")
    assert next_role == "developer"
    
    # Clean up
    await agent_manager.kill_agent(scout_session)
    await coordinator.complete_task(scout_session)
    
    # Verify cleanup
    final_agents = await agent_manager.list_agents()
    assert len(final_agents) == 0


@pytest.mark.asyncio
async def test_role_permissions():
    """Test role-based permission system."""
    # Test scout permissions
    assert role_registry.can_perform_action("scout", "edit_code") == False
    assert role_registry.can_perform_action("scout", "read_repo") == True
    
    # Test builder permissions
    assert role_registry.can_perform_action("builder", "edit_code") == True
    assert role_registry.can_perform_action("builder", "merge_branches") == False
    
    # Test developer permissions
    assert role_registry.can_perform_action("developer", "edit_code") == True
    assert role_registry.can_perform_action("developer", "analyze_architecture") == True
    
    # Test tester permissions
    assert role_registry.can_perform_action("tester", "run_tests") == True
    assert role_registry.can_perform_action("tester", "implement_features") == False


@pytest.mark.asyncio
async def test_system_integration():
    """Test integration between all major components."""
    # Clean slate
    await agent_manager.cleanup_all()
    
    # Test role registry
    roles = role_registry.list_roles()
    assert len(roles) >= 4  # We have at least scout, builder, developer, tester
    
    # Test coordinator
    tasks = await coordinator.decompose_goal("Build API endpoint")
    assert len(tasks) > 0
    
    # Test agent manager
    for task in tasks:
        if role_registry.has_role(task.role_required):
            session_id = await coordinator.assign_task(task)
            if session_id:
                # Verify agent was created
                status = await agent_manager.get_agent_status(session_id)
                assert status is not None
                assert status.role == task.role_required
                
                # Clean up
                await agent_manager.kill_agent(session_id)
                await coordinator.complete_task(session_id)
                break  # Just test one agent
    
    # Final verification
    final_agents = await agent_manager.list_agents()
    assert len(final_agents) == 0


@pytest.mark.asyncio
async def test_error_handling():
    """Test system error handling."""
    # Test invalid role
    from src.orchestrator.coordinator import TaskPacket
    
    task = TaskPacket(
        id="invalid-task",
        title="Invalid task",
        description="Task with invalid role",
        role_required="nonexistent-role",
        runtime_preference=["echo"],
        priority="high"
    )
    
    # Should return None for invalid role
    session_id = await coordinator.assign_task(task)
    assert session_id is None
    
    # Test invalid runtime - should fallback to available runtime
    task.runtime_preference = ["nonexistent-runtime"]
    task.role_required = "scout"  # Valid role
    
    session_id = await coordinator.assign_task(task)
    assert session_id is not None  # Should succeed with fallback to available runtime
    
    # Test killing non-existent agent
    result = await agent_manager.kill_agent("nonexistent-session")
    assert result == False
    
    # Test getting status of non-existent agent
    status = await agent_manager.get_agent_status("nonexistent-session")
    assert status is None