# Plan 02-3: Create Role Contracts

## Objective
Create the YAML role contract files for the remaining core roles in `src/roles/contracts/` to enforce role locking and anti-drift policies.

## Tasks
1. **Orchestrator Contract**: Create `src/roles/contracts/orchestrator.yaml`.
2. **Coordinator Contract**: Create `src/roles/contracts/coordinator.yaml`.
3. **Supervisor Contract**: Create `src/roles/contracts/supervisor.yaml`.
4. **Lead Contract**: Create `src/roles/contracts/lead.yaml`.
5. **Reviewer Contract**: Create `src/roles/contracts/reviewer.yaml`.
6. **Merger Contract**: Create `src/roles/contracts/merger.yaml`.
7. **Monitor Contract**: Create `src/roles/contracts/monitor.yaml`.

## Verification
- [ ] All YAML files exist in `src/roles/contracts/`.
- [ ] Each file defines identity, mission, may/may_not permissions, and required outputs.
- [ ] Each file includes handoff rules that align with the orchestration hierarchy.
