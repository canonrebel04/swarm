# src/runtimes/codex.py
import asyncio
import json
import os
from pathlib import Path
from typing import AsyncIterator

from .base import AgentRuntime, AgentConfig, AgentStatus, RuntimeCapabilities


class CodexRuntime(AgentRuntime):
    """
    OpenAI Codex CLI adapter.

    Headless mode: codex exec --json
    Confirmed JSONL event types from official docs:
      thread.started   → {"type": "thread.started", "thread_id": "uuid"}
      turn.started     → {"type": "turn.started"}
      item.started     → {"type": "item.started",   "item": {...}}
      item.completed   → {"type": "item.completed", "item": {...}}
      turn.completed   → {"type": "turn.completed", "usage": {...}}
      turn.failed      → {"type": "turn.failed",    "error": "..."}
      error            → {"type": "error",           "message": "..."}

    Confirmed item types:
      agent_message      → item.text  (final assistant output)
      command_execution  → item.command + item.output
      file_change        → item.path
      reasoning          → item.text  (chain-of-thought, skip in output)
      web_search         → item.query
      plan_update        → item.text

    Resume: codex exec resume SESSION_ID "follow-up prompt"
    Sandbox: --sandbox read-only | workspace-write | danger-full-access
    Approval: --ask-for-approval never (for headless, non-interactive)
    """

    # Sandbox policy per role — enforced at OS/kernel level by Codex
    # This is the strongest enforcement of the three runtimes
    ROLE_SANDBOX: dict[str, str] = {
        "scout":        "read-only",          # kernel-enforced read-only FS
        "reviewer":     "read-only",
        "coordinator":  "read-only",
        "supervisor":   "read-only",
        "lead":         "read-only",
        "monitor":      "read-only",
        "builder":      "workspace-write",    # can write inside worktree only
        "tester":       "workspace-write",
        "developer":    "workspace-write",
        "merger":       "workspace-write",
        "orchestrator": "read-only",
    }

    # Approval policy — always never for headless agents
    # Codex will not pause and wait for human input
    ROLE_APPROVAL: dict[str, str] = {
        "scout":     "never",
        "reviewer":  "never",
        "builder":   "never",
        "tester":    "never",
        "developer": "never",
        "merger":    "never",
        "monitor":   "never",
        "coordinator":  "never",
        "supervisor":   "never",
        "lead":         "never",
        "orchestrator": "never",
    }

    # Model per role — o4-mini for fast/cheap roles, o3 for complex ones
    ROLE_MODEL: dict[str, str] = {
        "scout":        "o4-mini",
        "reviewer":     "o3",       # deep analysis needs full reasoning
        "coordinator":  "o4-mini",
        "supervisor":   "o4-mini",
        "lead":         "o3",
        "builder":      "o4-mini",
        "tester":       "o4-mini",
        "developer":    "o3",       # complex implementation needs o3
        "merger":       "o4-mini",
        "monitor":      "o4-mini",
        "orchestrator": "o3",
    }

    def __init__(self) -> None:
        self._sessions:    dict[str, asyncio.subprocess.Process] = {}
        self._thread_ids:  dict[str, str] = {}   # internal_id → codex thread_id (for resume)
        self._configs:     dict[str, AgentConfig] = {}
        self._last_output: dict[str, str] = {}
        self._event_callback = None

    # ── Interface ──────────────────────────────────────────────────────────────

    @property
    def runtime_name(self) -> str:
        return "codex"

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            interactive_chat=True,
            headless_run=True,
            resume_session=True,
            streaming_output=True,
            tool_allowlist=False,    # Codex uses sandbox policy, not tool allowlist
            sandbox_support=True,    # strongest sandbox of all three runtimes
            agent_profiles=False,
            parallel_safe=True,
        )

    # ── Spawn ──────────────────────────────────────────────────────────────────

    async def spawn(self, config: AgentConfig) -> str:
        system_prompt = self._build_system_prompt(config)
        sandbox       = self.ROLE_SANDBOX.get(config.role, "workspace-write")
        approval      = self.ROLE_APPROVAL.get(config.role, "never")
        model         = config.model or self.ROLE_MODEL.get(config.role, "o4-mini")

        # Write system prompt to temp file — codex exec uses -c to override config
        prompt_file = Path(config.worktree_path) / ".codex_system_prompt.md"
        prompt_file.write_text(system_prompt)

        full_prompt = config.task

        cmd = [
            "codex", "exec",
            "--json",                          # JSONL streaming to stdout
            "--model", model,
            "--sandbox", sandbox,
            "--ask-for-approval", approval,
            "-C", config.worktree_path,        # set workspace root
            "-c", f"system_prompt={json.dumps(system_prompt)}",
            full_prompt,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.worktree_path,
            env={**os.environ, **(config.extra_env or {})},
        )

        session_id = f"codex-{config.name}-{proc.pid}"
        self._sessions[session_id]    = proc
        self._configs[session_id]     = config
        self._last_output[session_id] = ""

        if self._event_callback:
            self._event_callback(
                "spawn", config.name,
                f"spawned as {config.role} via codex ({sandbox} sandbox, {model})"
            )

        return session_id

    # ── Nudge / resume ─────────────────────────────────────────────────────────

    async def send_message(self, session_id: str, message: str) -> None:
        config    = self._configs.get(session_id)
        if not config:
            return

        sandbox  = self.ROLE_SANDBOX.get(config.role, "workspace-write")
        approval = self.ROLE_APPROVAL.get(config.role, "never")
        model    = config.model or self.ROLE_MODEL.get(config.role, "o4-mini")
        thread_id = self._thread_ids.get(session_id)

        if thread_id:
            # Resume the existing session with a follow-up prompt
            cmd = [
                "codex", "exec", "resume", thread_id,
                "--json",
                "--sandbox", sandbox,
                "--ask-for-approval", approval,
                "-C", config.worktree_path,
                message,
            ]
        else:
            # No thread ID yet — use --last to continue most recent session
            cmd = [
                "codex", "exec",
                "--json",
                "--model", model,
                "--sandbox", sandbox,
                "--ask-for-approval", approval,
                "-C", config.worktree_path,
                message,
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
        proc = self._sessions.get(session_id)
        if not proc or not proc.stdout:
            return

        async for raw in proc.stdout:
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            text = self._parse_jsonl_event(session_id, line)
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
        self._thread_ids.pop(session_id, None)
        self._last_output.pop(session_id, None)
        # Clean up temp system prompt file
        config = self._configs.get(session_id)
        if config:
            p = Path(config.worktree_path) / ".codex_system_prompt.md"
            p.unlink(missing_ok=True)
        if proc and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_system_prompt(self, config: AgentConfig) -> str:
        base = ""
        p = Path(config.system_prompt_path)
        if p.exists():
            base = p.read_text().strip() + "\n\n"

        behavioral = self._role_behavioral_constraints(config.role)
        sandbox_note = (
            f"NOTE: You are running inside a '{self.ROLE_SANDBOX.get(config.role, 'workspace-write')}' "
            f"sandbox. Attempts to access paths outside your workspace will fail at the OS level.\n"
        )
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
            f"{sandbox_note}"
            f"{completion}"
        )

    def _role_behavioral_constraints(self, role: str) -> str:
        constraints = {
            "scout": (
                "You MUST NOT edit, write, or delete any files.\n"
                "You MUST NOT run commands that modify state.\n"
                "Your sandbox enforces read-only access at the OS level.\n"
            ),
            "reviewer": (
                "You MUST NOT edit, write, or delete any files.\n"
                "Produce a written review only. No code changes.\n"
            ),
            "tester": (
                "You MAY write test files and run pytest.\n"
                "You MUST NOT commit or push changes.\n"
            ),
            "builder": (
                "You MAY edit files and stage changes with git add.\n"
                "You MUST NOT push to remote or merge branches.\n"
            ),
            "developer": (
                "You MAY implement features and write code.\n"
                "You MUST NOT push to remote without reviewer sign-off.\n"
            ),
            "merger": (
                "You handle merge operations only.\n"
                "You MUST NOT write new feature code.\n"
            ),
            "monitor": (
                "You MUST NOT edit or write any files.\n"
                "You MAY run read-only inspection commands.\n"
            ),
        }
        return constraints.get(role, "")

    def _parse_jsonl_event(self, session_id: str, line: str) -> str | None:
        """
        Parse confirmed Codex exec --json JSONL event stream.

        Confirmed event shapes from official OpenAI docs:
          {"type": "thread.started",  "thread_id": "uuid"}
          {"type": "turn.started"}
          {"type": "item.started",   "item": {"id":"...", "type":"command_execution",
                                               "command":"bash -lc ls", "status":"in_progress"}}
          {"type": "item.completed", "item": {"id":"...", "type":"agent_message",
                                               "text":"Repo contains docs..."}}
          {"type": "turn.completed", "usage": {"input_tokens":N, "output_tokens":N}}
          {"type": "turn.failed",    "error": "..."}
          {"type": "error",          "message": "..."}
        """
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return line if line else None

        event_type = obj.get("type", "")

        # ── Capture thread ID for resume ───────────────────────────────────────
        if event_type == "thread.started":
            tid = obj.get("thread_id")
            if tid:
                self._thread_ids[session_id] = tid
            return None  # internal event, don't surface to output panel

        # ── Turn lifecycle — only surface failures ─────────────────────────────
        if event_type == "turn.started":
            return None

        if event_type == "turn.completed":
            usage = obj.get("usage", {})
            inp   = usage.get("input_tokens", 0)
            out   = usage.get("output_tokens", 0)
            return f"[usage] {inp} in / {out} out tokens"

        if event_type == "turn.failed":
            return f"[failed] {obj.get('error', 'unknown error')}"

        if event_type == "error":
            return f"[error] {obj.get('message', 'unknown error')}"

        # ── Item events ────────────────────────────────────────────────────────
        # item.started = in-progress (show as live indicator)
        # item.completed = final result (show full content)

        item = obj.get("item", {})
        if not item:
            return None

        item_type   = item.get("type", "")
        item_status = item.get("status", "")

        # Skip in-progress items — wait for item.completed for clean output
        if event_type == "item.started":
            if item_type == "command_execution":
                cmd = item.get("command", "")[:100]
                return f"[exec] $ {cmd}"
            return None

        if event_type != "item.completed":
            return None

        # ── Completed item types ───────────────────────────────────────────────

        if item_type == "agent_message":
            # Final assistant message — primary output
            text = item.get("text", "")
            return text if text else None

        if item_type == "command_execution":
            cmd    = item.get("command", "")[:80]
            output = item.get("output", "")
            if output:
                # Cap output to 15 lines to avoid flooding the output panel
                lines = output.splitlines()[:15]
                truncated = "\n".join(lines)
                suffix = f"\n… ({len(output.splitlines()) - 15} more lines)" \
                         if len(output.splitlines()) > 15 else ""
                return f"[exec] $ {cmd}\n{truncated}{suffix}"
            return f"[exec] $ {cmd}"

        if item_type == "file_change":
            path   = item.get("path", "")
            change = item.get("change_type", "modified")
            return f"[file] {change}: {path}"

        if item_type == "reasoning":
            # Chain-of-thought — skip, don't surface to output panel
            return None

        if item_type == "web_search":
            query = item.get("query", "")
            return f"[search] {query}"

        if item_type == "plan_update":
            text = item.get("text", "")
            return f"[plan] {text}" if text else None

        return None
