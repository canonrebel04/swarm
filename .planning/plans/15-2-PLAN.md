# Plan 15-2: Interactive Fleet Panel

## Objective
Implement an interactive panel for managing the active agent fleet.

## Tasks
1. **Component Design**: Create `src/api/static/components/AgentCard.js` to render individual agent status and metrics.
2. **Metrics Display**: Show real-time token usage, latency, and status badges on each card.
3. **Action Controls**: Implement "Nudge", "Pause", "Retry", and "Kill" buttons on each card.
4. **API Integration**: Link buttons to the corresponding `/api/v1/agents/{id}/...` endpoints.

## Verification
- [ ] Agent cards appear and disappear in sync with spawns/kills.
- [ ] Clicking "Kill" on a card successfully terminates the agent session via the API.
- [ ] Status updates (e.g., from Running to Done) are reflected on the cards.
