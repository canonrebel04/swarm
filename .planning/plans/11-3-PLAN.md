# Plan 11-3: Task Graph Visualization

## Objective
Provide a visual representation of the active task graph in the TUI.

## Tasks
1. **New Panel**: Create `src/tui/panels/task_graph.py` with `TaskGraphPanel`.
2. **Graph Rendering**: Use `Rich` or specialized Textual widgets to draw relationships between tasks.
3. **Status Sync**: Connect the panel to the `EventBus` to update task colors in real-time.
4. **Integration**: Add the panel to the `MainScreen` (potentially replacing or augmenting the fleet panel).

## Verification
- [ ] active task graph is visible in the TUI.
- [ ] Task status changes (e.g., from Blocked to Ready) are reflected visually.
