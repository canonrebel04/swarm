# Phase 12 Context: Autonomous Conflict Resolution

## Overview
Phase 12 introduces mechanisms to detect and resolve semantic and structural conflicts between agent tasks. This prevents agents from working at cross-purposes and automates the resolution of Git merge conflicts using LLM reasoning.

## Implementation Decisions

### Logical Conflict Detection
- **Mechanism:** The `Coordinator` will scan proposed task packets for "semantic overlap" (e.g., two tasks modifying the same file or architectural component simultaneously).
- **Flagging:** Overlapping tasks are flagged as `potential_conflict` and paused for Arbiter review.

### The Arbiter Role
- **Identity:** High-level judge with final authority.
- **Mission:** Resolve disagreements between agents or decide the best path when task overlap is detected.
- **Tools:** Access to `git diff`, task history, and architectural documentation.
- **Output:** A resolution plan (e.g., "Sequentialize Task A and B", "Cancel Task C", "Merge Task D into E").

### Automated Merge Resolution
- **Integration:** Upgrade `MergeManager` to spawn a "Fixer" agent when `git merge` fails.
- **Logic:** The Fixer reads conflict markers, analyzes the intent of both branches, and applies a combined fix.
- **Validation:** Automated tests must pass in the merged worktree before the fix is accepted.

### Conflict Learning
- Store conflict resolution outcomes in the `experience_logs` table (from Phase 9) to help future Overseers avoid creating conflicting plans.

## Gray Areas
- **Manual vs. Auto Arbiter:** *Decision: Default to an automated Arbiter agent; escalate to human only if the agent fails or confidence is low.*
- **Concurrency Impact:** *Decision: Resolving conflicts may temporarily reduce fleet parallelization as tasks are sequentialized.*
