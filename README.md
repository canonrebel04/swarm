# Swarm - Multi-Agent Orchestration System

Swarm is a distributed multi-agent system for orchestrating autonomous AI agents, enabling parallel task execution, resource management, and inter-agent communication.

## Features

- **Agent Orchestration**: Spawn, monitor, and manage AI agents across multiple runtimes.
- **OpenAI-Compatible Providers**: Use any v1 API — OpenRouter, Groq, Together, DeepSeek, vLLM, Ollama, or your own endpoint.
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
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   Or with Poetry:
   ```bash
   poetry install
   ```

3. Run the setup wizard to configure your LLM provider:
   ```bash
   swarm setup
   ```

   You'll be prompted to pick a provider:
   - **Anthropic** — Claude Opus / Sonnet / Haiku (requires `ANTHROPIC_API_KEY`)
   - **OpenAI** — GPT-4o, o3-mini, etc. (requires `OPENAI_API_KEY`)
   - **Google** — Gemini 2.5 Pro / Flash (requires `GOOGLE_API_KEY`)
   - **Mistral** — Mistral Large / Small / Codestral (requires `MISTRAL_API_KEY`)
   - **Ollama** — Local models via `http://localhost:11434`
   - **OpenAI-compatible** — Any v1 API endpoint (OpenRouter, Groq, vLLM, etc.)

   For OpenAI-compatible providers, you'll enter:
   - Base URL (e.g. `https://api.openrouter.ai`)
   - API key (saved to `.env`)
   - Pick a model from the live model list

   Settings are saved to `config.yaml`.

4. Launch the TUI:
   ```bash
   swarm tui
   ```

   Or start the API server + dashboard:
   ```bash
   swarm serve
   ```
   Then open `http://localhost:8000/dashboard`

## CLI Commands

| Command | Description |
|---------|-------------|
| `swarm setup` | Interactive provider & model configuration |
| `swarm doctor` | Diagnostic checks (deps, binaries, API keys) |
| `swarm doctor --verify` | Runtime connectivity verification |
| `swarm tui` | Launch the Textual TUI dashboard |
| `swarm serve` | Start REST API + WebSocket server |
| `swarm logs` | View recent agent events |
| `swarm roles` | List available agent roles |
| `swarm runtimes` | List supported runtimes + status |
| `swarm cleanup` | Remove active worktrees |
| `swarm init` | Initialize a new Swarm project directory |

## Supported Runtimes

Swarm orchestrates agents across these runtimes:

| Runtime | Binary | Description |
|---------|--------|-------------|
| Claude Code | `claude` | Anthropic's coding agent |
| Vibe | `vibe` | Mistral's coding agent |
| Codex | `codex` | OpenAI's coding agent |
| Gemini | `gemini` | Google's coding agent |
| Hermes | `hermes` | Nous Research agent |
| OpenCode | `opencode` | OpenCode CLI |
| OpenClaw | `openclaw` | Multi-channel AI gateway |
| Goose | `goose` | Block's coding agent |
| Cline | `cline` | VS Code agent |
| Qodo | `qodo` | Qodo Merge agent |
| Docker | - | Ephemeral container agents |
| SSH | - | Remote host agents |

## OpenAI-Compatible Provider API

Use any endpoint that exposes `/v1/models` and `/v1/chat/completions`:

```python
from src.utils.provider import ProviderConfig, fetch_models, chat_completion

config = ProviderConfig(
    base_url="https://api.openrouter.ai",
    api_key="sk-...",
    model="anthropic/claude-sonnet-4",
)

models = await fetch_models(config)
response = await chat_completion(config, [{"role": "user", "content": "..."}])
```

### Supported Provider URLs

| Provider | Base URL |
|----------|----------|
| OpenRouter | `https://api.openrouter.ai` |
| Groq | `https://api.groq.com/openai` |
| Together AI | `https://api.together.xyz` |
| DeepSeek | `https://api.deepseek.com` |
| Fireworks | `https://api.fireworks.ai/inference` |
| vLLM (local) | `http://localhost:8000` |
| Ollama (local) | `http://localhost:11434` |
| LiteLLM (proxy) | `http://localhost:4000` |

## Documentation

- [Architecture](./docs/architecture.md) (if exists)
- [API Reference](./docs/api.md)
- [Security Guidelines](./.jules/sentinel.md)

## Contributing

Pull requests are welcome. Please ensure your changes pass existing tests and add new tests as needed.

## License

MIT