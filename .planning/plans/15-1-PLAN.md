# Plan 15-1: Web UI Base & State Management

## Objective
Establish the foundational structure, theme, and real-time state management for the Swarm Web UI.

## Tasks
1. **Theming**: Create `src/api/static/theme.css` with the "Tokyo Night" variables and global styles.
2. **Layout Shell**: Update `src/api/static/index.html` to implement the multi-pane Sidebar + Grid layout.
3. **State Store**: Implement a reactive state store in `src/api/static/app.js` using native JS Proxies to track fleet and task changes.
4. **WebSocket Bridge**: Refine the WebSocket listener to update the State Store on every event.

## Verification
- [ ] UI renders with correct Tokyo Night colors.
- [ ] Sidebar displays live agent count.
- [ ] Console logs show state updates when WebSocket events arrive.
