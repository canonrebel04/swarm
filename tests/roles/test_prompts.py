import pytest
from src.roles.prompts import get_role_policy, ROLE_TOOL_POLICY

def test_get_role_policy_known_role():
    """Test that get_role_policy returns the correct policy for a known role."""
    policy = get_role_policy("developer")
    expected_policy = ROLE_TOOL_POLICY.get("developer")

    assert policy == expected_policy
    assert "allowed" in policy
    assert "blocked" in policy

def test_get_role_policy_another_known_role():
    """Test that get_role_policy returns the correct policy for another known role."""
    policy = get_role_policy("scout")
    expected_policy = ROLE_TOOL_POLICY.get("scout")

    assert policy == expected_policy
    assert "allowed" in policy
    assert "blocked" in policy

def test_get_role_policy_unknown_role():
    """Test that get_role_policy returns an empty dict for an unknown role."""
    policy = get_role_policy("unknown_role_xyz")

    assert policy == {}

def test_get_role_policy_empty_string():
    """Test that get_role_policy returns an empty dict for an empty string."""
    policy = get_role_policy("")

    assert policy == {}
