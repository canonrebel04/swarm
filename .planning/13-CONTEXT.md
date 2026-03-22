# Phase 13 Context: Multi-Swarm Coordination

## Overview
Phase 13 enables multiple Swarm instances to discover and coordinate with each other. This allows for a "Swarm of Swarms" architecture where specialized Swarms handle massive projects.

## Implementation Decisions

### Inter-Swarm Protocol
- **Discovery:** Use a simple shared SQLite database or a centralized registry (conceptual for now) to list active Swarms.
- **Messaging:** Extend the `EventBus` to support "Cross-Swarm" events via WebSockets or shared DB polling.
- **Handshaking:** Swarms must exchange role and capability manifests before delegating work.

### Hierarchical Swarms
- **Top Swarm:** Acts as the high-level project manager.
- **Sub-Swarms:** Act as "Super-Agents" that handle specific components (e.g., Frontend Swarm, Backend Swarm).
- **Delegation:** The `Coordinator` can now handoff a `TaskPacket` not just to an agent, but to an entire external Swarm.

### Shared Resource Management
- Implementation of a global "Resource Lock" to prevent multiple Swarms from modifying the same repository area (building on Phase 12's overlap detection).

## Gray Areas
- Security: How to authenticate remote Swarms? *Decision: Out of scope for Milestone 3; assume local/trusted network for now.*
- Latency: Multi-swarm event propagation delays. *Decision: Treat sub-swarms as asynchronous long-running tasks.*
