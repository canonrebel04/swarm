"""
Filesystem access controls per role.

This module enforces per-role filesystem boundaries, preventing
agents from reading or writing files outside their authorized scope.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional
from ..roles.prompts import ROLE_READ_ONLY
from ..messaging.event_bus import event_bus


# Directories that no agent may access regardless of role
BLOCKED_PATHS = {
    ".git/config",
    ".git/HEAD",
    ".env",
    ".swarm/data/swarm.db",
    "/etc",
    "/proc",
    "/sys",
}

# Directories that are always allowed for reading
SAFE_READ_DIRS = {
    "src/",
    "tests/",
    "docs/",
    "config.yaml",
    "pyproject.toml",
    "README.md",
}


@dataclass
class FsAccessDecision:
    """Result of a filesystem access check."""

    allowed: bool
    role: str
    operation: str  # "read" or "write"
    path: str
    reason: str


class FilesystemGuard:
    """
    Enforces per-role filesystem boundaries.

    - Read-only roles can never write.
    - All roles are blocked from accessing sensitive paths.
    - Write operations on critical files (pyproject.toml, config.yaml)
      are restricted to developer/builder/lead roles.
    """

    CRITICAL_FILES = {
        "pyproject.toml",
        "config.yaml",
        "poetry.lock",
    }

    WRITE_ALLOWED_ROLES = {
        "developer",
        "builder",
        "lead",
        "merger",
        "tester",
    }

    def __init__(self, worktree_root: str = ".swarm/worktrees") -> None:
        self.worktree_root = worktree_root
        self._violations: list[FsAccessDecision] = []

    def check_read(self, role: str, path: str) -> FsAccessDecision:
        """Check if a role can read a given path."""
        normalized = self._normalize_path(path)

        # Block sensitive paths for everyone
        if self._is_blocked(normalized):
            decision = FsAccessDecision(
                allowed=False,
                role=role,
                operation="read",
                path=path,
                reason=f"Path {path} is in the blocked list",
            )
            self._violations.append(decision)
            return decision

        # Everyone can read non-blocked files
        return FsAccessDecision(
            allowed=True,
            role=role,
            operation="read",
            path=path,
            reason="Read allowed for all roles on non-blocked paths",
        )

    def check_write(self, role: str, path: str) -> FsAccessDecision:
        """Check if a role can write to a given path."""
        normalized = self._normalize_path(path)

        # Block sensitive paths for everyone
        if self._is_blocked(normalized):
            decision = FsAccessDecision(
                allowed=False,
                role=role,
                operation="write",
                path=path,
                reason=f"Path {path} is in the blocked list",
            )
            self._violations.append(decision)
            return decision

        # Read-only roles can never write
        if ROLE_READ_ONLY.get(role, False):
            decision = FsAccessDecision(
                allowed=False,
                role=role,
                operation="write",
                path=path,
                reason=f"{role} is a read-only role",
            )
            self._violations.append(decision)
            return decision

        # Critical files restricted to specific roles
        basename = os.path.basename(normalized)
        if basename in self.CRITICAL_FILES and role not in self.WRITE_ALLOWED_ROLES:
            decision = FsAccessDecision(
                allowed=False,
                role=role,
                operation="write",
                path=path,
                reason=f"Critical file {basename} requires elevated role",
            )
            self._violations.append(decision)
            return decision

        return FsAccessDecision(
            allowed=True,
            role=role,
            operation="write",
            path=path,
            reason="Write allowed",
        )

    def get_violations(self, clear: bool = False) -> list[FsAccessDecision]:
        """Get recorded violations."""
        violations = list(self._violations)
        if clear:
            self._violations.clear()
        return violations

    def _normalize_path(self, path: str) -> str:
        """Normalize a path to prevent traversal attacks."""
        return os.path.normpath(path)

    def _is_blocked(self, normalized_path: str) -> bool:
        """Check if a path is in the blocked list."""
        for blocked in BLOCKED_PATHS:
            if normalized_path == blocked or normalized_path.endswith(f"/{blocked}"):
                return True
            if normalized_path.startswith(f"{blocked}/"):
                return True
        return False


# Global instance
fs_guard = FilesystemGuard()
