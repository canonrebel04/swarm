# Swarm Project Handoff ◈ Context Dump

## 1. Project Objective
Swarm is a provider-agnostic multi-agent orchestration system. It coordinates specialized worker agents (Scout, Developer, Builder, etc.) under a high-level Overseer. It features both a **btop-inspired TUI** and a **Web-based Mission Control**.

## 2. Current Status
- **Milestone 1-4: 100% Completed.**
- All 15 planned phases are implemented and verified.
- The project has evolved from a basic TUI to an autonomous system with multi-swarm coordination and a full web interface.

## 3. Key Architectural Components

### 🤖 Core Roles (11+)
- **Coordination:** Overseer, Coordinator, Supervisor, Lead.
- **Workers:** Scout, Developer, Builder, Tester.
- **Specialized:** Reviewer, Merger, Monitor, Arbiter, Reflection.
- **Contracts:** Enforced via YAML files in `src/roles/contracts/` and identity prompts in `src/agents/definitions/`.

### 🔌 Runtime Adapters
- **Local/CLI:** Claude Code, Gemini CLI, Mistral Vibe, Codex, OpenCode, Hermes (Ollama), Goose, Cline, Qodo Gen.
- **Remote/Cloud:** SSH Runtime (via `paramiko`), Docker Runtime (via `docker-py`).
- **Dynamic Models:** Auto-fetches model lists from Mistral, OpenAI, and Ollama `/v1/models` endpoints.

### ⛓ Orchestration Engine
- **Task DAG:** Uses a Directed Acyclic Graph for task dependencies (replaces linear lists).
- **Parallelism:** Spawns all independent "ready" tasks simultaneously.
- **Arbiter:** Autonomously resolves logical task overlaps and Git merge conflicts.
- **Meta-Learning:** Reflection agent analyzes Reviewer critiques to inject "Lessons Learned" into future prompts.

### 📡 Messaging & API
- **Event Bus:** SQLite-backed async event system with cross-swarm support.
- **FastAPI:** REST endpoints (`/tasks`, `/agents`) and WebSockets (`/ws/events`).
- **Control Plane:** A framework-free JS/SVG dashboard for remote monitoring.

## 4. Environment Requirements
- **Python:** 3.12+
- **Database:** SQLite (local `.polyglot/swarm.db`).
- **Dependencies:** `textual`, `fastapi`, `uvicorn`, `aiosqlite`, `paramiko`, `docker`, `rich`.
- **API Keys:** `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`.

## 5. Summary of Done (Recent Progress)
- **Phase 11:** Implement DAG-based Goal Decomposition v2.
- **Phase 12:** Implement Autonomous Conflict Resolution (Arbiter).
- **Phase 13:** Enable Multi-Swarm Coordination (Global locks & cross-swarm events).
- **Phase 14:** Build FastAPI server & WebSocket event bridge.
- **Phase 15:** Build Interactive Web Mission Control.

## 6. Future Roadmap (Milestone 5+)
- **Scale:** Better file synchronization for remote SSH agents (Rsync integration).
- **Security:** Full OAuth2/JWT implementation for the Web UI.
- **Vision:** Multi-modal support for UI-testing agents.
- **Persistence:** Transition from SQLite to PostgreSQL for multi-swarm deployments.

---
**Resume Point:** Project is at a stable "v1.0" state. All core features are functional. Next steps would involve stress-testing the multi-swarm coordination in a distributed environment.
