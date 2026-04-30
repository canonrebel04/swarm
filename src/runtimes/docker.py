import asyncio
import os
import docker
from typing import AsyncIterator, Optional
from .remote_base import RemoteAgentRuntime
from .base import AgentConfig, AgentStatus, RuntimeCapabilities


class DockerRuntime(RemoteAgentRuntime):
    """
    Runtime adapter for executing agents in ephemeral Docker containers.
    """

    def __init__(self) -> None:
        self._client = None  # lazy — only connect when needed
        self._containers: dict[str, docker.models.containers.Container] = {}
        self._configs:    dict[str, AgentConfig] = {}
        self._last_output: dict[str, str] = {}

    def _get_client(self):
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    @property
    def runtime_name(self) -> str:
        return "docker"

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            interactive_chat=True,
            headless_run=True,
            streaming_output=True,
            sandbox_support=True,
            parallel_safe=True,
        )

    async def spawn(self, config: AgentConfig) -> str:
        image = config.container_image or "polyglotswarm/agent-base:latest"
        
        # Mount local worktree into container
        volumes = {
            os.path.abspath(config.worktree_path): {
                'bind': '/workspace',
                'mode': 'rw'
            }
        }

        # Run agent command in container
        container = self._get_client().containers.run(
            image,
            command=f"vibe -p '{config.task}'",
            volumes=volumes,
            working_dir='/workspace',
            detach=True,
            environment=config.extra_env
        )

        session_id = f"docker-{config.name}-{container.short_id}"
        self._containers[session_id] = container
        self._configs[session_id] = config
        self._last_output[session_id] = f"Container {container.short_id} started."

        return session_id

    async def sync_worktree(self, local_path: str, remote_path: str) -> bool:
        # Handled by Docker volumes mount in spawn()
        return True

    async def fetch_results(self, remote_path: str, local_path: str) -> bool:
        # Handled by Docker volumes mount
        return True

    async def stream_output(self, session_id: str) -> AsyncIterator[str]:
        container = self._containers.get(session_id)
        if not container: return

        # Stream logs from container
        for line in container.logs(stream=True, follow=True):
            text = line.decode('utf-8').strip()
            if text:
                self._last_output[session_id] = text
                yield text

    async def get_status(self, session_id: str) -> AgentStatus:
        container = self._containers.get(session_id)
        config = self._configs.get(session_id)
        
        if not container:
            state = "error"
        else:
            container.reload()
            state = "running" if container.status == "running" else "done"

        return AgentStatus(
            name=config.name if config else session_id,
            role=config.role if config else "unknown",
            state=state,
            current_task=config.task if config else "",
            runtime=self.runtime_name,
            last_output=self._last_output.get(session_id, "")
        )

    async def send_message(self, session_id: str, message: str) -> None:
        pass

    async def kill(self, session_id: str) -> None:
        container = self._containers.pop(session_id, None)
        if container:
            container.stop()
            container.remove()
