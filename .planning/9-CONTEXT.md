# Phase 9 Context: Meta-Learning Feedback Loops

## Overview
Phase 9 introduces self-improvement capabilities to the Swarm. Agents will learn from past Reviewer rejections and feedback to adjust their future behavior.

## Implementation Decisions

### Feedback Capture
- Extend the `reviewer` role's JSON handoff to include a mandatory `critique` field when status is `rejected`.
- Store these critiques in a new `experience` table in SQLite.

### Reflection Agent
- A specialized internal agent (using high-reasoning model like Opus or Gemini Pro) that periodically analyzes recent rejections.
- Generates "Lessons Learned" summaries for each role/task pair.

### Automated Prompt Tuning
- During `AgentConfig` creation, the `Coordinator` will fetch relevant "Lessons Learned" from the database.
- These will be injected as a "PAST EXPERIENCE" section in the system prompt.

## Gray Areas
- Should we use a Vector database for lesson retrieval? *Decision: Start with simple SQLite keyword matching; upgrade to vector if needed.*
- How often should the Reflection agent run? *Decision: Trigger after every N rejections or on-demand via the Supervisor.*
