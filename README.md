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
swarm init

# Configure your LLM providers and model selection
swarm setup
```

### 3. Launch TUI
```bash
swarm tui
```

---

## 🏗 Architecture

Swarm is built as a hierarchical orchestration system:

1.  **User**: Provides the high-level objective via the TUI.
2.  **Overseer** (`src/orchestrator/overseer.py`): LLM-backed brain that decomposes objectives into task DAGs. Falls back to heuristic decomposition when no LLM is available.
3.  **Coordinator** (`src/orchestrator/coordinator.py`): Manages task assignment, handoff chains, and conflict resolution.
4.  **Agent Fleet**: Specialized worker agents bound by specific roles, each in an isolated git worktree.

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

Swarm enforces strict **Role Locking** to prevent agent drift. Each agent is bound by a YAML contract (`src/roles/contracts/`) and a Markdown definition (`src/agents/definitions/`).

| Role | Mission | Allowed Actions |
| :--- | :--- | :--- |
| **Scout** | Exploration & Fact-finding | Read files, Grep, Search |
| **Developer** | Complex Implementation | Edit code, Plan, Test |
| **Builder** | Scoped execution | Write files, Build, Fix |
| **Tester** | Validation & QA | Run tests, Document bugs |
| **Reviewer** | Quality Audit | Audit changes, Feedback |
| **Merger** | Integration | Resolve conflicts, Merge |
| **Monitor** | Fleet Observability | Track health, Detect drift |
| **Coordinator** | Task Decomposition | Assign tasks, Manage handoffs |
| **Lead** | Team Leadership | Plan, Coordinate, Implement |

Tool policies are centralized in `src/roles/prompts.py` and enforced by:
- `src/safety/enforcer.py` — real-time tool policy validation
- `src/safety/fs_guard.py` — per-role filesystem access controls
- `src/safety/anti_drift.py` — regex-based drift detection with alert pipeline
- `src/safety/output_validator.py` — structured JSON handoff validation

---

## 🔌 Supported Runtimes

Swarm communicates with a variety of agent CLIs through standardized adapters (`src/runtimes/`):

| Runtime | Binary | Best For |
| :--- | :--- | :--- |
| **Claude Code** | `claude` | Multi-turn reasoning, complex implementation |
| **Mistral Vibe** | `vibe` | Fast execution, task-first implementation |
| **Gemini CLI** | `gemini` | Deep analysis, large-context exploration |
| **Codex CLI** | `codex` | OpenAI-powered task execution |
| **OpenCode** | `opencode` | SSE-based interactive coding |
| **Hermes** | `hermes` | Local model support via Ollama |
| **Goose** | `goose` | Extended task-first agent |
| **Cline** | `cline` | CLI-based coding agent |
| **Qodo** | `qodo` | Gen CLI agent |
| **OpenClaw** | `openclaw` | Experimental agent |
| **SSH** | — | Remote execution via paramiko |
| **Docker** | — | Containerized execution |
| **Echo** | — | Testing / simulation |

---

## 🛡 Safety & Isolation

- **Worktree Isolation**: Every active agent operates in its own `git worktree`.
- **Tool Policy Enforcement** (`src/safety/enforcer.py`): Validates tool invocations against role policies in real-time.
- **Filesystem Guards** (`src/safety/fs_guard.py`): Blocks access to sensitive paths; read-only roles cannot write.
- **Anti-Drift Monitor** (`src/safety/anti_drift.py`): Regex detection of forbidden tool usage with escalation alerts.
- **Output Validation** (`src/safety/output_validator.py`): Validates JSON handoff blocks against schema.
- **Watchdog Escalation**: nudge → respawn → supervisor alert for stalled/errant agents.

---

## 🛠 CLI Reference

| Command | Description |
| :--- | :--- |
| `swarm init` | Initialize a new swarm project |
| `swarm setup` | Interactive model and provider configuration |
| `swarm tui` | Launch the main coordination interface |
| `swarm doctor` | Run diagnostic checks on your environment |
| `swarm logs` | View recent system events and agent activity |
| `swarm cleanup` | Remove active worktrees and temporary files |
| `swarm serve` | Launch the FastAPI web control plane |
| `swarm roles` | List all available agent roles |
| `swarm runtimes` | List all supported runtimes and their status |

---

## ⚖ License

MIT
