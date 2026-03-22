"""
Claude Code Runtime Adapter

Uses Claude Code CLI with -p + --output-format stream-json for headless runs.
Supports resume via --resume SESSION_ID for nudges.
Enforces role contracts via --system-prompt + --allowedTools + --disallowedTools.
Provides worktree isolation via --add-dir + cwd.
"""

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import AsyncIterator

from .base import AgentRuntime, AgentConfig, AgentStatus, RuntimeCapabilities


class ClaudeCodeRuntime(AgentRuntime):
    """
    Claude Code adapter using -p + --output-format stream-json for headless runs.
    Resume support via --resume SESSION_ID for nudges.
    Role enforcement via --system-prompt + --allowedTools + --disallowedTools.
    Worktree isolation via --add-dir + cwd.
    """

    # Tool sets per role — enforces role contracts at the runtime level
    ROLE_TOOL_POLICY: dict[str, dict] = {
        "scout": {
            "allowed": ["Read", "Bash(find:*)", "Bash(grep:*)", "Bash(cat:*)",
                        "Bash(ls:*)", "Bash(tree:*)", "Bash(git:log:*)",
                        "Bash(git:diff:*)", "Bash(git:show:*)"],
            "disallowed": ["Edit", "Write", "Bash(git:commit:*)",
                           "Bash(git:push:*)", "Bash(git:merge:*)"],
        },
        "developer": {
            "allowed": ["default"],   # full tool access
            "disallowed": ["Bash(git:push:*)", "Bash(git:merge:*)"],
        },
        "builder": {
            "allowed": ["Read", "Edit", "Write", "Bash(python:*)",
                        "Bash(pytest:*)", "Bash(git:add:*)",
                        "Bash(git:status:*)", "Bash(git:diff:*)"],
            "disallowed": ["Bash(git:push:*)", "Bash(git:merge:*)",
                           "Bash(git:commit:*)"],
        },
        "tester": {
            "allowed": ["Read", "Edit", "Write", "Bash(pytest:*)",
                        "Bash(python:*)", "Bash(git:status:*)",
                        "Bash(git:diff:*)"],
            "disallowed": ["Bash(git:push:*)", "Bash(git:merge:*)",
                           "Bash(git:commit:*)"],
        },
        "reviewer": {
            "allowed": ["Read", "Bash(git:diff:*)", "Bash(git:log:*)",
                        "Bash(git:show:*)", "Bash(grep:*)", "Bash(cat:*)"],
            "disallowed": ["Edit", "Write", "Bash(git:commit:*)",
                           "Bash(git:push:*)", "Bash(git:merge:*)"],
        },
        "merger": {
            "allowed": ["Read", "Edit", "Write", "Bash(git:*)" ],
            "disallowed": [],
        },
        "monitor": {
            "allowed": ["Read", "Bash(ps:*)", "Bash(ls:*)",
                        "Bash(git:status:*)", "Bash(git:log:*)"],
            "disallowed": ["Edit", "Write", "Bash(git:commit:*)",
                           "Bash(git:push:*)", "Bash(git:merge:*)"],
        },
        "coordinator": {
            "allowed": ["Read", "Bash(ls:*)", "Bash(git:status:*)"],
            "disallowed": ["Edit", "Write", "Bash(git:commit:*)",
                           "Bash(git:push:*)", "Bash(git:merge:*)"],
        },
    }

    def __init__(self) -> None:
        self._sessions:    dict[str, asyncio.subprocess.Process] = {}
        self._session_ids: dict[str, str] = {}   # internal_id -> claude SESSION_ID
        self._configs:     dict[str, AgentConfig] = {}
        self._last_output: dict[str, str] = {}

    # ── Interface ─────────────────────────────────────────────────────────────

    @property
    def runtime_name(self) -> str:
        return "claude-code"

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            interactive_chat=True,
            headless_run=True,
            resume_session=True,
            streaming_output=True,
            tool_allowlist=True,
            sandbox_support=False,
            agent_profiles=True,
            parallel_safe=True,
        )

    # ── Spawn ─────────────────────────────────────────────────────────────────

    async def spawn(self, config: AgentConfig) -> str:
        system_prompt = self._build_system_prompt(config)
        tool_flags    = self._build_tool_flags(config)
        session_name  = f"polyglot-{config.name}-{uuid.uuid4().hex[:6]}"
        
        # Determine permission mode
        perm_mode = "readOnly" if config.read_only else "acceptEdits"

        cmd = [
            "claude",
            "--print",                          # headless mode
            "--output-format", "stream-json",   # NDJSON token stream
            "--system-prompt", system_prompt,
            "--name", session_name,
            "--permission-mode", perm_mode,
            "--add-dir", config.worktree_path,
            "--model", config.model or "sonnet",
            "--effort", self._effort_for_role(config.role),
        ] + tool_flags + [config.task]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.worktree_path,
            env={**os.environ, **(config.extra_env or {})},
        )

        session_id = f"claude-{config.name}-{proc.pid}"
        self._sessions[session_id]    = proc
        self._configs[session_id]     = config
        self._last_output[session_id] = ""
        return session_id

    # ── Nudge / resume ────────────────────────────────────────────────────────

    async def send_message(self, session_id: str, message: str) -> None:
        config = self._configs.get(session_id)
        if not config:
            return

        tool_flags    = self._build_tool_flags(config)
        system_prompt = self._build_system_prompt(config)
        claude_sid    = self._session_ids.get(session_id)

        cmd = [
            "claude",
            "--print",
            "--output-format", "stream-json",
            "--system-prompt", system_prompt,
            "--permission-mode", "acceptEdits",
            "--add-dir", config.worktree_path,
            "--model", config.model or "sonnet",
        ] + tool_flags

        # Resume the same session so it retains context
        if claude_sid:
            cmd += ["--resume", claude_sid]
        else:
            cmd += ["--continue"]

        cmd.append(message)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.worktree_path,
            env={**os.environ, **(config.extra_env or {})},
        )
        self._sessions[session_id] = proc

    # ── Stream output ─────────────────────────────────────────────────────────

    async def stream_output(self, session_id: str) -> AsyncIterator[str]:
        proc = self._sessions.get(session_id)
        if not proc or not proc.stdout:
            return

        async for raw in proc.stdout:
            line = raw.decode(errors="replace").strip()
            if not line:
                continue

            text = self._extract_text(session_id, line)
            if text:
                self._last_output[session_id] = text
                yield text

    # ── Status ────────────────────────────────────────────────────────────────

    async def get_status(self, session_id: str) -> AgentStatus:
        proc   = self._sessions.get(session_id)
        config = self._configs.get(session_id)
        role   = config.role if config else "unknown"

        if not proc:
            state = "error"
        elif proc.returncode is None:
            state = "running"
        elif proc.returncode == 0:
            state = "done"
        else:
            state = "error"

        return AgentStatus(
            name=session_id,
            role=role,
            state=state,
            current_task=config.task if config else "",
            runtime=self.runtime_name,
            last_output=self._last_output.get(session_id, ""),
            pid=proc.pid if proc else None,
        )

    # ── Kill ──────────────────────────────────────────────────────────────────

    async def kill(self, session_id: str) -> None:
        proc = self._sessions.pop(session_id, None)
        self._configs.pop(session_id, None)
        self._session_ids.pop(session_id, None)
        self._last_output.pop(session_id, None)
        if proc and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_system_prompt(self, config: AgentConfig) -> str:
        """Load role definition file + append role-lock footer."""
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
            f'{{' + '"role":"' + config.role + '","status":"done",'
            f'"summary":"...","files_changed":[],"handoff_to":"..."' + '}}'
        )
        return base + lock

    def _build_tool_flags(self, config: AgentConfig) -> list[str]:
        policy = self.ROLE_TOOL_POLICY.get(config.role, {})

        # Config-level overrides win over role defaults
        allowed    = config.allowed_tools    or policy.get("allowed", ["default"])
        disallowed = config.blocked_tools    or policy.get("disallowed", [])

        flags = []
        if allowed and allowed != ["default"]:
            flags += ["--allowedTools"] + allowed
        if disallowed:
            flags += ["--disallowedTools"] + disallowed
        return flags

    def _effort_for_role(self, role: str) -> str:
        """Map roles to effort levels — developer/reviewer get max."""
        high  = {"developer", "reviewer", "coordinator", "supervisor", "orchestrator"}
        low   = {"monitor", "scout"}
        if role in high:
            return "high"
        if role in low:
            return "low"
        return "medium"

    def _extract_text(self, session_id: str, line: str) -> str | None:
        """
        Parse stream-json NDJSON line.
        Claude Code stream-json emits objects with type field.
        Capture SESSION_ID from init event for future resumes.
        """
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return line  # pass through non-JSON lines (rare)

        event_type = obj.get("type", "")

        # Capture session ID for resume support
        if event_type == "system" and "session_id" in obj:
            self._session_ids[session_id] = obj["session_id"]
            return None

        # Text delta tokens
        if event_type in ("assistant", "text"):
            return obj.get("text") or obj.get("content") or None

        # Tool use notifications — show in output panel
        if event_type == "tool_use":
            tool = obj.get("name", "tool")
            inp  = json.dumps(obj.get("input", {}))[:80]
            return f"[tool] {tool}({inp})"

        # Tool result
        if event_type == "tool_result":
            content = obj.get("content", "")
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            return f"[result] {str(content)[:120]}" if content else None

        # Completion signal — emit structured output
        if event_type in ("result", "end_turn"):
            return None

        return None