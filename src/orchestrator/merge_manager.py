"""
Merge manager for handling agent handoffs and resolving conflicts.

This module watches for completed agent tasks, checks for conflicts,
and either auto-merges clean work or assigns merger agents for conflicts.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..messaging.event_bus import event_bus
from ..worktree.manager import worktree_manager
from .agent_manager import agent_manager
from .coordinator import Coordinator, TaskPacket


@dataclass
class HandoffEvent:
    """Represents an agent handoff event."""

    from_agent: str
    to_agent: str
    status: str
    task_title: str
    worktree_branch: str
    data: dict
    project_path: Optional[str] = None


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
            project_path=data.get("project_path"),
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
        """Check for conflicts using CodebaseIndex or fallback to advanced check."""
        try:
            from src.memory.codebase_index import CodebaseIndex

            index = CodebaseIndex()
            return await index.conflict_check(handoff.worktree_branch)
        except ImportError:
            await event_bus.emit(
                "warning",
                "merge-manager",
                {
                    "message": "CodebaseIndex not available. Falling back to simple conflict check."
                },
            )
            return await self._advanced_conflict_check(handoff)

    async def _advanced_conflict_check(self, handoff: HandoffEvent) -> List[str]:
        """Check for conflicts using git merge-tree."""
        conflicts = []
        worktree_path = os.path.join(
            worktree_manager.base_path, handoff.worktree_branch
        )

        if not os.path.isdir(worktree_path):
            return conflicts

        success = False
        try:
            # We use git merge-tree to perform a 3-way merge in memory.
            # `git merge-tree $(git merge-base main HEAD) main HEAD`
            # For git >= 2.38: `git merge-tree --write-tree main HEAD`
            # We'll use the older syntax for better compatibility if needed,
            # but --write-tree is much better at identifying conflicts.
            # Let's try --write-tree first.

            process = await asyncio.create_subprocess_exec(
                "git",
                "merge-tree",
                "--write-tree",
                "main",
                "HEAD",
                cwd=worktree_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=15
                )
                # If exit code is 0, no conflicts.
                # If exit code is non-zero (usually 1), there are conflicts.
                if process.returncode == 0:
                    success = True
                elif process.returncode == 1:
                    success = True
                    # Parse conflicting files from stdout
                    # The output format of `git merge-tree --write-tree` contains:
                    # <OID>
                    # <OID> <OID> <OID> <filename>
                    for line in stdout.decode().strip().splitlines():
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            # Conflicting file path is usually the last part after the tab
                            conflicting_file = parts[-1]
                            conflicts.append(conflicting_file)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

        except Exception as e:
            await event_bus.emit(
                "warning",
                "merge-manager",
                {"message": f"Advanced conflict check failed: {str(e)}"},
            )

        # In case the git version doesn't support --write-tree or it failed,
        # fallback to the simple conflict check logic to maintain some level of detection
        if not success:
            conflicts.extend(await self._simple_conflict_check(handoff))

        return list(set(conflicts))

    async def _get_git_diff_async(self, worktree_path: str) -> Optional[str]:
        """Helper to run git diff asynchronously."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "diff",
                "--name-only",
                "main...HEAD",
                cwd=worktree_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            if proc.returncode != 0:
                return None
            return stdout.decode().strip()
        except (asyncio.TimeoutError, Exception):
            if "proc" in locals() and proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            return None

    async def _simple_conflict_check(self, handoff: HandoffEvent) -> List[str]:
        """Conflict detection using git diff between worktree and main."""
        conflicts = []
        worktree_path = os.path.join(
            worktree_manager.base_path, handoff.worktree_branch
        )

        if not os.path.isdir(worktree_path):
            return conflicts

        # ⚡ Bolt Optimization: Replaced blocking subprocess.run calls with asyncio.create_subprocess_exec
        # and asyncio.gather to avoid blocking the event loop and parallelize N+1 I/O-bound git operations
        # over all active agents' worktrees.
        diff_output = await self._get_git_diff_async(worktree_path)
        if diff_output is None:
            return conflicts

        modified_files = [f for f in diff_output.splitlines() if f]
        if not modified_files:
            return conflicts

        # Check if those files are also modified by other active agents
        active_agents = await agent_manager.list_agents()
        agent_wts = []
        for agent in active_agents:
            agent_wt = os.path.join(worktree_manager.base_path, agent.name)
            if os.path.isdir(agent_wt) and agent_wt != worktree_path:
                agent_wts.append(agent_wt)

        # Run all diffs concurrently
        if agent_wts:
            diff_results = await asyncio.gather(
                *[self._get_git_diff_async(wt) for wt in agent_wts],
                return_exceptions=True,
            )

            for result in diff_results:
                if isinstance(result, str) and result:
                    other_files = set(result.splitlines())
                    overlap = set(modified_files) & other_files
                    if overlap:
                        conflicts.extend(overlap)

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
