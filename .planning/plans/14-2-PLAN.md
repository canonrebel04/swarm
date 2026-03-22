# Plan 14-2: WebSocket Event Streaming

## Objective
Stream real-time events from Swarm's `EventBus` to connected remote clients.

## Tasks
1. **WebSocket Endpoint**: Create `@app.websocket("/ws/events")` in `src/api/server.py`.
2. **EventBus Integration**: 
    - Create a bridging function that subscribes to `*` (all events) on the `EventBus`.
    - When an event fires, push the JSON-serialized data to an `asyncio.Queue` for the active WebSocket connection.
3. **Connection Management**: Handle client connects/disconnects gracefully without leaking event subscriptions.

## Verification
- [ ] Connecting via a tool like `wscat` or a simple HTML page shows real-time JSON events as tasks are processed.
