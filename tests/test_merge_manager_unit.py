"""
Unit tests for MergeManager component.

This module tests the merge manager's core logic without event bus dependencies.
"""

import pytest
import subprocess
from unittest.mock import Mock, patch
from src.orchestrator.merge_manager import MergeManager, HandoffEvent
from src.orchestrator.coordinator import Coordinator


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
def merge_manager(mock_coordinator):
    """Create a MergeManager instance for testing."""
    # Mock the event bus to prevent actual subscriptions
    with patch('src.orchestrator.merge_manager.event_bus'):
        manager = MergeManager(mock_coordinator)
        return manager


def test_handoff_event_parsing(merge_manager, sample_handoff):
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


def test_merge_task_creation(merge_manager, sample_handoff):
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


def test_merge_completion_handling(merge_manager):
    """Test merge completion event handling."""
    # Add an active merge
    merge_manager.active_merges["Test Task"] = "agent-merger-1"
    
    event_data = {
        "data": {
            "task_title": "Test Task"
        }
    }
    
    # Mock event_bus.emit
    with patch('src.orchestrator.merge_manager.event_bus.emit'):
        merge_manager._handle_merge_completion(event_data)
        
        # Should clean up active merges
        assert "Test Task" not in merge_manager.active_merges


def test_edge_case_no_active_merges(merge_manager):
    """Test handling merge completion for non-existent merge."""
    event_data = {
        "data": {
            "task_title": "Non-existent Task"
        }
    }
    
    # Mock emit method
    with patch.object(merge_manager, 'emit'):
        merge_manager._handle_merge_completion(event_data)
        
        # Should not crash
        assert True


def test_edge_case_multiple_conflicts(merge_manager, sample_handoff):
    """Test handling of multiple conflicts."""
    conflicts = ["file1.py", "file2.py", "file3.py", "file4.py", "file5.py"]
    
    # Mock coordinator
    merge_manager.coordinator.assign_task = Mock(return_value="agent-merger-1")
    
    # Mock emit method
    with patch.object(merge_manager, 'emit'):
        merge_manager._handle_merge_conflicts(sample_handoff, conflicts)
        
        # Should create task with truncated conflict list
        merge_task = merge_manager._create_merge_task(sample_handoff, conflicts)
        assert "file1.py, file2.py, file3.py..." in merge_task.description
        assert merge_task.files_in_scope == conflicts


def test_error_handling_in_handoff(merge_manager):
    """Test error handling in handoff event processing."""
    event_data = {
        "data": {
            "from_agent": "agent-scout-1",
            "status": "done",
            "task_title": "Implement authentication"
            # Missing required fields
        }
    }
    
    # Mock emit method
    with patch.object(merge_manager, 'emit'):
        merge_manager._handle_handoff_event(event_data)
        
        # Should not crash
        assert True


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
        with patch('src.orchestrator.agent_manager.agent_manager.list_agents', return_value=[mock_agent]):
            conflicts = await merge_manager._check_for_conflicts(sample_handoff)
            
            # Should detect conflicts
            assert len(conflicts) == 2
            assert "src/auth.py" in conflicts
            assert "src/config.py" in conflicts


def test_merger_assignment(merge_manager, sample_handoff):
    """Test merger agent assignment for conflicts."""
    conflicts = ["src/auth.py", "src/config.py"]
    
    # Mock coordinator
    merge_manager.coordinator.assign_task = Mock(return_value="agent-merger-1")
    
    # Mock emit method
    with patch.object(merge_manager, 'emit'):
        merge_manager._handle_merge_conflicts(sample_handoff, conflicts)
        
        # Verify merger was assigned
        assert "Implement authentication" in merge_manager.active_merges
        assert merge_manager.active_merges["Implement authentication"] == "agent-merger-1"


def test_simple_conflict_check_fallback(merge_manager, sample_handoff):
    """Test fallback to simple conflict detection when CodebaseIndex unavailable."""
    # Mock the import to raise ImportError
    with patch.dict('sys.modules', {'src.memory.codebase_index': None}):
        with patch('src.orchestrator.agent_manager.agent_manager.list_agents', return_value=[]):
            with patch.object(merge_manager, 'emit'):
                conflicts = merge_manager._check_for_conflicts(sample_handoff)
                
                # Should return empty list (no conflicts detected in simple mode)
                assert conflicts == []


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
    
    # Mock process_completed_handoff
    with patch.object(merge_manager, 'process_completed_handoff'):
        # Mock event_bus.emit to prevent actual event emission
        with patch('src.orchestrator.merge_manager.event_bus.emit'):
            # Since _handle_handoff_event is async, we need to await it
            async def mock_handle(event):
                pass
            
            merge_manager._handle_handoff_event = mock_handle
            await merge_manager._handle_handoff_event(event_data)
        
        # Should call process_completed_handoff
        merge_manager.process_completed_handoff.assert_called_once()
        
        # Verify the handoff object was created correctly
        handoff_arg = merge_manager.process_completed_handoff.call_args[0][0]
        assert handoff_arg.from_agent == "agent-scout-1"
        assert handoff_arg.status == "done"


def test_clean_merge_scenario(merge_manager, sample_handoff):
    """Test auto-merge logic without event bus."""
    # Mock the conflict check to return no conflicts
    with patch.object(merge_manager, '_check_for_conflicts', return_value=[]):
        # Mock worktree manager
        with patch('src.orchestrator.merge_manager.worktree_manager') as mock_worktree:
            mock_worktree.get_worktree_path.return_value = "/tmp/worktree"
            
            # Mock subprocess for git merge
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(stdout="Merge successful", returncode=0)
                
                # Mock worktree cleanup
                with patch.object(merge_manager, '_cleanup_worktree'):
                    with patch.object(merge_manager, '_update_worktree_snapshot'):
                        with patch.object(merge_manager, 'emit'):
                            merge_manager.process_completed_handoff(sample_handoff)
                            
                            # Verify git merge was called correctly
                            mock_subprocess.assert_called_once()
                            call_args = mock_subprocess.call_args[0][0]
                            assert call_args[0] == "git"
                            assert call_args[1] == "merge"
                            assert call_args[2] == "--no-ff"
                            assert call_args[3] == "-m"
                            assert call_args[4] == "Auto-merge: Implement authentication"
                            assert call_args[5] == "main"


def test_auto_merge_failure_fallback(merge_manager, sample_handoff):
    """Test fallback to manual merge when auto-merge fails."""
    # Mock conflict check to return no conflicts initially
    with patch.object(merge_manager, '_check_for_conflicts', return_value=[]):
        # Mock worktree manager
        with patch('src.orchestrator.merge_manager.worktree_manager') as mock_worktree:
            mock_worktree.get_worktree_path.return_value = "/tmp/worktree"
            
            # Mock subprocess to fail
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.side_effect = subprocess.CalledProcessError(1, 'git', output="Conflict detected")
                
                # Mock conflict handling
                with patch.object(merge_manager, '_handle_merge_conflicts'):
                    with patch.object(merge_manager, 'emit'):
                        merge_manager.process_completed_handoff(sample_handoff)
                        
                        # Should fall back to manual merge
                        merge_manager._handle_merge_conflicts.assert_called_once()
                        call_args = merge_manager._handle_merge_conflicts.call_args[0]
                        assert call_args[0] == sample_handoff
                        assert "auto-merge_failed" in call_args[1]


def test_edge_case_empty_conflicts(merge_manager, sample_handoff):
    """Test handling of empty conflicts list."""
    with patch.object(merge_manager, '_check_for_conflicts', return_value=[]):
        with patch('src.orchestrator.merge_manager.worktree_manager') as mock_worktree:
            mock_worktree.get_worktree_path.return_value = "/tmp/worktree"
            
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(stdout="Merge successful", returncode=0)
                
                with patch.object(merge_manager, '_cleanup_worktree'):
                    with patch.object(merge_manager, '_update_worktree_snapshot'):
                        with patch.object(merge_manager, 'emit'):
                            merge_manager.process_completed_handoff(sample_handoff)
                            
                            # Should proceed with auto-merge
                            mock_subprocess.assert_called_once()


def test_edge_case_missing_worktree(merge_manager, sample_handoff):
    """Test handling of missing worktree."""
    with patch.object(merge_manager, '_check_for_conflicts', return_value=[]):
        with patch('src.orchestrator.merge_manager.worktree_manager') as mock_worktree:
            mock_worktree.get_worktree_path.return_value = None
            
            with patch.object(merge_manager, 'emit'):
                merge_manager.process_completed_handoff(sample_handoff)
                
                # Should not crash
                assert True


def test_edge_case_subprocess_error(merge_manager, sample_handoff):
    """Test handling of subprocess errors during merge."""
    with patch.object(merge_manager, '_check_for_conflicts', return_value=[]):
        with patch('src.orchestrator.merge_manager.worktree_manager') as mock_worktree:
            mock_worktree.get_worktree_path.return_value = "/tmp/worktree"
            
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.side_effect = Exception("Unexpected error")
                
                with patch.object(merge_manager, '_handle_merge_conflicts'):
                    with patch.object(merge_manager, 'emit'):
                        merge_manager.process_completed_handoff(sample_handoff)
                        
                        # Should fall back to manual merge
                        merge_manager._handle_merge_conflicts.assert_called_once()


def test_edge_case_no_active_merges(merge_manager):
    """Test handling merge completion for non-existent merge."""
    event_data = {
        "data": {
            "task_title": "Non-existent Task"
        }
    }
    
    with patch.object(merge_manager, 'emit'):
        merge_manager._handle_merge_completion(event_data)
        
        # Should not emit any events or crash
        assert True
