# UI Design Specification: Swarm Mission Control (Phase 15)

## 1. Vision
Transform the read-only dashboard into a comprehensive **Mission Control** interface for multi-agent orchestration. The Web UI should mirror the power of the TUI while leveraging web technologies for rich visualization (DAGs) and complex interactions (fleet steering).

## 2. Visual Language & Branding
- **Theme:** "Tokyo Night" (Dark-first, high-contrast syntax highlighting).
- **Core Colors:**
    - Background: `#1a1b26` (Deep Navy)
    - Surface: `#24283b` (Slate)
    - Primary: `#7aa2f7` (Soft Blue)
    - Accent: `#bb9af7` (Purple)
    - Success: `#9ece6a` (Green)
    - Error: `#f7768e` (Red)
- **Typography:** System monospaced font (e.g., "Fira Code", "JetBrains Mono") for all technical data; Sans-serif for navigation.

## 3. Layout Architecture (Mission Control)
A multi-pane, tiled layout inspired by `btop` and modern IDEs.

### A. Sidebar (Navigation & Status)
- Swarm status (Online/Offline/Syncing).
- Active agent count.
- Navigation links: Fleet, Tasks, Skills, Settings.

### B. Fleet Management Panel (Active Agents)
- **Card-based view** for each active agent.
- Metrics per agent: Status, Role, Runtime, Token Usage, Latency.
- **Controls:** Nudge (Message), Pause, Retry, Kill.

### C. Task Graph Visualization (DAG)
- **Core Component:** Dynamic, interactive SVG/Canvas-based task graph.
- **Node Status:**
    - Gray: Queued / Pending
    - Blue: Active
    - Green: Completed
    - Red: Failed
    - Pulse Animation: Currently executing.
- **Interactions:** Click node to view specific agent output/logs.

### D. Overseer Chat (Interactive)
- Unified chat interface to submit new objectives.
- Real-time streaming of Overseer thoughts and decomposition plans.

## 4. Component Architecture
- **WebSockets:** Persistent connection to `/ws/events` for all live updates.
- **State Management:** Simple reactive store (e.g., using a lightweight library or native JS proxies) to keep the UI synced with DB events.
- **Modular CSS:** BEM-like naming for dashboard components.

## 5. User Interaction Models
- **Task Submission:** "Command Palette" style entry or traditional chat input.
- **Human-in-the-Loop:** Pop-up modals for Arbiter decisions or high-risk tool approvals.
- **Responsive Design:** Adaptive layout for desktop, tablet, and mobile (read-only mode).

## 6. Technical Deliverables
- `src/api/static/index.html`: Main shell.
- `src/api/static/app.js`: Core logic, WebSocket handling, state management.
- `src/api/static/components/`: Modular JS components for Graph, Fleet, and Chat.
- `src/api/static/theme.css`: Global styles and theme variables.
