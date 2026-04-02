"""
FastAPI server for Swarm Control Plane & API.
"""

import asyncio
import os
import json
from typing import List, Dict, Any, Optional
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
    Security,
    Request,
)
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..orchestrator.coordinator import coordinator
from ..orchestrator.agent_manager import agent_manager
from ..messaging.event_bus import event_bus

# Define API key authentication
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_key(api_key_header: str = Security(api_key_header)) -> str:
    """Validate API key from header."""
    # In a real app, read from config/db. For MVP, we check an env var.
    expected_key = os.environ.get("SWARM_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=500, detail="Server configuration error: API key not set"
        )

    if api_key_header == expected_key:
        return api_key_header
    raise HTTPException(status_code=403, detail="Could not validate credentials")


app = FastAPI(title="Swarm API", version="1.0.0")

# Mount static files for the dashboard
# Using html=True so it serves index.html at root automatically if available
app.mount(
    "/dashboard", StaticFiles(directory="src/api/static", html=True), name="static"
)


# Models
class TaskRequest(BaseModel):
    objective: str


@app.get("/")
async def root():
    return {"message": "Swarm API running. Visit /dashboard for the UI."}


# --- REST API ---


@app.get("/api/v1/status", dependencies=[Depends(get_api_key)])
async def get_status():
    """Get overall Swarm status."""
    agent_count = await agent_manager.get_agent_count()
    return {
        "status": "online",
        "active_agents": agent_count,
        "queue_size": len(coordinator._task_queue),
        "history_size": len(coordinator._task_history),
    }


@app.get("/api/v1/tasks", dependencies=[Depends(get_api_key)])
async def get_tasks():
    """Get current tasks (active, queued, completed)."""
    return {
        "active": [t.__dict__ for t in coordinator._active_tasks.values()],
        "queued": [t.__dict__ for t in coordinator._task_queue],
        "history": [t.__dict__ for t in coordinator._task_history],
    }


@app.post("/api/v1/tasks", dependencies=[Depends(get_api_key)])
async def create_task(request: TaskRequest):
    """Submit a new high-level objective."""
    coordinator.handle_overseer_input(request.objective)
    return {"status": "accepted", "message": f"Objective queued: {request.objective}"}


@app.get("/api/v1/agents", dependencies=[Depends(get_api_key)])
async def get_agents():
    """List all active agents."""
    agents = await agent_manager.list_agents()
    return {"agents": [a.__dict__ for a in agents]}


@app.post("/api/v1/agents/{session_id}/kill", dependencies=[Depends(get_api_key)])
async def kill_agent(session_id: str):
    """Terminate a specific agent session."""
    success = await agent_manager.kill_agent(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "killed", "session_id": session_id}


# --- WebSocket ---


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass  # Connection closed abruptly


manager = ConnectionManager()


# Background task to bridge EventBus and WebSockets
async def event_bridge(event):
    """Callback attached to EventBus that broadcasts to WebSockets."""
    # Serialize event to JSON
    event_dict = {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "source": event.source,
        "data": event.data,
        "timestamp": event.timestamp,
        "session_id": event.session_id,
        "agent_name": event.agent_name,
        "target_swarm": event.target_swarm,
    }
    await manager.broadcast(json.dumps(event_dict))


@app.on_event("startup")
async def startup_event():
    # Subscribe to all events
    event_bus.subscribe("*", event_bridge)


@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time event streaming."""
    # Note: WebSocket auth is tricky via headers, often passed via query params or tokens.
    # For MVP, we'll keep the WS open or check a simple query param.
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, wait for client messages if any
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
