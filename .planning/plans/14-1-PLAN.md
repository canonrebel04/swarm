# Plan 14-1: FastAPI REST Server

## Objective
Expose Swarm's core orchestration capabilities via a REST API using FastAPI.

## Tasks
1. **Dependencies**: Add `fastapi` and `uvicorn` to project requirements.
2. **Server Setup**: Create `src/api/server.py` with basic FastAPI app initialization.
3. **Endpoints**:
    - `GET /api/v1/status`: Returns overall Swarm health and active agent count.
    - `GET /api/v1/tasks`: Returns the current task queue and history from the `Coordinator`.
    - `POST /api/v1/tasks`: Accepts a new objective and passes it to `Coordinator.handle_overseer_input`.
    - `GET /api/v1/agents`: Returns list of active agents via `agent_manager.list_agents()`.
4. **CLI Integration**: Add a `swarm serve` command to `src/cli/app.py` to launch the API server.

## Verification
- [ ] `uvicorn src.api.server:app` runs without errors.
- [ ] `curl localhost:8000/api/v1/status` returns expected JSON.
