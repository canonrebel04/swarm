# Swarm  ◈  Multi-Agent Orchestration System

**Provider-agnostic multi-agent orchestration TUI for coding agents.**

Swarm provides a centralized interface to coordinate multiple specialized AI agents (workers) using various runtimes (Claude Code, Gemini CLI, Mistral Vibe, etc.) under the guidance of a top-level Overseer.

---

## 🚀 Quick Start

### 1. Installation
```bash
git clone https://github.com/canonrebel04/swarm.git
cd swarm
poetry install
```

### 2. Initialization & Setup
```bash
# Initialize project directories and database
poetry run swarm init

# Configure your LLM providers and model selection
poetry run swarm setup
```

### 3. Launch TUI
```bash
poetry run swarm tui
```

---

## 🏗 Architecture

Swarm is built as a hierarchical orchestration system:

1.  **User**: Provides the high-level objective via the TUI.
2.  **Overseer**: An LLM-backed central brain that decomposes the objective into tasks.
3.  **Coordinator**: Internal logic managing agent lifecycles, worktrees, and data flow.
4.  **Agent Fleet**: Specialized worker agents bound by specific roles.

```text
┌────────────────────────────────────────────────────────────────────┐
│                             Swarm TUI                              │
├──────────────────────────────────┬─────────────────────────────────┤
│        OVERSEER CHAT             │          AGENT FLEET            │
│  [User] build feature X          │  lead-1      running   claude   │
│  [Overseer] spawning lead        │  builder-1   running   vibe     │
│  [Overseer] scout first          │  tester-1    queued    gemini   │
│  [Overseer] nudging builder      │  reviewer-1  stalled   codex    │
│                                  │  merger-1    waiting   opencode │
├──────────────────────────────────┴─────────────────────────────────┤
│                  SELECTED AGENT OUTPUT / EVENTS                    │
│  [builder-1] Running pytest...                                     │
│  [builder-1] Fix applied to src/auth.py                            │
│  [System] builder-1 reached 80% cost cap. Nudging...               │
└────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 Agent Roles & Contracts

Swarm enforces strict **Role Locking** to prevent agent drift. Each agent is bound by a YAML contract and a Markdown definition.

| Role | Mission | Allowed Actions |
| :--- | :--- | :--- |
| **Scout** | Exploration & Fact-finding | Read files, Grep, Search |
| **Developer** | Complex Implementation | Edit code, Plan, Test |
| **Builder** | Scoped execution | Write files, Build, Fix |
| **Tester** | Validation & QA | Run tests, Document bugs |
| **Reviewer** | Quality Audit | Audit changes, Feedback |
| **Merger** | Integration | Resolve conflicts, Merge |
| **Monitor** | Fleet Observability | Track health, Detect drift |

---

## 🔌 Supported Runtimes

Swarm communicates with a variety of agent CLIs through standardized adapters:

- **Claude Code**: Multi-turn reasoning and complex implementation.
- **Mistral Vibe**: Fast execution and task-first implementation.
- **Gemini CLI**: Deep analysis and large-context exploration.
- **Codex CLI**: OpenAI-powered task execution.
- **OpenCode**: SSE-based interactive coding server.
- **Hermes**: Local model support via Ollama/OpenAI-compat APIs.
- **Goose / Cline / Qodo**: Extended task-first agents.

---

## 🛡 Safety & Isolation

- **Worktree Isolation**: Every active agent operates in its own `git worktree` to prevent file conflicts.
- **Tool Policy Enforcement**: Permissions are enforced at the runtime level (e.g., Scouts are spawned in `--read-only` mode).
- **Anti-Drift Monitor**: Real-time inspection of agent output to detect and alert on role violations.
- **Structured Handoffs**: Tasks are only completed when a valid JSON handoff block is produced and validated.

---

## 🛠 CLI Reference

- `swarm init`: Initialize a new swarm project.
- `swarm setup`: Interactive model and provider configuration.
- `swarm tui`: Launch the main coordination interface.
- `swarm doctor`: Run diagnostic checks on your environment.
- `swarm logs`: View recent system events and agent activity.
- `swarm cleanup`: Remove active worktrees and temporary files.

---

## ⚖ License

MIT
