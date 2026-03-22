import asyncio
import os
from pathlib import Path
from typing import AsyncIterator, Optional

from .base import AgentRuntime, AgentConfig, AgentStatus, RuntimeCapabilities


class GooseRuntime(AgentRuntime):
    """
    Goose CLI adapter.
    Uses 'goose run -t "..." --instructions <path>' for headless execution.
    """

    def __init__(self) -> None:
        self._sessions:    dict[str, asyncio.subprocess.Process] = {}
        self._configs:     dict[str, AgentConfig] = {}
        self._last_output: dict[str, str] = {}

    @property
    def runtime_name(self) -> str:
        return "goose"

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            interactive_chat=True,
            headless_run=True,
            resume_session=False,
            streaming_output=True,
            tool_allowlist=False,
            sandbox_support=False,
            agent_profiles=False,
            parallel_safe=True,
        )

    async def spawn(self, config: AgentConfig) -> str:
        cmd = [
            "goose", "run",
            "-t", config.task,
            "-q", # quiet mode
        ]
        
        if config.system_prompt_path:
            cmd += ["--instructions", config.system_prompt_path]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.worktree_path,
            env={**os.environ, **(config.extra_env or {})},
        )

        session_id = f"goose-{config.name}-{proc.pid}"
        self._sessions[session_id]    = proc
        self._configs[session_id]     = config
        self._last_output[session_id] = ""

        return session_id

    async def send_message(self, session_id: str, message: str) -> None:
        # goose run is one-shot
        pass

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

    async def stream_output(self, session_id: str) -> AsyncIterator[str]:
        proc = self._sessions.get(session_id)
        if not proc or not proc.stdout:
            return

        async for raw in proc.stdout:
            line = raw.decode(errors="replace").strip()
            if line:
                self._last_output[session_id] = line
                yield line

    async def kill(self, session_id: str) -> None:
        proc = self._sessions.pop(session_id, None)
        self._configs.pop(session_id, None)
        self._last_output.pop(session_id, None)
        if proc and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                proc.kill()
