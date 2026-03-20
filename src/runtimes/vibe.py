import asyncio
import json
import os
from pathlib import Path
from typing import AsyncIterator

from .base import AgentRuntime, AgentConfig, AgentStatus, RuntimeCapabilities


class VibeRuntime(AgentRuntime):
    """
    Mistral Vibe adapter.
    Confirmed tool names from stream-json output:
      - bash        (single tool, command as argument — cannot glob-restrict by subcommand)
      - read_file
      - write_file
      - edit_file
      - list_directory
      - search_files

    Strategy:
      - scout/reviewer: no bash (read-only tools only) + prompt-level contract
      - builder/tester/monitor: bash allowed + file tools
      - developer/merger: unrestricted (no --enabled-tools flags at all)
      - All roles: system prompt role-lock footer injected into task prompt
    """

    # Built-in Vibe agents — mapped by role behavior profile
    ROLE_AGENT_MAP: dict[str, str] = {
        "scout":        "plan",           # read-only exploration
        "coordinator":  "plan",
        "supervisor":   "plan",
        "lead":         "plan",
        "developer":    "auto-approve",   # full execution, all tools auto-approved
        "builder":      "accept-edits",   # file edits auto-approved, bash manual
        "tester":       "accept-edits",
        "reviewer":     "default",        # manual approval — reviewers must be careful
        "merger":       "auto-approve",
        "monitor":      "default",
        "orchestrator": "plan",
    }

    # Verified tool names from stream-json output analysis
    # Empty list = no --enabled-tools flags = all tools available
    ROLE_TOOL_POLICY: dict[str, list[str]] = {
        "scout": [
            "read_file",
            "list_directory",
            "search_files",
            # bash intentionally excluded — cannot restrict to read-only subcommands
            # role contract prompt enforces read-only behavior as soft layer
        ],
        "reviewer": [
            "read_file",
            "list_directory",
            "search_files",
            # bash excluded — reviewer must never modify files
        ],
        "coordinator": [
            "read_file",
            "list_directory",
        ],
        "supervisor": [
            "read_file",
            "list_directory",
            "search_files",
        ],
        "lead": [
            "read_file",
            "list_directory",
            "search_files",
        ],
        "builder": [
            "read_file",
            "write_file",
            "edit_file",
            "list_directory",
            "search_files",
            "bash",   # needed: pytest, pip, git add, git status
        ],
        "tester": [
            "read_file",
            "write_file",
            "edit_file",
            "list_directory",
            "search_files",
            "bash",   # needed: pytest, python -m, coverage
        ],
        "monitor": [
            "read_file",
            "list_directory",
            "bash",   # needed: ps, git log, git status
        ],
        "developer": [],   # unrestricted — empty = all tools enabled
        "merger":    [],   # unrestricted — needs full git tooling
        "orchestrator": [
            "read_file",
            "list_directory",
        ],
    }

    # Cost caps per role — scouts are cheap reads, developers can run long
    ROLE_MAX_PRICE: dict[str, float] = {
        "scout":        0.15,
        "reviewer":     0.20,
        "coordinator":  0.15,
        "supervisor":   0.20,
        "lead":         0.25,
        "builder":      0.75,
        "tester":       0.50,
        "monitor":      0.10,
        "developer":    1.00,
        "merger":       0.60,
        "orchestrator": 0.20,
    }

    # Max turns per role — planners need fewer, builders need more
    ROLE_MAX_TURNS: dict[str, int] = {
        "scout":        20,
        "reviewer":     15,
        "coordinator":  10,
        "supervisor":   10,
        "lead":         15,
        "builder":      60,
        "tester":       40,
        "monitor":      10,
        "developer":    80,
        "merger":       30,
        "orchestrator": 10,
    }

    def __init__(self) -> None:
        self._sessions:    dict[str, asyncio.subprocess.Process] = {}
        self._session_ids: dict[str, str] = {}   # internal_id → vibe SESSION_ID
        self._configs:     dict[str, AgentConfig] = {}
        self._last_output: dict[str, str] = {}
        self._event_callback = None              # optional: push events to TUI

    # ── Interface ──────────────────────────────────────────────────────────────

    @property
    def runtime_name(self) -> str:
        return "vibe"

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

    # ── Spawn ──────────────────────────────────────────────────────────────────

    async def spawn(self, config: AgentConfig) -> str:
        tool_flags  = self._build_tool_flags(config)
        agent_name  = self.ROLE_AGENT_MAP.get(config.role, "default")
        max_price   = self.ROLE_MAX_PRICE.get(config.role, 0.50)
        max_turns   = self.ROLE_MAX_TURNS.get(config.role, 40)
        full_prompt = self._build_full_prompt(config)

        cmd = [
            "vibe",
            "-p", full_prompt,
            "--output", "streaming",
            "--agent", agent_name,
            "--max-turns", str(max_turns),
            "--max-price", str(max_price),
            "--workdir", config.worktree_path,
        ] + tool_flags

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.worktree_path,
            env={**os.environ, **(config.extra_env or {})},
        )

        session_id = f"vibe-{config.name}-{proc.pid}"
        self._sessions[session_id]    = proc
        self._configs[session_id]     = config
        self._last_output[session_id] = ""

        if self._event_callback:
            self._event_callback(
                "spawn", config.name,
                f"spawned as {config.role} via vibe ({agent_name} agent)"
            )

        return session_id

    # ── Nudge / resume ─────────────────────────────────────────────────────────

    async def send_message(self, session_id: str, message: str) -> None:
        config = self._configs.get(session_id)
        if not config:
            return

        tool_flags = self._build_tool_flags(config)
        agent_name = self.ROLE_AGENT_MAP.get(config.role, "default")
        max_price  = self.ROLE_MAX_PRICE.get(config.role, 0.50)
        vibe_sid   = self._session_ids.get(session_id)

        cmd = [
            "vibe",
            "-p", message,
            "--output", "streaming",
            "--agent", agent_name,
            "--max-turns", "20",
            "--max-price", str(max_price),
            "--workdir", config.worktree_path,
        ] + tool_flags

        # Vibe supports partial SESSION_ID matching
        if vibe_sid:
            cmd += ["--resume", vibe_sid[:8]]
        else:
            cmd += ["--continue"]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.worktree_path,
            env={**os.environ, **(config.extra_env or {})},
        )
        self._sessions[session_id] = proc

    # ── Stream output ──────────────────────────────────────────────────────────

    async def stream_output(self, session_id: str) -> AsyncIterator[str]:
        proc = self._sessions.get(session_id)
        if not proc or not proc.stdout:
            return

        async for raw in proc.stdout:
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            text = self._parse_streaming_line(session_id, line)
            if text:
                self._last_output[session_id] = text
                yield text

    # ── Status ─────────────────────────────────────────────────────────────────

    async def get_status(self, session_id: str) -> AgentStatus:
        proc   = self._sessions.get(session_id)
        config = self._configs.get(session_id)

        if not proc:
            state = "error"
        elif proc.returncode is None:
            state = "running"
        elif proc.returncode == 0:
            state = "done"
        else:
            state = "error"

        return AgentStatus(
            name=config.name if config else session_id,
            role=config.role if config else "unknown",
            state=state,
            current_task=config.task if config else "",
            runtime=self.runtime_name,
            last_output=self._last_output.get(session_id, ""),
            pid=proc.pid if proc else None,
        )

    # ── Kill ───────────────────────────────────────────────────────────────────

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

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_full_prompt(self, config: AgentConfig) -> str:
        """Load role contract md + inject role-lock footer + append task."""
        base = ""
        if config.system_prompt_path:
            p = Path(config.system_prompt_path)
            if p.exists() and p.is_file():
                base = p.read_text().strip() + "\n\n"

        # Role-lock footer — redundant with tool policy on purpose (defense in depth)
        # Especially important for bash-enabled roles that can't be tool-restricted
        lock = (
            f"ROLE CONTRACT (non-negotiable):\n"
            f"You are {config.name}, a {config.role} agent in a multi-agent swarm.\n"
            f"Stay strictly within your role boundaries.\n"
        )

        # Role-specific behavioral constraints injected at prompt level
        # Critical for scout/monitor who have bash blocked and rely on this
        behavioral = self._role_behavioral_constraints(config.role)

        completion = (
            f"\nWhen your task is complete, output this JSON on its own line:\n"
            f'{{"role":"{config.role}","status":"done",'
            f'"summary":"...","files_changed":[],"handoff_to":"..."}}\n'
        )

        return f"{base}{lock}{behavioral}{completion}\n---\n\nTASK:\n{config.task}"

    def _role_behavioral_constraints(self, role: str) -> str:
        """Per-role behavioral rules injected into prompt as soft enforcement layer."""
        constraints = {
            "scout": (
                "You MUST NOT edit, write, or delete any files.\n"
                "You MUST NOT run bash commands that modify state (git commit, rm, etc).\n"
                "You MAY only read files, list directories, and search.\n"
            ),
            "reviewer": (
                "You MUST NOT edit, write, or delete any files.\n"
                "You MUST NOT run any bash commands.\n"
                "You MAY only read files and produce a written review.\n"
            ),
            "tester": (
                "You MUST NOT commit or push any changes.\n"
                "You MAY write test files and run pytest/python commands.\n"
            ),
            "builder": (
                "You MUST NOT push to remote or merge branches.\n"
                "You MAY edit files, run tests, and stage changes with git add.\n"
            ),
            "merger": (
                "You are responsible for merge operations only.\n"
                "You MUST NOT write new feature code.\n"
            ),
            "monitor": (
                "You MUST NOT edit or write any files.\n"
                "You MAY run read-only bash commands (ps, git log, git status).\n"
            ),
        }
        return constraints.get(role, "")

    def _build_tool_flags(self, config: AgentConfig) -> list[str]:
        """
        Build --enabled-tools flags from verified tool name list.
        IMPORTANT: In -p mode, ANY --enabled-tools flag disables ALL unlisted tools.
        Empty list = no flags = all tools available (used for developer, merger).
        Config-level allowed_tools override role defaults.
        """
        tools = config.allowed_tools or self.ROLE_TOOL_POLICY.get(config.role, [])

        if not tools:
            return []  # all tools remain available

        flags = []
        for tool in tools:
            flags += ["--enabled-tools", tool]
        return flags

    def _parse_streaming_line(self, session_id: str, line: str) -> str | None:
        """
        Parse confirmed Vibe --output streaming NDJSON format.

        Confirmed message shapes from stream-json output:
          Assistant text:
            {"role": "assistant", "content": "...string..."}

          Tool call:
            {"role": "assistant", "tool_calls": [
              {"function": {"name": "bash", "arguments": "{\"command\":\"...\"}"}},
              {"function": {"name": "read_file", "arguments": "{\"path\":\"...\"}"}}
            ]}

          Tool result:
            {"role": "tool", "content": "command: ...\nstdout: ...\nstderr: ..."}

          Session info (may contain session_id for resume):
            {"session_id": "...", ...}
        """
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Plain text line (rare in streaming mode) — pass through
            return line if line else None

        # Capture session ID for nudge/resume support
        if "session_id" in obj and session_id not in self._session_ids:
            self._session_ids[session_id] = obj["session_id"]

        role    = obj.get("role", "")
        content = obj.get("content", "")

        # ── Assistant message ──────────────────────────────────────────────────
        if role == "assistant":
            tool_calls = obj.get("tool_calls")

            if tool_calls:
                # Tool invocation — format for output panel
                parts = []
                for call in tool_calls:
                    fn   = call.get("function", {})
                    name = fn.get("name", "tool")
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}

                    # Format each known tool cleanly
                    if name == "bash":
                        cmd = args.get("command", "")[:100]
                        parts.append(f"[bash] $ {cmd}")
                    elif name == "read_file":
                        parts.append(f"[read] {args.get('path', '')}")
                    elif name == "write_file":
                        parts.append(f"[write] {args.get('path', '')}")
                    elif name == "edit_file":
                        parts.append(f"[edit] {args.get('path', '')}")
                    elif name == "list_directory":
                        parts.append(f"[ls] {args.get('path', '.')}")
                    elif name == "search_files":
                        parts.append(f"[search] {args.get('pattern', '')}")
                    else:
                        parts.append(f"[{name}] {str(args)[:80]}")
                return "\n".join(parts) if parts else None

            # Plain assistant text
            if isinstance(content, str) and content:
                return content

            # Content blocks array (some Vibe versions)
            if isinstance(content, list):
                texts = [
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                result = "\n".join(t for t in texts if t)
                return result or None

        # ── Tool result ────────────────────────────────────────────────────────
        if role == "tool":
            if isinstance(content, str) and content:
                # Vibe tool results contain "command: ...\nstdout: ...\nstderr: ..."
                # Extract stdout only for cleaner display
                lines = content.splitlines()
                stdout_lines = []
                in_stdout = False
                for l in lines:
                    if l.startswith("stdout:"):
                        in_stdout = True
                        rest = l[len("stdout:"):].strip()
                        if rest:
                            stdout_lines.append(rest)
                    elif l.startswith("stderr:") or l.startswith("returncode:"):
                        in_stdout = False
                    elif in_stdout:
                        stdout_lines.append(l)
                output = "\n".join(stdout_lines[:10])  # cap at 10 lines
                return f"[result] {output}" if output else None

        # ── Cost / usage ───────────────────────────────────────────────────────
        if "total_cost" in obj or "cost" in obj:
            cost = obj.get("total_cost") or obj.get("cost")
            if cost is not None:
                return f"[cost] ${float(cost):.4f}"

        # ── Error ──────────────────────────────────────────────────────────────
        if obj.get("type") == "error" or "error" in obj:
            err = obj.get("message") or obj.get("error") or "unknown error"
            return f"[error] {err}"

        return None