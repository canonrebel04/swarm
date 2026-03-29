"""
Merge manager for handling agent handoffs and resolving conflicts.

This module watches for completed agent tasks, checks for conflicts,
and either auto-merges clean work or assigns merger agents for conflicts.
"""

from __future__ import annotations
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
import json
import subprocess
import os
import time

from .agent_manager import agent_manager
from .coordinator import Coordinator, TaskPacket
from ..messaging.event_bus import event_bus
from ..worktree.manager import worktree_manager


@dataclass
class HandoffEvent:
    """Represents an agent handoff event."""

    from_agent: str
    to_agent: str
    status: str
    task_title: str
    worktree_branch: str
    data: dict


class MergeManager:
    """Manages agent handoffs and merge operations."""

    def __init__(self, coordinator: Coordinator):
        self.coordinator = coordinator
        self.active_merges: Dict[str, str] = {}  # task_title → merger_agent
        self._setup_event_listeners()

    def _setup_event_listeners(self) -> None:
        """Set up event listeners for handoff events."""
        # Subscribe to handoff-related events
        event_bus.subscribe("handoff", self._handle_handoff_event)
        event_bus.subscribe("merge_completed", self._handle_merge_completion)

    async def _handle_handoff_event(self, event: Dict) -> None:
        """Handle handoff events from agents."""
        try:
            # Parse handoff data
            handoff = self._parse_handoff_event(event)

            if handoff.status == "done":
                await self.process_completed_handoff(handoff)

        except Exception as e:
            await event_bus.emit(
                "error",
                "merge-manager",
                {"message": f"Failed to handle handoff: {str(e)}"},
            )

    def _parse_handoff_event(self, event_data: Dict) -> HandoffEvent:
        """Parse handoff event data."""
        data = event_data.get("data", {})

        return HandoffEvent(
            from_agent=data.get("from_agent", "unknown"),
            to_agent=data.get("to_agent", "unknown"),
            status=data.get("status", "unknown"),
            task_title=data.get("task_title", "unknown"),
            worktree_branch=data.get("worktree_branch", "unknown"),
            data=data,
        )

    async def process_completed_handoff(self, handoff: HandoffEvent) -> None:
        """Process a completed handoff and attempt merge."""
        await event_bus.emit(
            "info",
            "merge-manager",
            {"message": f"Processing handoff from {handoff.from_agent}"},
        )

        # Check for conflicts
        conflicts = await self._check_for_conflicts(handoff)

        if conflicts:
            await self._handle_merge_conflicts(handoff, conflicts)
        else:
            await self._perform_auto_merge(handoff)

    async def _check_for_conflicts(self, handoff: HandoffEvent) -> List[str]:
        """Check for conflicts using git merge-tree."""
        return await self._simple_conflict_check(handoff)

    async def _simple_conflict_check(self, handoff: HandoffEvent) -> List[str]:
        """Conflict detection using git diff between worktree and main."""
        conflicts = []
        worktree_path = os.path.join(
            worktree_manager.base_path, handoff.worktree_branch
        )

        if not os.path.isdir(worktree_path):
            return conflicts

        try:
            # Get list of files modified in the worktree branch
            result = subprocess.run(
                ["git", "diff", "--name-only", "main...HEAD"],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            modified_files = [f for f in result.stdout.strip().splitlines() if f]

            # Check if those files are also modified by other active agents
            active_agents = await agent_manager.list_agents()
            for agent in active_agents:
                agent_wt = os.path.join(worktree_manager.base_path, agent.name)
                if not os.path.isdir(agent_wt) or agent_wt == worktree_path:
                    continue
                try:
                    other_result = subprocess.run(
                        ["git", "diff", "--name-only", "main...HEAD"],
                        cwd=agent_wt,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    other_files = set(other_result.stdout.strip().splitlines())
                    overlap = set(modified_files) & other_files
                    if overlap:
                        conflicts.extend(overlap)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    continue

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        return list(set(conflicts))

    async def _handle_merge_conflicts(
        self, handoff: HandoffEvent, conflicts: List[str]
    ) -> None:
        """Handle merge conflicts by assigning a merger agent."""
        await event_bus.emit(
            "merge_conflict",
            "merge-manager",
            {
                "task_title": handoff.task_title,
                "conflicting_files": conflicts,
                "from_agent": handoff.from_agent,
                "to_agent": handoff.to_agent,
            },
        )

        # Create a merge task for the merger agent
        merge_task = self._create_merge_task(handoff, conflicts)

        # Assign the merge task to a merger agent
        session_id = await self.coordinator.assign_task(merge_task)

        if session_id:
            self.active_merges[handoff.task_title] = session_id
            await event_bus.emit(
                "info",
                "merge-manager",
                {
                    "message": f"Assigned merger agent {session_id} for conflicts in {handoff.task_title}"
                },
            )
        else:
            await event_bus.emit(
                "error",
                "merge-manager",
                {"message": f"Failed to assign merger agent for {handoff.task_title}"},
            )

    def _create_merge_task(
        self, handoff: HandoffEvent, conflicts: List[str]
    ) -> "TaskPacket":
        """Create a merge task for the merger agent."""
        # Import TaskPacket from coordinator module
        from .coordinator import TaskPacket

        conflict_list = ", ".join(conflicts[:3]) + ("..." if len(conflicts) > 3 else "")

        return TaskPacket(
            id=f"merge-{len(self.active_merges) + 1}",
            title=f"Resolve merge conflicts in {handoff.task_title}",
            description=(
                f"Resolve conflicts in files: {conflict_list}\n\n"
                f"Original task: {handoff.task_title}\n"
                f"From agent: {handoff.from_agent}\n"
                f"Worktree: {handoff.worktree_branch}"
            ),
            role_required="merger",
            runtime_preference=[
                "mistral-vibe",
                "openclaw",
            ],  # Best for merge resolution
            priority="high",
            files_in_scope=conflicts,
            acceptance_criteria=[
                "All conflicts resolved",
                "Code compiles and tests pass",
                "Original functionality preserved",
            ],
            parent_agent=handoff.from_agent,
        )

    async def _perform_auto_merge(self, handoff: HandoffEvent) -> None:
        """Perform automatic merge for non-conflicting changes."""
        await event_bus.emit(
            "info",
            "merge-manager",
            {"message": f"Auto-merging worktree {handoff.worktree_branch}"},
        )

        try:
            # Get the worktree path
            worktree_path = os.path.join(
                worktree_manager.base_path, handoff.worktree_branch
            )
            if not os.path.isdir(worktree_path):
                raise ValueError(
                    f"Worktree {handoff.worktree_branch} not found at {worktree_path}"
                )

            # Change to worktree directory
            original_dir = os.getcwd()
            os.chdir(worktree_path)

            try:
                # Perform the merge
                result = subprocess.run(
                    [
                        "git",
                        "merge",
                        "--no-ff",
                        "-m",
                        f"Auto-merge: {handoff.task_title}",
                        "main",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                await event_bus.emit(
                    "merge_success",
                    "merge-manager",
                    {
                        "task_title": handoff.task_title,
                        "worktree": handoff.worktree_branch,
                        "merge_output": result.stdout,
                    },
                )

                # Update worktree snapshot
                await self._update_worktree_snapshot(handoff)

                # Cleanup worktree after successful merge
                await self._cleanup_worktree(handoff)

            finally:
                os.chdir(original_dir)

        except subprocess.CalledProcessError as e:
            # Extract conflicting files from git output
            conflicting_files = []
            for line in e.stdout.split("\n"):
                if line.startswith("CONFLICT"):
                    parts = line.split(":")
                    if len(parts) > 1:
                        conflicting_files.append(parts[1].strip().split()[1])

            await event_bus.emit(
                "merge_conflict",
                "merge-manager",
                {
                    "task_title": handoff.task_title,
                    "conflicting_files": conflicting_files or ["unknown"],
                    "from_agent": handoff.from_agent,
                    "error": e.stderr or e.stdout,
                },
            )
            # Fall back to manual/agentic merge
            await self._handle_merge_conflicts(
                handoff, conflicting_files or ["merge_failed"]
            )
        except Exception as e:
            await event_bus.emit(
                "error",
                "merge-manager",
                {
                    "message": f"Unexpected error during merge: {str(e)}",
                    "worktree": handoff.worktree_branch,
                },
            )

    async def _update_worktree_snapshot(self, handoff: HandoffEvent) -> None:
        """Update worktree snapshot after successful merge."""
        try:
            worktree_path = os.path.join(
                worktree_manager.base_path, handoff.worktree_branch
            )
            if not os.path.isdir(worktree_path):
                return

            result = subprocess.run(
                ["git", "diff", "--name-only", "main...HEAD"],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            modified_files = [f for f in result.stdout.strip().splitlines() if f]

            await event_bus.emit(
                "info",
                "merge-manager",
                {
                    "message": f"Snapshot: {len(modified_files)} files merged from {handoff.worktree_branch}",
                    "files": modified_files,
                },
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception):
            pass

    async def _cleanup_worktree(self, handoff: HandoffEvent) -> None:
        """Clean up worktree after successful merge."""
        try:
            # Remove the worktree since it's been merged
            worktree_manager.remove_worktree(handoff.worktree_branch)

            await event_bus.emit(
                "info",
                "merge-manager",
                {"message": f"Cleaned up worktree {handoff.worktree_branch}"},
            )

        except Exception as e:
            await event_bus.emit(
                "warning",
                "merge-manager",
                {"message": f"Failed to cleanup worktree: {str(e)}"},
            )

    async def _handle_merge_completion(self, event: Dict) -> None:
        """Handle merge completion events."""
        task_title = event.get("data", {}).get("task_title")

        if task_title in self.active_merges:
            # Merge completed successfully
            await event_bus.emit(
                "merge_success",
                "merge-manager",
                {
                    "message": f"Merge completed for {task_title}",
                    "task_title": task_title,
                },
            )

            # Clean up
            del self.active_merges[task_title]


def get_merge_manager(coordinator: Coordinator) -> MergeManager:
    """Get the global merge manager instance."""
    # In a real implementation, this would be a singleton
    # For now, we'll create a new instance
    return MergeManager(coordinator)
