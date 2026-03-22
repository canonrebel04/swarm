# Phase 14 Context: Control Plane & API

## Overview
Phase 14 exposes Swarm's orchestration engine to the outside world. By providing a REST API and a Web-based dashboard, users can monitor and control Swarm instances without needing direct terminal access.

## Implementation Decisions

### API Framework
- **Choice:** FastAPI
- **Reason:** Native async support, excellent OpenAPI documentation generation, and high performance. Fits perfectly with Swarm's asyncio architecture.

### API Endpoints
- **REST (`/api/v1/...`):**
    - `GET /tasks`: List all tasks and their statuses.
    - `POST /tasks`: Submit a new high-level objective to the Overseer.
    - `GET /agents`: List active agents in the fleet.
    - `POST /agents/{id}/kill`: Terminate an agent session.
- **WebSockets (`/ws/events`):**
    - Stream real-time events from the `EventBus` to connected clients (crucial for the live dashboard).

### Web Dashboard
- **Scope:** Initial release will be a read-only monitoring dashboard.
- **Tech Stack:** Simple HTML/JS/CSS served statically by FastAPI, connecting to the WebSocket for live updates. No complex frontend framework required for MVP.

### Security
- **Authentication:** Implement basic API Key authentication using FastAPI dependencies. 
- **Tenancy:** Single-tenant for Milestone 3; multi-tenancy basics (associating tasks with API keys) will be sketched out but not fully enforced at the OS/worktree level yet.
