"""
Simplified test suite for MergeManager component.

This module tests the merge manager's core functionality without complex async fixtures.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import subprocess
import tempfile
import os

from src.orchestrator.merge_manager import MergeManager, HandoffEvent
from src.orchestrator.coordinator import Coordinator
from src.messaging.event_bus import EventBus


@pytest.fixture
def sample_handoff():
    """Create a sample handoff event."""
    return HandoffEvent(
        from_agent="agent-scout-1",
        to_agent="agent-builder-1",
        status="done",
        task_title="Implement authentication",
        worktree_branch="feature/auth",
        data={
            "from_agent": "agent-scout-1",
            "to_agent": "agent-builder-1",
            "status": "done",
            "task_title": "Implement authentication",
            "worktree_branch": "feature/auth"
        }
    )


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for testing."""
    return Mock(spec=Coordinator)


@pytest.fixture
async def event_bus():
    """Create a test event bus with clean database."""
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Create event bus with test database
        bus = EventBus(db_path)
        await bus.db.connect()
        await bus.clear_events()
        yield bus
    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
async def merge_manager(mock_coordinator, event_bus):
    """Create a MergeManager instance for testing."""
    # Replace global event_bus temporarily
    from src.messaging import event_bus as global_event_bus_module
    original_event_bus = global_event_bus_module.event_bus
    global_event_bus_module.event_bus = event_bus
    
    manager = MergeManager(mock_coordinator)
    
    yield manager
    
    # Restore original event_bus
    global_event_bus_module.event_bus = original_event_bus


@pytest.mark.asyncio
async def test_handoff_event_parsing(merge_manager, sample_handoff):
    """Test that handoff events are parsed correctly."""
    event_data = {
        "data": {
            "from_agent": "agent-scout-1",
            "to_agent": "agent-builder-1", 
            "status": "done",
            "task_title": "Implement authentication",
            "worktree_branch": "feature/auth"
        }
    }
    
    parsed = merge_manager._parse_handoff_event(event_data)
    
    assert parsed.from_agent == "agent-scout-1"
    assert parsed.to_agent == "agent-builder-1"
    assert parsed.status == "done"
    assert parsed.task_title == "Implement authentication"
    assert parsed.worktree_branch == "feature/auth"


@pytest.mark.asyncio
async def test_merge_task_creation(merge_manager, sample_handoff):
    """Test merge task creation for merger agents."""
    conflicts = ["src/auth.py", "src/config.py", "src/utils.py"]
    
    merge_task = merge_manager._create_merge_task(sample_handoff, conflicts)
    
    # Verify task structure
    assert merge_task.title == "Resolve merge conflicts in Implement authentication"
    assert "Resolve conflicts in files: src/auth.py, src/config.py, src/utils.py" in merge_task.description
    assert merge_task.role_required == "merger"
    assert merge_task.runtime_preference == ["mistral-vibe", "openclaw"]
    assert merge_task.priority == "high"
    assert merge_task.files_in_scope == ["src/auth.py", "src/config.py", "src/utils.py"]
    assert merge_task.parent_agent == "agent-scout-1"


@pytest.mark.asyncio
async def test_handoff_event_handling(merge_manager):
    """Test complete handoff event handling flow."""
    event_data = {
        "data": {
            "from_agent": "agent-scout-1",
            "to_agent": "agent-builder-1", 
            "status": "done",
            "task_title": "Implement authentication",
            "worktree_branch": "feature/auth"
        }
    }
    
    with patch.object(merge_manager, 'process_completed_handoff', new_callable=AsyncMock) as mock_process:
        await merge_manager._handle_handoff_event(event_data)
        
        # Should call process_completed_handoff
        mock_process.assert_called_once()
        
        # Verify the handoff object was created correctly
        handoff_arg = mock_process.call_args[0][0]
        assert handoff_arg.from_agent == "agent-scout-1"
        assert handoff_arg.status == "done"


@pytest.mark.asyncio
async def test_merge_completion_handling(merge_manager):
    """Test merge completion event handling."""
    # Add an active merge
    merge_manager.active_merges["Test Task"] = "agent-merger-1"
    
    event_data = {
        "data": {
            "task_title": "Test Task"
        }
    }
    
    with patch.object(merge_manager, 'emit', new_callable=AsyncMock) as mock_emit:
        await merge_manager._handle_merge_completion(event_data)
        
        # Should emit merge success event
        mock_emit.assert_called_once_with(
            "merge_success", "merge-manager",
            {
                "message": "Merge completed for Test Task",
                "task_title": "Test Task"
            }
        )
        
        # Should clean up active merges
        assert "Test Task" not in merge_manager.active_merges


@pytest.mark.asyncio
async def test_edge_case_no_active_merges(merge_manager):
    """Test handling merge completion for non-existent merge."""
    event_data = {
        "data": {
            "task_title": "Non-existent Task"
        }
    }
    
    with patch.object(merge_manager, 'emit', new_callable=AsyncMock) as mock_emit:
        await merge_manager._handle_merge_completion(event_data)
        
        # Should not emit any events or crash
        # No merge_success event should be emitted
        success_calls = [call for call in mock_emit.call_args_list 
                       if call[0][0] == "merge_success"]
        assert len(success_calls) == 0


@pytest.mark.asyncio
async def test_edge_case_multiple_conflicts(merge_manager, sample_handoff):
    """Test handling of multiple conflicts."""
    conflicts = ["file1.py", "file2.py", "file3.py", "file4.py", "file5.py"]
    
    # Mock coordinator
    merge_manager.coordinator.assign_task = AsyncMock(return_value="agent-merger-1")
    
    with patch.object(merge_manager, 'emit', new_callable=AsyncMock):
        await merge_manager._handle_merge_conflicts(sample_handoff, conflicts)
        
        # Should create task with truncated conflict list
        merge_task = merge_manager._create_merge_task(sample_handoff, conflicts)
        assert "file1.py, file2.py, file3.py..." in merge_task.description
        assert merge_task.files_in_scope == conflicts


@pytest.mark.asyncio
async def test_error_handling_in_handoff(merge_manager):
    """Test error handling in handoff event processing."""
    event_data = {
        "data": {
            "from_agent": "agent-scout-1",
            "status": "done",
            "task_title": "Implement authentication"
            # Missing required fields
        }
    }
    
    with patch.object(merge_manager, 'emit', new_callable=AsyncMock) as mock_emit:
        await merge_manager._handle_handoff_event(event_data)
        
        # Should emit error event
        error_calls = [call for call in mock_emit.call_args_list 
                     if call[0][0] == "error"]
        assert len(error_calls) > 0
        assert "Failed to handle handoff" in str(error_calls[0])


@pytest.mark.asyncio
async def test_clean_merge_scenario(merge_manager, sample_handoff):
    """Test auto-merge works with git merge --no-ff."""
    # Mock the conflict check to return no conflicts
    with patch.object(merge_manager, '_check_for_conflicts', new_callable=AsyncMock) as mock_conflict_check:
        mock_conflict_check.return_value = []
        
        # Mock worktree manager
        with patch('src.orchestrator.merge_manager.worktree_manager') as mock_worktree:
            mock_worktree.get_worktree_path.return_value = "/tmp/worktree"
            
            # Mock subprocess for git merge
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(stdout="Merge successful", returncode=0)
                
                # Mock worktree cleanup
                with patch.object(merge_manager, '_cleanup_worktree', new_callable=AsyncMock):
                    with patch.object(merge_manager, '_update_worktree_snapshot', new_callable=AsyncMock):
                        with patch('src.messaging.event_bus.event_bus.emit', new_callable=AsyncMock):
                            await merge_manager.process_completed_handoff(sample_handoff)
                            
                            # Verify git merge was called correctly
                            mock_subprocess.assert_called_once()
                            call_args = mock_subprocess.call_args[0][0]
                            assert call_args[0] == "git"
                            assert call_args[1] == "merge"
                            assert call_args[2] == "--no-ff"
                            assert call_args[3] == "-m"
                            assert call_args[4] == "Auto-merge: Implement authentication"
                            assert call_args[5] == "main"


@pytest.mark.asyncio
async def test_conflict_detection(merge_manager, sample_handoff):
    """Test conflict detection using CodebaseIndex."""
    # Mock CodebaseIndex module
    mock_index = Mock()
    mock_index.conflict_check.return_value = ["src/auth.py", "src/config.py"]
    
    # Mock agent manager
    mock_agent = Mock()
    mock_agent.config.name = "agent-builder-1"
    
    # Mock the import and instantiation
    with patch.dict('sys.modules', {'src.memory.codebase_index': Mock(CodebaseIndex=Mock(return_value=mock_index))}):
        with patch('src.orchestrator.agent_manager.agent_manager.get_all_agents', return_value=[mock_agent]):
            conflicts = await merge_manager._check_for_conflicts(sample_handoff)
            
            # Should detect conflicts
            assert len(conflicts) == 2
            assert "src/auth.py" in conflicts
            assert "src/config.py" in conflicts


@pytest.mark.asyncio
async def test_merger_assignment(merge_manager, sample_handoff):
    """Test merger agent assignment for conflicts."""
    conflicts = ["src/auth.py", "src/config.py"]
    
    # Mock coordinator
    merge_manager.coordinator.assign_task = AsyncMock(return_value="agent-merger-1")
    
    with patch.object(merge_manager, 'emit', new_callable=AsyncMock):
        await merge_manager._handle_merge_conflicts(sample_handoff, conflicts)
        
        # Verify merger was assigned
        assert "Implement authentication" in merge_manager.active_merges
        assert merge_manager.active_merges["Implement authentication"] == "agent-merger-1"
        
        # Verify correct event was emitted
        await merge_manager.emit.assert_any_call(
            "merge_conflict", "merge-manager", 
            {
                "task_title": "Implement authentication",
                "conflicting_files": ["src/auth.py", "src/config.py"],
                "from_agent": "agent-scout-1",
                "to_agent": "agent-builder-1"
            }
        )
