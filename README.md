# Swarm

**Provider-agnostic multi-agent orchestration TUI for coding agents**

## Overview

Swarm is a terminal-first multi-agent orchestration system that supports popular coding-agent CLIs including Claude Code, Codex CLI, Gemini CLI, Aider, OpenHands CLI, OpenCode, Goose, Cline CLI, Qodo Gen CLI, Mistral Vibe, Hermes-based local agents, and OpenClaw.

## Features

- **Overseer + Worker Fleet Interface**: Visible coordination between overseer and worker agents
- **Role-Stable Agents**: Agents stay within their assigned roles with strict contracts
- **Provider/Runtime Portability**: Support for cloud and local models
- **Extensible Architecture**: Easy to add new agent runtimes
- **Interactive & Headless Modes**: Support for both terminal agents and CI/task agents

## Installation

```bash
# Using pip (when published)
pip install swarm

# From source
poetry install
```

## Quick Start

```bash
# Initialize a new swarm
swarm init

# Run the swarm
swarm run

# Check status
swarm status
```

## Architecture

```text
┌────────────────────────────────────────────────────────────────────┐
│                        Swarm TUI                          │
├──────────────────────────────────┬─────────────────────────────────────┤
│        OVERSEER CHAT         │          AGENT FLEET                │
│  [User] build feature X      │  lead-1       running   claude      │
│  [Overseer] spawning lead    │  builder-1    running   aider       │
│  [Overseer] scout first      │  tester-1     queued    gemini      │
│  [Overseer] nudging builder  │  reviewer-1   stalled   codex       │
│                              │  merger-1     waiting   opencode    │
├──────────────────────────────────┴─────────────────────────────────────┤
│                  SELECTED AGENT OUTPUT / EVENTS                    │
│  builder-1: reading files...                                       │
│  builder-1: edited auth.py                                         │
│  builder-1: ready for tests                                        │
└────────────────────────────────────────────────────────────────────┘
```

## Supported Runtimes

### Tier 1 (Full Support)
- Claude Code
- Codex CLI
- Gemini CLI
- Aider
- OpenHands CLI
- OpenCode
- Mistral Vibe
- Hermes (local models)

### Tier 2 (High Value)
- Goose
- Cline CLI
- Qodo Gen CLI
- OpenClaw

## Agent Roles

- **Orchestrator**: Multi-project coordinator
- **Coordinator**: Task decomposition and assignment
- **Supervisor**: Fleet oversight and intervention
- **Lead**: Team-level coordination
- **Scout**: Code exploration and fact gathering
- **Developer**: Complex implementation
- **Builder**: Fast execution tasks
- **Tester**: Validation and testing
- **Reviewer**: Code review
- **Merger**: Branch merging
- **Monitor**: Health monitoring

## Configuration

Edit `config.yaml` to configure:
- Overseer settings
- Agent limits and timeouts
- Role definitions and contracts
- Runtime capabilities
- Messaging and worktree settings

## Development

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run linting
poetry run black .
poetry run isort .
poetry run mypy .
```

## License

MIT