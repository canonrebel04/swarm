# Swarm — Multi-Agent Orchestration System

Swarm is a provider-agnostic multi-agent orchestration TUI designed for coding agents. It provides a centralized interface to coordinate multiple specialized AI agents (workers) using various runtimes (Claude Code, Gemini CLI, Codex, etc.) under the guidance of a top-level Overseer.

## Project Overview

- **Purpose:** Visible coordination between an Overseer and a fleet of role-bound worker agents.
- **Core Technologies:**
    - **Language:** Python 3.12+
    - **TUI Framework:** [Textual](https://github.com/Textualize/textual)
    - **CLI Framework:** [Typer](https://typer.tiangolo.com/)
    - **Persistence:** SQLite (WAL mode) via `aiosqlite`
    - **Concurrency:** `asyncio` for non-blocking agent management
    - **Configuration:** Pydantic and YAML
- **Architecture:**
    - **Overseer:** Manages the high-level objective and decomposes tasks.
    - **Agent Fleet:** Specialized agents (Scout, Developer, Builder, Tester, etc.) executing sub-tasks.
    - **Runtime Adapters:** Standardized interface (`AgentRuntime`) for interacting with different agent CLIs.
    - **Event Bus:** Centralized, persistent messaging system for coordination and TUI updates.

## Key Directories and Files

- `src/runtimes/`: Contains the `AgentRuntime` base class and specific adapters (e.g., `claude_code.py`, `gemini.py`).
- `src/orchestrator/`: Core logic for managing agents (`agent_manager.py`) and coordination (`coordinator.py`).
- `src/messaging/`: Event bus and database logic for inter-agent communication.
- `src/tui/`: Textual-based TUI implementation (panels for chat, fleet status, and output).
- `src/agents/definitions/`: Markdown files defining the identity and constraints of each agent role.
- `src/roles/contracts/`: YAML definitions of role-based permissions and forbidden actions.
- `PROJECT_SCOPE.md`: Detailed architectural vision, roadmap, and best practices.

## Development Commands

### Setup and Installation
```bash
# Install dependencies with poetry
poetry install
```

### Running the Application
```bash
# Run the Swarm TUI
poetry run python src/main.py run

# Initialize a new swarm project
poetry run python src/main.py init
```

### Testing and Quality
```bash
# Run the test suite
poetry run pytest

# Linting and Type Checking
poetry run black .
poetry run isort .
poetry run mypy .
```

## Development Conventions

1. **Role Locking:** Agents must strictly adhere to their assigned roles. Never allow an agent to self-upgrade or drift into another role's responsibilities (e.g., a Scout should not edit code).
2. **Runtime Abstraction:** All new agent integrations must implement the `AgentRuntime` interface in `src/runtimes/base.py`.
3. **Event-Driven Communication:** Use the `event_bus` in `src/messaging/event_bus.py` for all significant state changes and agent communications.
4. **Worktree Isolation:** Each active agent should operate in its own `git worktree` to prevent file conflicts during concurrent execution.
5. **Async-First:** The core orchestrator and runtime adapters must be non-blocking using `asyncio`.
