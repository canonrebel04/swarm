import asyncio
import os
import paramiko
from typing import AsyncIterator, Optional
from .remote_base import RemoteAgentRuntime
from .base import AgentConfig, AgentStatus, RuntimeCapabilities


class SSHRuntime(RemoteAgentRuntime):
    """
    Runtime adapter for executing agents on remote hosts via SSH.
    """

    def __init__(self) -> None:
        self._ssh_clients: dict[str, paramiko.SSHClient] = {}
        self._sessions:    dict[str, asyncio.subprocess.Process] = {} # Not used for SSH
        self._configs:     dict[str, AgentConfig] = {}
        self._last_output: dict[str, str] = {}

    @property
    def runtime_name(self) -> str:
        return "ssh"

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            interactive_chat=True,
            headless_run=True,
            streaming_output=True,
            parallel_safe=True,
        )

    async def spawn(self, config: AgentConfig) -> str:
        if not config.remote_host:
            raise ValueError("remote_host is required for SSHRuntime")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect using key or agent
        client.connect(config.remote_host, username=config.remote_user)
        
        session_id = f"ssh-{config.name}-{config.remote_host}"
        self._ssh_clients[session_id] = client
        self._configs[session_id] = config
        self._last_output[session_id] = ""

        # 1. Sync worktree
        remote_path = config.remote_path or f"/tmp/swarm-{config.name}"
        await self.sync_worktree(config.worktree_path, remote_path)

        # 2. Start agent command (simplified for now)
        # Assuming 'vibe' or other binary is in PATH on remote
        stdin, stdout, stderr = client.exec_command(f"cd {remote_path} && vibe -p '{config.task}'")
        
        # We store the channel to read from it in stream_output
        self._last_output[session_id] = "Connection established. Starting remote agent..."
        
        return session_id

    async def sync_worktree(self, local_path: str, remote_path: str) -> bool:
        # Simplified SFTP sync logic
        # In production, we'd use rsync or a more robust recursive SFTP
        return True

    async def fetch_results(self, remote_path: str, local_path: str) -> bool:
        return True

    async def stream_output(self, session_id: str) -> AsyncIterator[str]:
        client = self._ssh_clients.get(session_id)
        if not client: return

        # In a real implementation, we'd wrap stdout in an async reader
        # For this prototype, we'll yield a mock stream
        yield "[ssh] Streaming from remote host..."
        yield f"[ssh] Task: {self._configs[session_id].task[:50]}..."

    async def get_status(self, session_id: str) -> AgentStatus:
        config = self._configs.get(session_id)
        return AgentStatus(
            name=config.name if config else session_id,
            role=config.role if config else "unknown",
            state="running",
            current_task=config.task if config else "",
            runtime=self.runtime_name,
            last_output=self._last_output.get(session_id, "")
        )

    async def send_message(self, session_id: str, message: str) -> None:
        pass

    async def kill(self, session_id: str) -> None:
        client = self._ssh_clients.pop(session_id, None)
        if client:
            client.close()
