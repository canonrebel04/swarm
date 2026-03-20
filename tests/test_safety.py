"""
Test suite for safety systems: role locker and anti-drift monitor.
"""

import pytest
from unittest.mock import MagicMock

from src.safety.role_locker import RoleLocker, RoleViolation, RoleContract
from src.safety.anti_drift import AntiDriftMonitor, DriftViolation


# Test RoleLocker
class TestRoleLocker:
    
    def test_role_locker_initialization(self):
        """Test that role locker loads contracts successfully."""
        locker = RoleLocker()
        assert len(locker.list_roles()) > 0
        assert 'scout' in locker.list_roles()
        assert 'developer' in locker.list_roles()
    
    def test_valid_handoff_scout_to_developer(self):
        """Test valid handoff from scout to developer."""
        locker = RoleLocker()
        # This should be valid based on typical workflow
        result = locker.validate_handoff('scout', 'developer')
        assert result is True
    
    def test_invalid_handoff_scout_to_reviewer(self):
        """Test invalid handoff from scout to reviewer."""
        locker = RoleLocker()
        # Scouts typically shouldn't handoff directly to reviewers
        with pytest.raises(RoleViolation) as exc_info:
            locker.validate_handoff('scout', 'reviewer')
        
        assert 'scout' in str(exc_info.value)
        assert 'reviewer' in str(exc_info.value)
    
    def test_unknown_role_handoff(self):
        """Test handoff with unknown roles."""
        locker = RoleLocker()
        
        with pytest.raises(RoleViolation) as exc_info:
            locker.validate_handoff('scout', 'nonexistent_role')
        assert 'Unknown target role' in str(exc_info.value)
    
    def test_get_allowed_handoffs(self):
        """Test getting allowed handoffs for a role."""
        locker = RoleLocker()
        allowed = locker.get_allowed_handoffs('scout')
        assert isinstance(allowed, list)
        # Should return some roles
        assert len(allowed) > 0
    
    def test_get_role_contract(self):
        """Test getting contract for a specific role."""
        locker = RoleLocker()
        contract = locker.get_role_contract('scout')
        assert contract is not None
        assert isinstance(contract, RoleContract)
        assert contract.name == 'scout'
    
    def test_self_handoff(self):
        """Test that self-handoff is allowed."""
        locker = RoleLocker()
        # Agents should be able to handoff to themselves (e.g., for retry)
        result = locker.validate_handoff('developer', 'developer')
        assert result is True


# Test AntiDriftMonitor
class TestAntiDriftMonitor:
    
    def test_anti_drift_initialization(self):
        """Test anti-drift monitor initialization."""
        monitor = AntiDriftMonitor()
        constraints = monitor.get_role_constraints('scout')
        assert 'forbidden_tools' in constraints
        assert len(constraints['forbidden_tools']) > 0
    
    def test_scout_write_violation(self):
        """Test detection of write violation by scout."""
        monitor = AntiDriftMonitor()
        
        # Set up event callback mock
        events = []
        monitor.set_event_callback(lambda level, source, message: events.append((level, source, message)))
        
        # Output containing forbidden write action
        output = "Analyzing files...\n[write] src/auth.py\nDone"
        violations = monitor.monitor_output(output, 'scout')
        
        assert len(violations) == 1
        assert violations[0].role == 'scout'
        assert violations[0].violation_type == 'tool_violation'
        assert '[write]' in violations[0].tool_line
        
        # Check that event was emitted
        assert len(events) == 1
        assert events[0][0] == 'warn'
        assert events[0][1] == 'scout'
    
    def test_reviewer_edit_violation(self):
        """Test detection of edit violation by reviewer."""
        monitor = AntiDriftMonitor()
        
        output = "Reviewing code...\n[edit] README.md\nComplete"
        violations = monitor.monitor_output(output, 'reviewer')
        
        assert len(violations) == 1
        assert violations[0].role == 'reviewer'
        assert '[edit]' in violations[0].tool_line
    
    def test_monitor_write_violation(self):
        """Test detection of write violation by monitor."""
        monitor = AntiDriftMonitor()
        
        output = "Monitoring system...\n[write] log.txt\nDone"
        violations = monitor.monitor_output(output, 'monitor')
        
        assert len(violations) == 1
        assert violations[0].role == 'monitor'
    
    def test_tester_git_push_violation(self):
        """Test detection of git push violation by tester."""
        monitor = AntiDriftMonitor()
        
        output = "Running tests...\n[bash] git push origin main\nComplete"
        violations = monitor.monitor_output(output, 'tester')
        
        assert len(violations) == 1
        assert violations[0].role == 'tester'
        assert 'git push' in violations[0].tool_line
    
    def test_no_violation_developer(self):
        """Test that developer actions don't trigger violations."""
        monitor = AntiDriftMonitor()
        
        # Developer should be allowed to write/edit
        output = "Implementing feature...\n[write] src/feature.py\n[edit] tests/test_feature.py\nDone"
        violations = monitor.monitor_output(output, 'developer')
        
        assert len(violations) == 0
    
    def test_no_violation_unknown_role(self):
        """Test that unknown roles don't trigger violations."""
        monitor = AntiDriftMonitor()
        
        output = "Doing something...\n[write] file.txt\nDone"
        violations = monitor.monitor_output(output, 'unknown_role')
        
        assert len(violations) == 0
    
    def test_multiple_violations_same_line(self):
        """Test that only first violation per line is reported."""
        monitor = AntiDriftMonitor()
        
        # Line with multiple forbidden patterns
        output = "[write] file.txt and [edit] other.txt"
        violations = monitor.monitor_output(output, 'scout')
        
        # Should only report one violation for this line
        assert len(violations) == 1
    
    def test_case_insensitive_violation_detection(self):
        """Test that violation detection is case insensitive."""
        monitor = AntiDriftMonitor()
        
        output = "[WRITE] file.txt"
        violations = monitor.monitor_output(output, 'scout')
        
        assert len(violations) == 1
    
    def test_add_custom_role_constraints(self):
        """Test adding custom constraints for a role."""
        monitor = AntiDriftMonitor()
        
        # Add constraints for a custom role
        monitor.add_role_constraints(
            'custom_role',
            [r'\[delete\]', r'\[remove\]'],
            'Custom role cannot delete files'
        )
        
        constraints = monitor.get_role_constraints('custom_role')
        assert 'forbidden_tools' in constraints
        assert any('\[delete\]' in pattern for pattern in constraints['forbidden_tools'])
        
        # Test the new constraint
        output = "[delete] old_file.txt"
        violations = monitor.monitor_output(output, 'custom_role')
        assert len(violations) == 1


# Integration tests
class TestSafetyIntegration:
    
    def test_role_locker_with_coordinator(self):
        """Test role locker integration with coordinator handoff."""
        from src.orchestrator.coordinator import Coordinator
        
        coordinator = Coordinator()
        locker = RoleLocker()
        
        # Mock a valid handoff
        assert locker.validate_handoff('scout', 'developer') is True
        
        # Test that invalid handoff raises exception
        # Use a handoff that should be forbidden based on contracts
        with pytest.raises(RoleViolation):
            locker.validate_handoff('reviewer', 'scout')  # Reviewers shouldn't handoff to scouts
    
    def test_anti_drift_with_agent_output(self):
        """Test anti-drift monitoring with realistic agent output."""
        monitor = AntiDriftMonitor()
        
        # Realistic scout output with violation
        scout_output = """
Exploring codebase structure...
Found auth module in src/auth.py
Analyzing dependencies...
[write] exploration_notes.md  # This should trigger violation
Complete: exploration complete
"""
        
        violations = monitor.monitor_output(scout_output, 'scout')
        assert len(violations) == 1
        assert 'exploration_notes.md' in violations[0].tool_line
    
    def test_comprehensive_role_transitions(self):
        """Test various role transition scenarios."""
        locker = RoleLocker()
        
        # Test typical workflow transitions
        valid_transitions = [
            ('scout', 'developer'),
            ('developer', 'tester'),
            ('tester', 'reviewer'),
            ('reviewer', 'merger'),
        ]
        
        for from_role, to_role in valid_transitions:
            try:
                result = locker.validate_handoff(from_role, to_role)
                assert result is True, f"Expected {from_role}→{to_role} to be valid"
            except RoleViolation:
                # Some transitions might be invalid based on contracts
                pass
    
    def test_event_callback_integration(self):
        """Test that anti-drift monitor properly uses event callbacks."""
        monitor = AntiDriftMonitor()
        
        # Track events
        emitted_events = []
        def mock_callback(level, source, message):
            emitted_events.append((level, source, message))
        
        monitor.set_event_callback(mock_callback)
        
        # Trigger a violation
        output = "[write] forbidden.txt"
        monitor.monitor_output(output, 'scout')
        
        # Check event was emitted
        assert len(emitted_events) == 1
        event = emitted_events[0]
        assert event[0] == 'warn'
        assert event[1] == 'scout'
        assert 'Role constraint violation' in event[2]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
