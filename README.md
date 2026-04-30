# Swarm - Multi-Agent Orchestration System

Swarm is a distributed multi-agent system for orchestrating autonomous AI agents, enabling parallel task execution, resource management, and inter-agent communication.

## Features

- **Agent Orchestration**: Spawn, monitor, and manage AI agents across multiple runtimes.
- **Task Graph Visualization**: Real-time DAG of tasks and dependencies.
- **Resource Locking**: Prevent conflicts with fine-grained resource locks.
- **Event Bus**: Real-time event streaming across the swarm.
- **Security**: API key authentication, SQL injection prevention, and security logging.
- **UI Dashboard**: Web-based mission control with live updates.

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/canonrebel04/swarm.git
   cd swarm
   ```

2. Create a virtual environment and install:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   Or with Poetry:
   ```bash
   poetry install
   ```

3. Set environment variables:
   ```bash
   export SWARM_API_KEY=your-secret-key
   ```

4. Verify installation:
   ```bash
   swarm --help
   ```

5. Launch the TUI:
   ```bash
   swarm tui
   ```
   Or start the API server:
   ```bash
   swarm serve
   ```

6. Open the dashboard at `http://localhost:8000/dashboard`

## Documentation

- [Architecture](./docs/architecture.md) (if exists)
- [API Reference](./docs/api.md)
- [Security Guidelines](./.jules/sentinel.md)

## Contributing

Pull requests are welcome. Please ensure your changes pass existing tests and add new tests as needed.

## License

MIT