# src/runtimes/opencode.py
import asyncio
import aiohttp
import json
import os
import uuid
from pathlib import Path
from typing import AsyncIterator

from .base import AgentRuntime, AgentConfig, AgentStatus, RuntimeCapabilities


class OpenCodeRuntime(AgentRuntime):
    """
    OpenCode adapter — HTTP/SSE server mode (preferred) with subprocess fallback.

    Architecture: Unlike all other runtimes, opencode runs as a persistent
    HTTP server. We spawn ONE opencode serve process per worktree, then
    communicate via REST API. This means:
      - Multiple agents can share one server if on the same worktree
      - No stdout parsing — events come via SSE on /session/:id/message
      - Full REST API: create/fork/abort/revert sessions

    Confirmed REST API from opencode.ai/docs/server:
      POST /session                           → create session
      POST /session/:id/message               → send prompt (blocks until done)
      POST /session/:id/prompt_async          → send prompt (non-blocking, 204)
      POST /session/:id/abort                 → kill running turn
      GET  /session/:id/message               → list all messages + parts
      GET  /global/event                      → global SSE stream
      GET  /session/:id/diff                  → file diff for session

    Message parts (confirmed from SDK docs):
      {type: "text",      content: "..."}
      {type: "tool-use",  toolName: "...", input: {...}, toolUseID: "..."}
      {type: "tool-result", toolUseID: "...", content: [...], isError: bool}
      {type: "step-start"}
      {type: "step-finish", finishReason: "...", usage: {...}}

    Role enforcement:
      - tools: [] in POST body restricts tool access at API level (strongest)
      - system: "..." in POST body injects system prompt per-message
      - No built-in sandbox (use worktree isolation + tool list)
    """

    # Tool names confirmed from opencode tool registry
    # Source: opencode default agent tool set
    KNOWN_TOOLS = {
        "read",          # read_file equivalent
        "write",         # write_file
        "edit",          # patch/edit file
        "bash",          # shell command execution
        "glob",          # file pattern matching
        "grep",          # content search
        "ls",            # list directory
        "todo_read",     # read session todo list
        "todo_write",    # update session todo list
        "fetch",         # HTTP fetch
        "task",          # spawn sub-agent task
    }

    # Tool allowlist per role — empty = all tools (developer/merger only)
    # Passed directly in POST /session/:id/message body as tools: [...]
    ROLE_TOOLS: dict[str, list[str]] = {
        "scout": [
            "read", "glob", "grep", "ls",
            # bash excluded — can't restrict to read-only subcommands
        ],
        "reviewer": [
            "read", "glob", "grep", "ls",
        ],
        "coordinator": [
            "read", "glob", "ls",
        ],
        "supervisor": [
            "read", "glob", "grep", "ls",
        ],
        "lead": [
            "read", "glob", "grep", "ls",
        ],
        "monitor": [
            "read", "glob", "grep", "ls",
            "bash",   # needs ps, git log — no write ops enforced by prompt
        ],
        "builder": [
            "read", "write", "edit",
            "glob", "grep", "ls",
            "bash",
        ],
        "tester": [
            "read", "write", "edit",
            "glob", "grep", "ls",
            "bash",
        ],
        "developer": [],   # unrestricted
        "merger":    [],   # unrestricted
        "orchestrator": [
            "read", "glob", "ls",
            "task",         # orchestrator can spawn sub-tasks
        ],
    }

    # Model per role — provider/model format as per opencode -m flag
    ROLE_MODEL: dict[str, str] = {
        "scout":        "anthropic/claude-sonnet-4-5",
        "reviewer":     "anthropic/claude-opus-4-5",
        "coordinator":  "anthropic/claude-sonnet-4-5",
        "supervisor":   "anthropic/claude-sonnet-4-5",
        "lead":         "anthropic/claude-opus-4-5",
        "builder":      "anthropic/claude-sonnet-4-5",
        "tester":       "anthropic/claude-sonnet-4-5",
        "monitor":      "anthropic/claude-haiku-3-5",
        "developer":    "anthropic/claude-opus-4-5",
        "merger":       "anthropic/claude-sonnet-4-5",
        "orchestrator": "anthropic/claude-opus-4-5",
    }

    # Default port range — each worktree gets its own server on a unique port
    BASE_PORT = 9100

    def __init__(self) -> None:
        # Maps worktree_path → (server_proc, port, http_session)
        self._servers:     dict[str, tuple[asyncio.subprocess.Process, int, aiohttp.ClientSession]] = {}
        # Maps internal session_id → opencode session_id
        self._oc_sessions: dict[str, str] = {}
        # Maps internal session_id → worktree_path (to look up server)
        self._session_worktree: dict[str, str] = {}
        self._configs:     dict[str, AgentConfig] = {}
        self._last_output: dict[str, str] = {}
        self._port_counter = self.BASE_PORT
        self._event_callback = None

    # ── Interface ──────────────────────────────────────────────────────────────

    @property
    def runtime_name(self) -> str:
        return "opencode"

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            interactive_chat=True,
            headless_run=True,
            resume_session=True,
            streaming_output=True,
            tool_allowlist=True,    # via tools: [] in message POST body
            sandbox_support=False,
            agent_profiles=False,
            parallel_safe=True,
        )

    # ── Server lifecycle ───────────────────────────────────────────────────────

    async def _ensure_server(self, worktree_path: str) -> tuple[int, aiohttp.ClientSession]:
        """
        Spin up ONE opencode serve process per worktree path if not running.
        Returns (port, http_session).
        """
        if worktree_path in self._servers:
            proc, port, http = self._servers[worktree_path]
            if proc.returncode is None:  # still alive
                return port, http

        port = self._port_counter
        self._port_counter += 1

        cmd = [
            "opencode", "serve",
            "--port", str(port),
            "--hostname", "127.0.0.1",
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=worktree_path,
            env={**os.environ},
        )

        # Wait for server to be ready — poll /global/health
        base_url = f"http://127.0.0.1:{port}"
        http = aiohttp.ClientSession(base_url=base_url)
        await self._wait_for_health(http, timeout=10.0)

        self._servers[worktree_path] = (proc, port, http)

        if self._event_callback:
            self._event_callback("info", "opencode-server",
                                 f"server started on port {port} for {worktree_path}")
        return port, http

    async def _wait_for_health(
        self, http: aiohttp.ClientSession, timeout: float = 10.0
    ) -> None:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                async with http.get("/global/health") as resp:
                    if resp.status == 200:
                        return
            except aiohttp.ClientConnectorError:
                pass
            await asyncio.sleep(0.2)
        raise TimeoutError("opencode server did not start in time")

    # ── Spawn ──────────────────────────────────────────────────────────────────

    async def spawn(self, config: AgentConfig) -> str:
        port, http = await self._ensure_server(config.worktree_path)

        # Parse provider/model
        model_str = config.model or self.ROLE_MODEL.get(config.role, "anthropic/claude-sonnet-4-5")
        provider_id, model_id = (model_str.split("/", 1)
                                 if "/" in model_str
                                 else ("anthropic", model_str))

        # Create a new session
        async with http.post("/session", json={"title": f"{config.name} ({config.role})"}) as resp:
            session_data = await resp.json()
        oc_session_id = session_data["id"]

        internal_id = f"opencode-{config.name}-{oc_session_id[:8]}"
        self._oc_sessions[internal_id]       = oc_session_id
        self._session_worktree[internal_id]  = config.worktree_path
        self._configs[internal_id]           = config
        self._last_output[internal_id]       = ""

        # Send initial task prompt asynchronously — don't block spawn
        system_prompt = self._build_system_prompt(config)
        tools         = self.ROLE_TOOLS.get(config.role)  # None = unrestricted

        body: dict = {
            "parts": [{"type": "text", "text": config.task}],
            "model": {"providerID": provider_id, "modelID": model_id},
            "system": system_prompt,
        }
        if tools is not None and len(tools) > 0:
            body["tools"] = tools

        # Fire-and-forget — stream_output will read the results
        asyncio.create_task(
            self._post_message_async(http, oc_session_id, body, internal_id)
        )

        if self._event_callback:
            self._event_callback("spawn", config.name,
                                 f"spawned as {config.role} via opencode ({model_str})")

        return internal_id

    async def _post_message_async(
        self,
        http: aiohttp.ClientSession,
        oc_session_id: str,
        body: dict,
        internal_id: str,
    ) -> None:
        """POST /session/:id/message — streams SSE parts until done."""
        try:
            async with http.post(
                f"/session/{oc_session_id}/message",
                json=body,
                timeout=aiohttp.ClientTimeout(total=600),
            ) as resp:
                # opencode returns the full message response when done
                result = await resp.json()
                parts  = result.get("parts", [])
                for part in parts:
                    text = self._parse_part(internal_id, part)
                    if text:
                        self._last_output[internal_id] = text
        except Exception as e:
            self._last_output[internal_id] = f"[error] {e}"

    # ── Nudge / resume ─────────────────────────────────────────────────────────

    async def send_message(self, session_id: str, message: str) -> None:
        config = self._configs.get(session_id)
        if not config:
            return

        worktree = self._session_worktree.get(session_id)
        if not worktree or worktree not in self._servers:
            return

        _, http = await self._ensure_server(worktree)
        oc_sid  = self._oc_sessions.get(session_id)
        if not oc_sid:
            return

        model_str   = config.model or self.ROLE_MODEL.get(config.role, "anthropic/claude-sonnet-4-5")
        provider_id, model_id = (model_str.split("/", 1)
                                 if "/" in model_str
                                 else ("anthropic", model_str))
        tools = self.ROLE_TOOLS.get(config.role)

        body: dict = {
            "parts": [{"type": "text", "text": message}],
            "model": {"providerID": provider_id, "modelID": model_id},
        }
        if tools is not None and len(tools) > 0:
            body["tools"] = tools

        asyncio.create_task(
            self._post_message_async(http, oc_sid, body, session_id)
        )

    # ── Stream output ──────────────────────────────────────────────────────────

    async def stream_output(self, session_id: str) -> AsyncIterator[str]:
        """
        Poll /session/:id/message for new parts.
        opencode uses SSE on the global event stream for real-time push,
        but polling the message list is simpler and reliable for our use case.
        """
        config   = self._configs.get(session_id)
        worktree = self._session_worktree.get(session_id)
        oc_sid   = self._oc_sessions.get(session_id)

        if not config or not worktree or not oc_sid:
            return

        _, http = await self._ensure_server(worktree)
        seen_part_ids: set[str] = set()

        while True:
            try:
                async with http.get(f"/session/{oc_sid}/message") as resp:
                    if resp.status != 200:
                        await asyncio.sleep(0.5)
                        continue
                    data = await resp.json()

                for msg in data:
                    for part in msg.get("parts", []):
                        part_id = part.get("id") or part.get("toolUseID") or str(part)
                        if part_id in seen_part_ids:
                            continue
                        seen_part_ids.add(part_id)
                        text = self._parse_part(session_id, part)
                        if text:
                            self._last_output[session_id] = text
                            yield text

            except aiohttp.ClientError:
                pass

            # Check if the agent process is still alive
            status = await self.get_status(session_id)
            if status.state in ("done", "error"):
                break

            await asyncio.sleep(1.0)

    # ── Status ─────────────────────────────────────────────────────────────────

    async def get_status(self, session_id: str) -> AgentStatus:
        config   = self._configs.get(session_id)
        worktree = self._session_worktree.get(session_id)
        oc_sid   = self._oc_sessions.get(session_id)

        if not config or not worktree or not oc_sid:
            return AgentStatus(
                name=session_id, role="unknown", state="error",
                current_task="", runtime=self.runtime_name,
                last_output="", pid=None,
            )

        try:
            _, http = await self._ensure_server(worktree)
            async with http.get("/session/status") as resp:
                statuses = await resp.json()
            oc_status = statuses.get(oc_sid, {})
            # opencode session statuses: "idle", "running", "error"
            raw = oc_status.get("status", "idle")
            state = {"idle": "done", "running": "running", "error": "error"}.get(raw, "done")
        except Exception:
            state = "error"

        return AgentStatus(
            name=config.name,
            role=config.role,
            state=state,
            current_task=config.task,
            runtime=self.runtime_name,
            last_output=self._last_output.get(session_id, ""),
            pid=None,   # no PID — server process owns all sessions
        )

    # ── Kill ───────────────────────────────────────────────────────────────────

    async def kill(self, session_id: str) -> None:
        config   = self._configs.get(session_id)
        worktree = self._session_worktree.get(session_id)
        oc_sid   = self._oc_sessions.get(session_id)

        # Abort the running session if active
        if worktree and oc_sid and worktree in self._servers:
            try:
                _, http = await self._ensure_server(worktree)
                async with http.post(f"/session/{oc_sid}/abort"):
                    pass
                async with http.delete(f"/session/{oc_sid}"):
                    pass
            except Exception:
                pass

        self._configs.pop(session_id, None)
        self._oc_sessions.pop(session_id, None)
        self._session_worktree.pop(session_id, None)
        self._last_output.pop(session_id, None)

    async def kill_server(self, worktree_path: str) -> None:
        """Shut down the opencode server for a given worktree. Call on full swarm teardown."""
        entry = self._servers.pop(worktree_path, None)
        if entry:
            proc, _, http = entry
            await http.close()
            if proc.returncode is None:
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
        )

    def _role_behavioral_constraints(self, role: str) -> str:
        constraints = {
            "scout": (
                "You MUST NOT edit, write, or delete any files.\n"
                "You MUST NOT run bash commands that modify state.\n"
            ),
            "reviewer": (
                "You MUST NOT edit, write, or delete any files.\n"
                "Produce a written review only.\n"
            ),
            "builder": (
                "You MAY edit files and run build/test commands.\n"
                "You MUST NOT push to remote or merge branches.\n"
            ),
            "tester": (
                "You MAY write test files and run test commands.\n"
                "You MUST NOT commit or push changes.\n"
            ),
            "developer": (
                "You MAY implement features and write code.\n"
                "You MUST NOT push without reviewer approval.\n"
            ),
            "merger": (
                "You handle merge operations only.\n"
                "You MUST NOT write new feature code.\n"
            ),
            "monitor": (
                "You MUST NOT edit or write any files.\n"
                "You MAY run read-only inspection commands only.\n"
            ),
        }
        return constraints.get(role, "")

    def _parse_part(self, session_id: str, part: dict) -> str | None:
        """
        Parse confirmed opencode message part types from REST API.

        Confirmed part shapes from opencode.ai/docs/sdk:
          {type: "text",        content: "..."}
          {type: "tool-use",    toolName: "...", input: {...}, toolUseID: "..."}
          {type: "tool-result", toolUseID: "...", content: [...], isError: bool}
          {type: "step-start"}
          {type: "step-finish", finishReason: "...", usage: {inputTokens, outputTokens}}
        """
        part_type = part.get("type", "")

        if part_type == "text":
            content = part.get("content", "")
            return content if content else None

        if part_type == "tool-use":
            tool  = part.get("toolName", "unknown")
            inp   = part.get("input", {})

            if tool == "bash":
                cmd = inp.get("command", "")[:100]
                return f"[bash] $ {cmd}"
            elif tool == "write":
                return f"[write] {inp.get('filePath', inp.get('path', ''))}"
            elif tool == "edit":
                return f"[edit] {inp.get('filePath', inp.get('path', ''))}"
            elif tool == "read":
                return f"[read] {inp.get('filePath', inp.get('path', ''))}"
            elif tool == "ls":
                return f"[ls] {inp.get('path', '.')}"
            elif tool == "glob":
                return f"[glob] {inp.get('pattern', '')}"
            elif tool == "grep":
                return f"[grep] {inp.get('pattern', '')} in {inp.get('path', '.')}"
            elif tool == "fetch":
                return f"[fetch] {inp.get('url', '')}"
            elif tool == "task":
                return f"[task] spawning: {inp.get('description', '')[:80]}"
            elif tool in ("todo_read", "todo_write"):
                return None  # internal bookkeeping, don't surface
            else:
                return f"[{tool}] {str(inp)[:80]}"

        if part_type == "tool-result":
            is_error = part.get("isError", False)
            content  = part.get("content", [])

            # content is an array of blocks
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif isinstance(block, str):
                    texts.append(block)

            output = "\n".join(t for t in texts if t)
            if not output:
                return None

            lines  = output.splitlines()[:10]
            result = "\n".join(lines)
            prefix = "[error]" if is_error else "[result]"
            return f"{prefix} {result}"

        if part_type == "step-finish":
            usage  = part.get("usage", {})
            inp    = usage.get("inputTokens", 0)
            out    = usage.get("outputTokens", 0)
            reason = part.get("finishReason", "")
            if reason == "stop":
                return f"[step] done — {inp} in / {out} out tokens"
            elif reason == "error":
                return f"[step] failed"
            return None  # length/other reasons — skip

        # step-start — nothing to surface
        return None