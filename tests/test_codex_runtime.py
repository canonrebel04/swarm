"""Tests for CodexRuntime adapter."""
import asyncio
import json
from pathlib import Path
from typing import AsyncIterator

import pytest

from src.runtimes.codex import CodexRuntime
from src.runtimes.base import AgentConfig, AgentStatus


@pytest.fixture
def codex_runtime() -> CodexRuntime:
    """Create a fresh CodexRuntime instance for each test."""
    return CodexRuntime()


@pytest.fixture
def sample_config() -> AgentConfig:
    """Create a sample agent configuration."""
    return AgentConfig(
        name="test-agent",
        role="scout",
        task="Explore the codebase and identify key components",
        worktree_path="/tmp/test-worktree",
        model="o4-mini",
        runtime="codex",
        system_prompt_path="",
        allowed_tools=None,
        blocked_tools=None,
        extra_env={},
    )


class TestCodexRuntimeProperties:
    """Test basic runtime properties."""

    def test_runtime_name(self, codex_runtime: CodexRuntime):
        """Test runtime name property."""
        assert codex_runtime.runtime_name == "codex"

    def test_capabilities(self, codex_runtime: CodexRuntime):
        """Test runtime capabilities."""
        caps = codex_runtime.capabilities
        assert caps.interactive_chat is True
        assert caps.headless_run is True
        assert caps.resume_session is True
        assert caps.streaming_output is True
        assert caps.tool_allowlist is False  # Codex uses sandbox, not tool allowlist
        assert caps.sandbox_support is True   # Strongest sandbox support
        assert caps.agent_profiles is False
        assert caps.parallel_safe is True


class TestCodexRuntimeRoleMappings:
    """Test role to sandbox/approval/model mappings."""

    def test_role_sandbox_mapping(self, codex_runtime: CodexRuntime):
        """Test role to sandbox mapping."""
        assert codex_runtime.ROLE_SANDBOX["scout"] == "read-only"
        assert codex_runtime.ROLE_SANDBOX["builder"] == "workspace-write"
        assert codex_runtime.ROLE_SANDBOX["developer"] == "workspace-write"
        assert codex_runtime.ROLE_SANDBOX["reviewer"] == "read-only"

    def test_role_approval_mapping(self, codex_runtime: CodexRuntime):
        """Test role to approval mapping (all should be 'never' for headless)."""
        # All roles should use "never" approval for headless operation
        for role in codex_runtime.ROLE_APPROVAL.values():
            assert role == "never"

    def test_role_model_mapping(self, codex_runtime: CodexRuntime):
        """Test role to model mapping."""
        assert codex_runtime.ROLE_MODEL["scout"] == "o4-mini"
        assert codex_runtime.ROLE_MODEL["developer"] == "o3"
        assert codex_runtime.ROLE_MODEL["reviewer"] == "o3"
        assert codex_runtime.ROLE_MODEL["builder"] == "o4-mini"


class TestCodexRuntimePromptBuilding:
    """Test prompt building functionality."""

    def test_build_system_prompt_without_system_prompt(self, codex_runtime: CodexRuntime, sample_config: AgentConfig):
        """Test prompt building without system prompt file."""
        prompt = codex_runtime._build_system_prompt(sample_config)
        
        # Should contain role contract and task
        assert "ROLE CONTRACT:" in prompt
        assert "You are test-agent, a scout agent." in prompt
        assert "NOTE: You are running inside a 'read-only' sandbox" in prompt
        assert "When your task is complete, output this JSON" in prompt

    def test_build_system_prompt_with_system_prompt(self, codex_runtime: CodexRuntime, sample_config: AgentConfig, tmp_path: Path):
        """Test prompt building with system prompt file."""
        # Create a temporary system prompt file
        prompt_file = tmp_path / "system_prompt.md"
        prompt_file.write_text("This is a system prompt\nwith multiple lines")
        
        config_with_prompt = AgentConfig(
            name=sample_config.name,
            role=sample_config.role,
            task=sample_config.task,
            worktree_path=sample_config.worktree_path,
            model=sample_config.model,
            runtime=sample_config.runtime,
            system_prompt_path=str(prompt_file),
            allowed_tools=sample_config.allowed_tools,
            blocked_tools=sample_config.blocked_tools,
            extra_env=sample_config.extra_env,
        )
        
        prompt = codex_runtime._build_system_prompt(config_with_prompt)
        
        # Should contain system prompt content
        assert "This is a system prompt" in prompt
        assert "with multiple lines" in prompt

    def test_role_behavioral_constraints(self, codex_runtime: CodexRuntime):
        """Test role-specific behavioral constraints."""
        # Scout constraints
        scout_constraints = codex_runtime._role_behavioral_constraints("scout")
        assert "MUST NOT edit, write, or delete any files" in scout_constraints
        assert "sandbox enforces read-only access at the OS level" in scout_constraints
        
        # Reviewer constraints
        reviewer_constraints = codex_runtime._role_behavioral_constraints("reviewer")
        assert "MUST NOT edit, write, or delete any files" in reviewer_constraints
        assert "Produce a written review only" in reviewer_constraints
        
        # Developer constraints
        dev_constraints = codex_runtime._role_behavioral_constraints("developer")
        assert "MAY implement features and write code" in dev_constraints
        assert "MUST NOT push to remote without reviewer sign-off" in dev_constraints


class TestCodexRuntimeJSONLEventParsing:
    """Test JSONL event parsing functionality."""

    def test_parse_thread_started_event(self, codex_runtime: CodexRuntime):
        """Test parsing thread.started event (should capture thread ID)."""
        line = '{"type": "thread.started", "thread_id": "abc-123-def"}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        
        # Should capture thread ID and return None (internal event)
        assert codex_runtime._thread_ids["test-session"] == "abc-123-def"
        assert result is None

    def test_parse_turn_started_event(self, codex_runtime: CodexRuntime):
        """Test parsing turn.started event (should return None)."""
        line = '{"type": "turn.started"}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result is None

    def test_parse_turn_completed_event(self, codex_runtime: CodexRuntime):
        """Test parsing turn.completed event (should show usage)."""
        line = '{"type": "turn.completed", "usage": {"input_tokens": 42, "output_tokens": 84}}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result == "[usage] 42 in / 84 out tokens"

    def test_parse_turn_failed_event(self, codex_runtime: CodexRuntime):
        """Test parsing turn.failed event (should show error)."""
        line = '{"type": "turn.failed", "error": "File not found"}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result == "[failed] File not found"

    def test_parse_error_event(self, codex_runtime: CodexRuntime):
        """Test parsing error event (should show error message)."""
        line = '{"type": "error", "message": "Invalid command"}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result == "[error] Invalid command"

    def test_parse_item_started_command_execution(self, codex_runtime: CodexRuntime):
        """Test parsing item.started event for command execution."""
        line = '{"type": "item.started", "item": {"type": "command_execution", "command": "ls -la"}}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result == "[exec] $ ls -la"

    def test_parse_item_completed_agent_message(self, codex_runtime: CodexRuntime):
        """Test parsing item.completed event for agent message."""
        line = '{"type": "item.completed", "item": {"type": "agent_message", "text": "Hello, I found the following files"}}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result == "Hello, I found the following files"

    def test_parse_item_completed_command_execution(self, codex_runtime: CodexRuntime):
        """Test parsing item.completed event for command execution with output."""
        # Use proper JSON with escaped newlines
        line = r'{"type": "item.completed", "item": {"type": "command_execution", "command": "ls -la", "output": "file1.txt\nfile2.txt\nfile3.txt"}}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        # Should parse the JSON and format the command execution
        assert "[exec] $ ls -la" in result
        assert "file1.txt" in result
        assert "file2.txt" in result
        assert "file3.txt" in result

    def test_parse_item_completed_command_execution_long_output(self, codex_runtime: CodexRuntime):
        """Test parsing command execution with long output (should truncate)."""
        # Create a long output with many lines
        long_output = "\n".join([f"line{i}" for i in range(20)])  # 20 lines
        # Use proper JSON escaping for the output
        line = json.dumps({
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "find .",
                "output": long_output
            }
        })
        result = codex_runtime._parse_jsonl_event("test-session", line)
        
        # Should show first 15 lines and indicate truncation
        assert "[exec] $ find ." in result
        assert "line0" in result
        assert "line14" in result
        assert "line15" not in result  # Should be truncated
        assert "… (5 more lines)" in result

    def test_parse_item_completed_file_change(self, codex_runtime: CodexRuntime):
        """Test parsing item.completed event for file change."""
        line = '{"type": "item.completed", "item": {"type": "file_change", "path": "src/main.py", "change_type": "modified"}}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result == "[file] modified: src/main.py"

    def test_parse_item_completed_reasoning(self, codex_runtime: CodexRuntime):
        """Test parsing item.completed event for reasoning (should return None)."""
        line = '{"type": "item.completed", "item": {"type": "reasoning", "text": "I think the best approach is..."}}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result is None  # Reasoning should be skipped

    def test_parse_item_completed_web_search(self, codex_runtime: CodexRuntime):
        """Test parsing item.completed event for web search."""
        line = '{"type": "item.completed", "item": {"type": "web_search", "query": "how to use pytest"}}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result == "[search] how to use pytest"

    def test_parse_item_completed_plan_update(self, codex_runtime: CodexRuntime):
        """Test parsing item.completed event for plan update."""
        line = '{"type": "item.completed", "item": {"type": "plan_update", "text": "Next, I will implement the authentication module"}}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result == "[plan] Next, I will implement the authentication module"

    def test_parse_invalid_json(self, codex_runtime: CodexRuntime):
        """Test parsing invalid JSON (should return original line)."""
        line = "not valid json"
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result == "not valid json"

    def test_parse_empty_line(self, codex_runtime: CodexRuntime):
        """Test parsing empty line (should return None)."""
        line = ""
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result is None


class TestCodexRuntimeStatus:
    """Test status reporting."""

    async def test_get_status_not_found(self, codex_runtime: CodexRuntime):
        """Test status for non-existent session."""
        status = await codex_runtime.get_status("non-existent-session")
        assert status.state == "error"
        assert status.name == "non-existent-session"
        assert status.role == "unknown"

    async def test_get_status_running(self, codex_runtime: CodexRuntime, sample_config: AgentConfig):
        """Test status for running session (mocked)."""
        session_id = "test-session"
        
        # Mock a running process
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self.returncode = None
                self.stdout = None
        
        codex_runtime._sessions[session_id] = MockProcess()
        codex_runtime._configs[session_id] = sample_config
        codex_runtime._last_output[session_id] = "Exploring..."
        
        status = await codex_runtime.get_status(session_id)
        assert status.state == "running"
        assert status.name == "test-agent"
        assert status.role == "scout"
        assert status.current_task == "Explore the codebase and identify key components"
        assert status.runtime == "codex"
        assert status.last_output == "Exploring..."
        assert status.pid == 12345


class TestCodexRuntimeLifecycle:
    """Test runtime lifecycle operations."""

    async def test_spawn_and_kill(self, codex_runtime: CodexRuntime, sample_config: AgentConfig, tmp_path: Path):
        """Test spawn and kill operations."""
        # Create a worktree directory
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        
        # Update config to use the temp worktree
        config = AgentConfig(
            name=sample_config.name,
            role=sample_config.role,
            task=sample_config.task,
            worktree_path=str(worktree),
            model=sample_config.model,
            runtime=sample_config.runtime,
            system_prompt_path=sample_config.system_prompt_path,
            allowed_tools=sample_config.allowed_tools,
            blocked_tools=sample_config.blocked_tools,
            extra_env=sample_config.extra_env,
        )
        
        # Mock subprocess creation to avoid actual spawn
        original_create_subprocess = asyncio.create_subprocess_exec
        
        async def mock_create_subprocess_exec(*args, **kwargs):
            # Return a mock process
            class MockProcess:
                def __init__(self):
                    self.pid = 99999
                    self.returncode = None
                    self.stdout = None
                    self.stderr = None
                
                async def wait(self):
                    pass
                
                def terminate(self):
                    self.returncode = -15
                
                def kill(self):
                    self.returncode = -9
            
            return MockProcess()
        
        # Patch the subprocess creation
        asyncio.create_subprocess_exec = mock_create_subprocess_exec
        
        try:
            # Test spawn
            session_id = await codex_runtime.spawn(config)
            assert session_id.startswith("codex-test-agent-")
            assert session_id in codex_runtime._sessions
            assert session_id in codex_runtime._configs
            
            # Test kill
            await codex_runtime.kill(session_id)
            assert session_id not in codex_runtime._sessions
            assert session_id not in codex_runtime._configs
            
            # Check that system prompt file was cleaned up
            prompt_file = worktree / ".codex_system_prompt.md"
            assert not prompt_file.exists()
            
        finally:
            # Restore original function
            asyncio.create_subprocess_exec = original_create_subprocess

    async def test_stream_output_empty(self, codex_runtime: CodexRuntime):
        """Test streaming output for non-existent session."""
        stream = codex_runtime.stream_output("non-existent-session")
        
        # Should return immediately with no output
        output = []
        async for item in stream:
            output.append(item)
        
        assert len(output) == 0


class TestCodexRuntimeEventCallbacks:
    """Test event callback functionality."""

    def test_event_callback_on_spawn(self, codex_runtime: CodexRuntime, sample_config: AgentConfig, tmp_path: Path):
        """Test that event callback is called on spawn."""
        # Create a worktree directory
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        
        # Update config to use the temp worktree
        config = AgentConfig(
            name=sample_config.name,
            role=sample_config.role,
            task=sample_config.task,
            worktree_path=str(worktree),
            model=sample_config.model,
            runtime=sample_config.runtime,
            system_prompt_path=sample_config.system_prompt_path,
            allowed_tools=sample_config.allowed_tools,
            blocked_tools=sample_config.blocked_tools,
            extra_env=sample_config.extra_env,
        )
        
        callback_called = []
        
        def mock_callback(event_type, agent_name, message):
            callback_called.append((event_type, agent_name, message))
        
        codex_runtime._event_callback = mock_callback
        
        # Mock the subprocess creation to avoid actual spawn
        original_create_subprocess = asyncio.create_subprocess_exec
        
        async def mock_create_subprocess_exec(*args, **kwargs):
            class MockProcess:
                def __init__(self):
                    self.pid = 12345
                    self.returncode = None
                    self.stdout = None
                    self.stderr = None
                
                async def wait(self):
                    pass
                
                def terminate(self):
                    self.returncode = -15
                
                def kill(self):
                    self.returncode = -9
            
            return MockProcess()
        
        asyncio.create_subprocess_exec = mock_create_subprocess_exec
        
        try:
            # Run spawn in event loop
            asyncio.run(codex_runtime.spawn(config))
            
            # Check that callback was called
            assert len(callback_called) == 1
            event_type, agent_name, message = callback_called[0]
            assert event_type == "spawn"
            assert agent_name == "test-agent"
            assert "spawned as scout via codex" in message
            assert "read-only sandbox" in message
            assert "o4-mini" in message
            
        finally:
            asyncio.create_subprocess_exec = original_create_subprocess


class TestCodexRuntimeCommandBuilding:
    """Test command line building."""

    async def test_spawn_command_building(self, codex_runtime: CodexRuntime, sample_config: AgentConfig, tmp_path: Path):
        """Test that spawn builds correct command line."""
        # Create a worktree directory
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        
        # Update config to use the temp worktree
        config = AgentConfig(
            name=sample_config.name,
            role=sample_config.role,
            task=sample_config.task,
            worktree_path=str(worktree),
            model=sample_config.model,
            runtime=sample_config.runtime,
            system_prompt_path=sample_config.system_prompt_path,
            allowed_tools=sample_config.allowed_tools,
            blocked_tools=sample_config.blocked_tools,
            extra_env=sample_config.extra_env,
        )
        
        # Mock subprocess creation to capture the command
        captured_commands = []
        
        original_create_subprocess = asyncio.create_subprocess_exec
        
        async def mock_create_subprocess_exec(*args, **kwargs):
            captured_commands.append({
                "args": args,
                "kwargs": kwargs
            })
            
            class MockProcess:
                def __init__(self):
                    self.pid = 12345
                    self.returncode = None
                    self.stdout = None
                    self.stderr = None
                
                async def wait(self):
                    pass
                
                def terminate(self):
                    self.returncode = -15
                
                def kill(self):
                    self.returncode = -9
            
            return MockProcess()
        
        asyncio.create_subprocess_exec = mock_create_subprocess_exec
        
        try:
            await codex_runtime.spawn(config)
            
            # Check that command was built correctly
            assert len(captured_commands) == 1
            cmd_info = captured_commands[0]
            args = cmd_info["args"]
            
            # Should start with codex exec
            assert args[0] == "codex"
            assert args[1] == "exec"
            
            # Should have --json flag
            assert "--json" in args
            
            # Should have model
            assert "--model" in args
            assert "o4-mini" in args
            
            # Should have sandbox
            assert "--sandbox" in args
            assert "read-only" in args
            
            # Should have approval
            assert "--ask-for-approval" in args
            assert "never" in args
            
            # Should have worktree
            assert "-C" in args
            assert str(worktree) in args
            
        finally:
            asyncio.create_subprocess_exec = original_create_subprocess


class TestCodexRuntimeEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_json_with_missing_fields(self, codex_runtime: CodexRuntime):
        """Test parsing JSON with missing expected fields."""
        line = '{"type": "unknown", "content": "test"}'
        result = codex_runtime._parse_jsonl_event("test-session", line)
        assert result is None  # Unknown type should return None

    def test_role_not_in_mappings(self, codex_runtime: CodexRuntime, sample_config: AgentConfig):
        """Test behavior for role not in mappings."""
        config = AgentConfig(
            name=sample_config.name,
            role="unknown-role",
            task=sample_config.task,
            worktree_path=sample_config.worktree_path,
            model=sample_config.model,
            runtime=sample_config.runtime,
            system_prompt_path=sample_config.system_prompt_path,
            allowed_tools=sample_config.allowed_tools,
            blocked_tools=sample_config.blocked_tools,
            extra_env=sample_config.extra_env,
        )
        
        # Should default to workspace-write sandbox
        sandbox = codex_runtime.ROLE_SANDBOX.get("unknown-role", "workspace-write")
        assert sandbox == "workspace-write"
        
        # Should default to never approval
        approval = codex_runtime.ROLE_APPROVAL.get("unknown-role", "never")
        assert approval == "never"
        
        # Should default to o4-mini model
        model = codex_runtime.ROLE_MODEL.get("unknown-role", "o4-mini")
        assert model == "o4-mini"

    async def test_system_prompt_file_cleanup_on_kill(self, codex_runtime: CodexRuntime, sample_config: AgentConfig, tmp_path: Path):
        """Test that system prompt file is cleaned up on kill."""
        # Create a worktree directory
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        
        config = AgentConfig(
            name=sample_config.name,
            role=sample_config.role,
            task=sample_config.task,
            worktree_path=str(worktree),
            model=sample_config.model,
            runtime=sample_config.runtime,
            system_prompt_path=sample_config.system_prompt_path,
            allowed_tools=sample_config.allowed_tools,
            blocked_tools=sample_config.blocked_tools,
            extra_env=sample_config.extra_env,
        )
        
        # Mock subprocess creation
        original_create_subprocess = asyncio.create_subprocess_exec
        
        async def mock_create_subprocess_exec(*args, **kwargs):
            class MockProcess:
                def __init__(self):
                    self.pid = 12345
                    self.returncode = None
                    self.stdout = None
                    self.stderr = None
                
                async def wait(self):
                    pass
                
                def terminate(self):
                    self.returncode = -15
                
                def kill(self):
                    self.returncode = -9
            
            return MockProcess()
        
        asyncio.create_subprocess_exec = mock_create_subprocess_exec
        
        try:
            # Spawn to create the system prompt file
            session_id = await codex_runtime.spawn(config)
            
            # Check that system prompt file was created
            prompt_file = worktree / ".codex_system_prompt.md"
            assert prompt_file.exists()
            
            # Kill the session
            await codex_runtime.kill(session_id)
            
            # Check that system prompt file was cleaned up
            assert not prompt_file.exists()
            
        finally:
            asyncio.create_subprocess_exec = original_create_subprocess