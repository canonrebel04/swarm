import pytest
from src.roles.prompts import get_effort, ROLE_EFFORT, DEFAULT_EFFORT

def test_get_effort_known_role_high():
    """Test get_effort with a known role that has high effort."""
    assert get_effort("developer") == "high"
    assert get_effort("developer") == ROLE_EFFORT["developer"]

def test_get_effort_known_role_low():
    """Test get_effort with a known role that has low effort."""
    assert get_effort("scout") == "low"
    assert get_effort("scout") == ROLE_EFFORT["scout"]

def test_get_effort_unknown_role():
    """Test get_effort with an unknown role returns default effort."""
    assert get_effort("unknown_role") == "medium"
    assert get_effort("unknown_role") == DEFAULT_EFFORT
