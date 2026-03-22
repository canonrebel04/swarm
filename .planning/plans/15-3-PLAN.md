# Plan 15-3: Task Graph & Chat Integration

## Objective
Implement visual task coordination and interactive Overseer communication.

## Tasks
1. **Graph Rendering**: Create `src/api/static/components/TaskGraph.js` using SVG to render the dependency DAG.
2. **Dynamic Nodes**: Nodes should change color based on task status (Queued, Active, Done, Failed).
3. **Chat Interface**: Create `src/api/static/components/OverseerChat.js` for submitting new objectives.
4. **Final Polish**: Implement the Dark/Light mode toggle and ensure mobile responsiveness.

## Verification
- [ ] Task graph accurately reflects the relationships between tasks in the queue.
- [ ] Submitting a message in the Web Chat triggers a new decomposition in the Swarm.
- [ ] Mobile view collapses sidebars correctly.
