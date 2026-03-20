# src/runtimes/openclaw.py
import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import AsyncIterator

from .base import AgentRuntime, AgentConfig, AgentStatus, RuntimeCapabilities


class OpenClawRuntime(AgentRuntime):
    """
    OpenClaw Gateway adapter.

    Architecture: OpenClaw is a persistent WebSocket Gateway + message bus.
    Unlike all other runtimes, it is NOT a coding agent — it's a multi-channel
    AI assistant with tool-calling. Use it for:
      - Orchestration/overseer roles (it has memory + cron + node control)
      - Monitor roles (system events, heartbeat, presence)
      - Cross-channel notification delivery
      - Tasks requiring browser automation or remote node execution

    Headless interface: openclaw agent --message "..." --json --local
      --local: run embedded (no channel delivery), returns JSON response
      --json:  structured output, no ANSI

    Gateway interface (preferred for production):
      openclaw gateway --port 18789 (run once, persists)
      openclaw agent --to <session> --message "..." --json
      Session key = agent name (stable across turns for same agent)

    Approval/tool control:
      openclaw approvals set --level <allow|ask|deny> (gateway-wide)
      openclaw approvals allowlist add <tool> (per-tool)
      No per-spawn tool restriction — approvals are gateway-level config

    Role enforcement strategy:
      - Prompt-level contracts (same as all runtimes)
      - approvals.allowlist configured per-agent via --agent flag
      - --thinking flag for reasoning depth on supported models
      - NOT suitable for isolated file-editing roles (builder/developer)
        → those should use Vibe/Claude Code/Codex/Gemini instead
        → OpenClaw shines for orchestrator/monitor/coordinator roles

    Output: --json returns structured response object (not JSONL stream)
    Resume: --session-id <id> or --to <dest> maintains session context
    """

    # Roles OpenClaw is actually suited for
    # File-editing roles (builder/developer/tester/merger) should use other runtimes
    SUITABLE_ROLES = {
        "orchestrator", "coordinator", "supervisor",
        "lead", "monitor", "scout",
    }

    # Thinking depth per role — controls reasoning budget on supported models
    # off=fast, minimal/low=light reasoning, medium/high/xhigh=deep reasoning
    ROLE_THINKING: dict[str, str] = {
        "orchestrator": "high",
        "coordinator":  "medium",
        "supervisor":   "medium",
        "lead":         "high",
        "monitor":      "minimal",
        "scout":        "low",
        "reviewer":     "high",
        # builder/developer etc use other runtimes — fallback if forced
        "builder":      "low",
        "tester":       "low",
        "developer":    "medium",
        "merger":       "low",
    }

    # Verbose level per role
    ROLE_VERBOSE: dict[str, str] = {
        "orchestrator": "full",
        "coordinator":  "on",
        "supervisor":   "on",
        "lead":         "full",
        "monitor":      "off",
        "scout":        "off",
    }

    # Default gateway config
    GATEWAY_HOST = "127.0.0.1"
    GATEWAY_PORT = 18789

    def __init__(self) -> None:
        self._sessions:     dict[str, asyncio.subprocess.Process] = {}
        self._session_keys: dict[str, str] = {}   # internal_id → openclaw session key
        self._configs:      dict[str, AgentConfig] = {}
        self._last_output:  dict[str, str] = {}
        self._gateway_proc: asyncio.subprocess.Process | None = None
        self._event_callback = None

    # ── Interface ──────────────────────────────────────────────────────────────

    @property
    def runtime_name(self) -> str:
        return "openclaw"

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            interactive_chat=True,
            headless_run=True,
            resume_session=True,
            streaming_output=False,  # --json returns complete response, not stream
            tool_allowlist=False,    # approval level is gateway-wide, not per-spawn
            sandbox_support=False,
            agent_profiles=False,
            parallel_safe=True,
        )

    # ── Gateway lifecycle ──────────────────────────────────────────────────────

    async def ensure_gateway(self, worktree_path: str) -> None:
        """
        Start the OpenClaw Gateway if not already running.
        Only call once per swarm session — gateway is shared across all agents.
        """
        # Check if gateway is already healthy
        check = await asyncio.create_subprocess_exec(
            "openclaw", "health", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await check.wait()
        if check.returncode == 0:
            return  # gateway already running

        # Start the gateway
        self._gateway_proc = await asyncio.create_subprocess_exec(
            "openclaw", "gateway",
            "--port", str(self.GATEWAY_PORT),
            "--bind", "loopback",
            "--allow-unconfigured",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=worktree_path,
            env={**os.environ},
        )

        # Wait for gateway to be ready
        for _ in range(20):
            await asyncio.sleep(0.5)
            check = await asyncio.create_subprocess_exec(
                "openclaw", "health", "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await check.wait()
            if check.returncode == 0:
                if self._event_callback:
                    self._event_callback("info", "openclaw-gateway",
                                         f"gateway started on port {self.GATEWAY_PORT}")
                return

        raise TimeoutError("OpenClaw gateway did not start in time")

    async def kill_gateway(self) -> None:
        """Shut down the gateway. Call on full swarm teardown."""
        if self._gateway_proc and self._gateway_proc.returncode is None:
            self._gateway_proc.terminate()
            try:
                await asyncio.wait_for(self._gateway_proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._gateway_proc.kill()
        self._gateway_proc = None

    # ── Spawn ──────────────────────────────────────────────────────────────────

    async def spawn(self, config: AgentConfig) -> str:
        # Warn if using OpenClaw for a file-editing role
        if config.role not in self.SUITABLE_ROLES and self._event_callback:
            self._event_callback(
                "warn", config.name,
                f"OpenClaw is not optimized for role '{config.role}' — "
                f"consider Vibe/Claude Code/Codex for file-editing roles"
            )

        full_prompt = self._build_full_prompt(config)
        thinking    = self.ROLE_THINKING.get(config.role, "low")
        verbose     = self.ROLE_VERBOSE.get(config.role, "off")

        # Session key = agent name — stable across turns, enables resume
        session_key = f"polyglot-{config.name}"

        cmd = [
            "openclaw", "agent",
            "--message", full_prompt,
            "--session-id", session_key,
            "--thinking", thinking,
            "--verbose", verbose,
            "--local",    # embedded mode — no channel delivery
            "--json",     # structured JSON output
            "--timeout", "300",
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.worktree_path,
            env={**os.environ, **(config.extra_env or {})},
        )

        session_id = f"openclaw-{config.name}-{proc.pid}"
        self._sessions[session_id]     = proc
        self._session_keys[session_id] = session_key
        self._configs[session_id]      = config
        self._last_output[session_id]  = ""

        if self._event_callback:
            self._event_callback(
                "spawn", config.name,
                f"spawned as {config.role} via openclaw "
                f"(thinking: {thinking}, session: {session_key})"
            )

        return session_id

    # ── Nudge / resume ─────────────────────────────────────────────────────────

    async def send_message(self, session_id: str, message: str) -> None:
        config = self._configs.get(session_id)
        if not config:
            return

        session_key = self._session_keys.get(session_id, f"polyglot-{config.name}")
        thinking    = self.ROLE_THINKING.get(config.role, "low")

        cmd = [
            "openclaw", "agent",
            "--message", message,
            "--session-id", session_key,   # resume same session context
            "--thinking", thinking,
            "--local",
            "--json",
            "--timeout", "300",
        ]

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
        """
        OpenClaw --json returns a complete JSON object when the turn finishes,
        not a JSONL stream. We read all stdout then parse once.

        Confirmed --json response shape from openclaw agent docs:
          {
            "response": "final text",
            "sessionId": "...",
            "messageId": "...",
            "model": "...",
            "toolsUsed": ["tool1", ...],
            "thinking": "...",
            "error": null
          }
        """
        proc = self._sessions.get(session_id)
        if not proc or not proc.stdout:
            return

        # Read full stdout (completes when process exits)
        raw_out, raw_err = await proc.communicate()
        output = raw_out.decode(errors="replace").strip()

        if not output:
            if raw_err:
                err = raw_err.decode(errors="replace").strip()
                self._last_output[session_id] = f"[error] {err[:200]}"
                yield f"[error] {err[:200]}"
            return

        # Try JSON parse first
        try:
            obj = json.loads(output)
            text = self._parse_response(session_id, obj)
            if text:
                self._last_output[session_id] = text
                yield text
            return
        except json.JSONDecodeError:
            pass

        # Fallback: plain text response
        self._last_output[session_id] = output
        yield output

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
        self._session_keys.pop(session_id, None)
        self._last_output.pop(session_id, None)
        if proc and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_full_prompt(self, config: AgentConfig) -> str:
        base = ""
        p = Path(config.system_prompt_path)
        if p.exists():
            base = p.read_text().strip() + "\n\n"

        behavioral = self._role_behavioral_constraints(config.role)
        completion = (
            f"\nWhen your task is complete, output this JSON on its own line:\n"
            f'{{"role":"{config.role}","status":"done",'
            f'"summary":"...","files_changed":[],"handoff_to":"..."}}\n'
        )

        return (
            f"{base}"
            f"ROLE CONTRACT:\n"
            f"You are {config.name}, a {config.role} agent.\n"
            f"{behavioral}"
            f"{completion}"
            f"\n---\n\nTASK:\n{config.task}"
        )

    def _role_behavioral_constraints(self, role: str) -> str:
        constraints = {
            "orchestrator": (
                "You coordinate the swarm. Decompose tasks, assign roles, track progress.\n"
                "You MUST NOT write feature code directly.\n"
                "Use your memory and session context to maintain state across turns.\n"
            ),
            "coordinator": (
                "You plan and assign tasks to other agents.\n"
                "You MUST NOT implement features yourself.\n"
            ),
            "supervisor": (
                "You monitor agent progress and intervene when blocked.\n"
                "You MUST NOT override or duplicate work in progress.\n"
            ),
            "lead": (
                "You make architectural decisions and review plans.\n"
                "You MAY read files and write design documents.\n"
                "You MUST NOT write implementation code.\n"
            ),
            "scout": (
                "You MUST NOT edit, write, or delete any files.\n"
                "Explore and report findings only.\n"
            ),
            "reviewer": (
                "You MUST NOT edit, write, or delete any files.\n"
                "Produce a written review only.\n"
            ),
            "monitor": (
                "You observe system state and report anomalies.\n"
                "You MUST NOT modify files or trigger actions.\n"
                "Use system events and presence data to build your report.\n"
            ),
        }
        return constraints.get(role, "")

    def _parse_response(self, session_id: str, obj: dict) -> str | None:
        """
        Parse confirmed openclaw agent --json response.

        Confirmed shape from openclaw agent docs:
          response:   final assistant text
          sessionId:  stable session key (for future resume)
          messageId:  unique message ID
          model:      model used
          toolsUsed:  list of tool names called during the turn
          thinking:   chain-of-thought text (if thinking enabled)
          error:      null or error string
        """
        # Capture stable session key for future resume
        sid = obj.get("sessionId")
        if sid:
            # Find which internal_id this belongs to and update key
            for internal_id, cfg in self._configs.items():
                if f"openclaw-{cfg.name}" in internal_id:
                    self._session_keys[internal_id] = sid
                    break

        # Surface error first
        error = obj.get("error")
        if error:
            return f"[error] {error}"

        parts = []

        # Tools used during this turn
        tools_used = obj.get("toolsUsed", [])
        if tools_used:
            parts.append(f"[tools] {', '.join(tools_used)}")

        # Main response text
        response = obj.get("response", "")
        if response:
            parts.append(response)

        # Model info (useful for orchestrator role debugging)
        model = obj.get("model", "")
        if model:
            parts.append(f"[model] {model}")

        return "\n".join(parts) if parts else None
