"""
Unified tool policy enforcement layer.

This module provides real-time enforcement of role tool policies.
It validates tool invocations before they are executed, blocking
actions that violate the role's contract.

Usage:
    enforcer = ToolPolicyEnforcer()
    allowed, reason = enforcer.validate_action("scout", "Edit")
    # -> (False, "Scout cannot use Edit")
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
from ..roles.prompts import ROLE_TOOL_POLICY, ROLE_READ_ONLY


@dataclass
class PolicyDecision:
    """Result of a policy check."""

    allowed: bool
    role: str
    tool: str
    reason: str


class ToolPolicyEnforcer:
    """
    Validates tool invocations against role policies.

    This sits between the agent output parser and the actual execution,
    blocking any action that violates the role's tool policy.
    """

    def __init__(self) -> None:
        self._violations: list[PolicyDecision] = []
        self._alert_callbacks: list = []

    def register_alert_callback(self, callback) -> None:
        """Register a callback for policy violation alerts."""
        self._alert_callbacks.append(callback)

    def validate_action(self, role: str, tool: str) -> PolicyDecision:
        """
        Check whether a role is allowed to use a specific tool.

        Args:
            role: The agent's role name.
            tool: The tool name (e.g., "Edit", "Write", "Bash(git:push:*)").

        Returns:
            PolicyDecision with allowed flag and reason.
        """
        policy = ROLE_TOOL_POLICY.get(role)

        if policy is None:
            # Unknown role — allow by default (no policy to enforce)
            return PolicyDecision(
                allowed=True,
                role=role,
                tool=tool,
                reason=f"No policy defined for role '{role}'",
            )

        blocked = policy.get("blocked", [])
        allowed = policy.get("allowed", [])

        # Check explicit block list first
        for pattern in blocked:
            if self._matches_pattern(tool, pattern):
                decision = PolicyDecision(
                    allowed=False,
                    role=role,
                    tool=tool,
                    reason=f"{role} is blocked from using {tool} (matches {pattern})",
                )
                self._record_violation(decision)
                return decision

        # Check allow list
        if allowed == ["default"]:
            # "default" means full access
            return PolicyDecision(
                allowed=True,
                role=role,
                tool=tool,
                reason="Role has default (full) access",
            )

        for pattern in allowed:
            if self._matches_pattern(tool, pattern):
                return PolicyDecision(
                    allowed=True,
                    role=role,
                    tool=tool,
                    reason=f"Tool {tool} is in {role}'s allow list",
                )

        # Not in allow list — deny
        decision = PolicyDecision(
            allowed=False,
            role=role,
            tool=tool,
            reason=f"{tool} is not in {role}'s allow list",
        )
        self._record_violation(decision)
        return decision

    def validate_write_action(self, role: str, filepath: str) -> PolicyDecision:
        """
        Check whether a role is allowed to write to a file path.

        Read-only roles are never allowed to write.
        """
        if ROLE_READ_ONLY.get(role, False):
            decision = PolicyDecision(
                allowed=False,
                role=role,
                tool=f"Write({filepath})",
                reason=f"{role} is a read-only role and cannot write files",
            )
            self._record_violation(decision)
            return decision

        return self.validate_action(role, "Write")

    def get_violations(self, clear: bool = False) -> list[PolicyDecision]:
        """Get recorded violations. Optionally clear the buffer."""
        violations = list(self._violations)
        if clear:
            self._violations.clear()
        return violations

    def _record_violation(self, decision: PolicyDecision) -> None:
        """Record a violation and fire alert callbacks."""
        if not decision.allowed:
            self._violations.append(decision)
            for cb in self._alert_callbacks:
                try:
                    cb(decision)
                except Exception:
                    pass

    @staticmethod
    def _matches_pattern(tool: str, pattern: str) -> bool:
        """
        Match a tool name against a policy pattern.

        Patterns:
            "Edit"          — exact match
            "Bash(git:*)"   — Bash subcommand wildcard
            "Bash(git:push:*)" — nested wildcard
        """
        if pattern == tool:
            return True
        if "*" in pattern:
            prefix = pattern.rstrip("*")
            return tool.startswith(prefix)
        return False


# Global instance
enforcer = ToolPolicyEnforcer()
