import asyncio
from typing import AsyncIterator, Optional
from .base import AgentRuntime, AgentConfig, AgentStatus, RuntimeCapabilities
from ..messaging.event_bus import event_bus

class RemoteSwarmRuntime(AgentRuntime):
    """
    Adapter for delegating tasks to external Swarm instances.
    """

    def __init__(self) -> None:
        self._configs: dict[str, AgentConfig] = {}
        self._statuses: dict[str, str] = {}
        self._last_output: dict[str, str] = {}

    @property
    def runtime_name(self) -> str:
        return "remote_swarm"

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            interactive_chat=False,
            headless_run=True,
            resume_session=False,
            streaming_output=True,
            parallel_safe=True,
        )

    async def spawn(self, config: AgentConfig) -> str:
        target_swarm_id = config.remote_host  # Use remote_host field for swarm ID
        if not target_swarm_id:
            raise ValueError("target_swarm (passed via remote_host) is required")

        session_id = f"remote_swarm-{target_swarm_id}-{config.name}"
        self._configs[session_id] = config
        self._statuses[session_id] = "running"
        self._last_output[session_id] = f"Delegating task to swarm: {target_swarm_id}..."

        # Emit delegation event
        await event_bus.emit(
            event_type="delegate_task",
            source="remote_swarm_runtime",
            data={
                "task": config.task,
                "role_required": config.role,
                "parent_session": session_id
            },
            session_id=session_id,
            target_swarm=target_swarm_id
        )

        return session_id

    async def get_status(self, session_id: str) -> AgentStatus:
        config = self._configs.get(session_id)
        state = self._statuses.get(session_id, "error")
        return AgentStatus(
            name=config.name if config else session_id,
            role=config.role if config else "unknown",
            state=state,
            current_task=config.task if config else "",
            runtime=self.runtime_name,
            last_output=self._last_output.get(session_id, "")
        )

    async def stream_output(self, session_id: str) -> AsyncIterator[str]:
        # In a full implementation, this would yield events received from the target swarm
        yield f"Waiting for completion from remote swarm..."

    async def send_message(self, session_id: str, message: str) -> None:
        config = self._configs.get(session_id)
        if config and config.remote_host:
            await event_bus.emit(
                event_type="remote_message",
                source="remote_swarm_runtime",
                data={"message": message},
                session_id=session_id,
                target_swarm=config.remote_host
            )

    async def kill(self, session_id: str) -> None:
        config = self._configs.pop(session_id, None)
        self._statuses.pop(session_id, None)
        self._last_output.pop(session_id, None)
        if config and config.remote_host:
            await event_bus.emit(
                event_type="cancel_task",
                source="remote_swarm_runtime",
                data={},
                session_id=session_id,
                target_swarm=config.remote_host
            )
