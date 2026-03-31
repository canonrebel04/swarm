"""
Centralized role tool policies and system prompt helpers.

This module consolidates role tool policies that were previously duplicated
across runtime adapters (claude_code.py) and the coordinator. All modules
should import from here instead of defining their own policies.
"""

from pathlib import Path
from typing import Optional


# ── Tool Policy ──────────────────────────────────────────────────────────────
# Single source of truth for which tools each role may/may not use.
# "allowed" uses Claude Code tool names (Read, Edit, Write, Bash(cmd:*)).
# "blocked" lists tools explicitly disallowed for the role.

ROLE_TOOL_POLICY: dict[str, dict[str, list[str]]] = {
    "scout": {
        "allowed": [
            "Read",
            "Bash(find:*)",
            "Bash(grep:*)",
            "Bash(cat:*)",
            "Bash(ls:*)",
            "Bash(tree:*)",
            "Bash(git:log:*)",
            "Bash(git:diff:*)",
            "Bash(git:show:*)",
        ],
        "blocked": [
            "Edit",
            "Write",
            "Bash(git:commit:*)",
            "Bash(git:push:*)",
            "Bash(git:merge:*)",
        ],
    },
    "developer": {
        "allowed": ["default"],  # full tool access
        "blocked": ["Bash(git:push:*)", "Bash(git:merge:*)"],
    },
    "builder": {
        "allowed": [
            "Read",
            "Edit",
            "Write",
            "Bash(python:*)",
            "Bash(pytest:*)",
            "Bash(git:add:*)",
            "Bash(git:status:*)",
            "Bash(git:diff:*)",
        ],
        "blocked": [
            "Bash(git:push:*)",
            "Bash(git:merge:*)",
            "Bash(git:commit:*)",
        ],
    },
    "tester": {
        "allowed": [
            "Read",
            "Edit",
            "Write",
            "Bash(pytest:*)",
            "Bash(python:*)",
            "Bash(git:status:*)",
            "Bash(git:diff:*)",
        ],
        "blocked": [
            "Bash(git:push:*)",
            "Bash(git:merge:*)",
            "Bash(git:commit:*)",
        ],
    },
    "reviewer": {
        "allowed": [
            "Read",
            "Bash(git:diff:*)",
            "Bash(git:log:*)",
            "Bash(git:show:*)",
            "Bash(grep:*)",
            "Bash(cat:*)",
        ],
        "blocked": [
            "Edit",
            "Write",
            "Bash(git:commit:*)",
            "Bash(git:push:*)",
            "Bash(git:merge:*)",
        ],
    },
    "merger": {
        "allowed": ["Read", "Edit", "Write", "Bash(git:*)"],
        "blocked": [],
    },
    "monitor": {
        "allowed": [
            "Read",
            "Bash(ps:*)",
            "Bash(ls:*)",
            "Bash(git:status:*)",
            "Bash(git:log:*)",
        ],
        "blocked": [
            "Edit",
            "Write",
            "Bash(git:commit:*)",
            "Bash(git:push:*)",
            "Bash(git:merge:*)",
        ],
    },
    "coordinator": {
        "allowed": ["Read", "Bash(ls:*)", "Bash(git:status:*)"],
        "blocked": [
            "Edit",
            "Write",
            "Bash(git:commit:*)",
            "Bash(git:push:*)",
            "Bash(git:merge:*)",
        ],
    },
    "orchestrator": {
        "allowed": ["Read", "Bash(ls:*)", "Bash(git:status:*)"],
        "blocked": ["Edit", "Write"],
    },
    "supervisor": {
        "allowed": ["Read", "Bash(ls:*)", "Bash(git:status:*)", "Bash(git:log:*)"],
        "blocked": ["Edit", "Write", "Bash(git:push:*)"],
    },
    "lead": {
        "allowed": [
            "Read",
            "Edit",
            "Write",
            "Bash(python:*)",
            "Bash(pytest:*)",
            "Bash(git:*)",
        ],
        "blocked": ["Bash(git:push:*)"],
    },
    "arbiter": {
        "allowed": ["Read", "Bash(git:diff:*)", "Bash(git:log:*)"],
        "blocked": ["Edit", "Write", "Bash(git:commit:*)"],
    },
}


# ── Read-Only Roles ─────────────────────────────────────────────────────────
# Roles that should never write files.

ROLE_READ_ONLY: dict[str, bool] = {
    "scout": True,
    "reviewer": True,
    "monitor": True,
    "coordinator": True,
    "orchestrator": True,
    "arbiter": True,
}


# ── Effort Levels ───────────────────────────────────────────────────────────
# Map roles to effort levels for runtimes that support it.

ROLE_EFFORT: dict[str, str] = {
    "developer": "high",
    "reviewer": "high",
    "coordinator": "high",
    "supervisor": "high",
    "orchestrator": "high",
    "lead": "high",
    "scout": "low",
    "monitor": "low",
}

DEFAULT_EFFORT = "medium"


def get_role_policy(role: str) -> dict[str, list[str]]:
    """Get the tool policy for a role. Returns empty dict if unknown."""
    return ROLE_TOOL_POLICY.get(role, {})


def is_read_only(role: str) -> bool:
    """Check if a role is read-only."""
    return ROLE_READ_ONLY.get(role, False)


def get_effort(role: str) -> str:
    """Get the effort level for a role."""
    return ROLE_EFFORT.get(role, DEFAULT_EFFORT)


def build_system_prompt(config) -> str:
    """
    Build a system prompt from the role definition file + role-lock footer.

    Args:
        config: AgentConfig with system_prompt_path, name, role attributes.
    """
    base = ""
    p = Path(config.system_prompt_path)
    if p.exists():
        base = p.read_text()

    lock = (
        f"\n\n---\n"
        f"ROLE CONTRACT (non-negotiable):\n"
        f"You are {config.name}, a {config.role} agent.\n"
        f"You must stay within your role. Do not self-reassign.\n"
        f"Do not perform actions reserved for other roles.\n"
        f"When your task is complete, output a structured JSON summary:\n"
        f'{{"role":"{config.role}","status":"done",'
        f'"summary":"...","files_changed":[],"handoff_to":"..."}}'
    )
    return base + lock


def build_claude_tool_flags(config) -> list[str]:
    """
    Build Claude Code CLI --allowedTools / --disallowedTools flags.

    Config-level overrides take precedence over role defaults.
    """
    policy = ROLE_TOOL_POLICY.get(config.role, {})

    allowed = config.allowed_tools or policy.get("allowed", ["default"])
    blocked = config.blocked_tools or policy.get("blocked", [])

    flags: list[str] = []
    if allowed and allowed != ["default"]:
        flags += ["--allowedTools"] + allowed
    if blocked:
        flags += ["--disallowedTools"] + blocked
    return flags
