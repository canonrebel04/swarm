"""Tests for VibeRuntime adapter."""
import asyncio
import json
from pathlib import Path
from typing import AsyncIterator

import pytest

from src.runtimes.vibe import VibeRuntime
from src.runtimes.base import AgentConfig, AgentStatus


@pytest.fixture
def vibe_runtime() -> VibeRuntime:
    """Create a fresh VibeRuntime instance for each test."""
    return VibeRuntime()


@pytest.fixture
def sample_config() -> AgentConfig:
    """Create a sample agent configuration."""
    return AgentConfig(
        name="test-agent",
        role="scout",
        task="Explore the codebase and identify key components",
        worktree_path="/tmp/test-worktree",
        model="gpt-4",
        runtime="vibe",
        system_prompt_path="",
        allowed_tools=None,
        blocked_tools=None,
        extra_env={},
    )


class TestVibeRuntimeProperties:
    """Test basic runtime properties."""

    def test_runtime_name(self, vibe_runtime: VibeRuntime):
        """Test runtime name property."""
        assert vibe_runtime.runtime_name == "vibe"

    def test_capabilities(self, vibe_runtime: VibeRuntime):
        """Test runtime capabilities."""
        caps = vibe_runtime.capabilities
        assert caps.interactive_chat is True
        assert caps.headless_run is True
        assert caps.resume_session is True
        assert caps.streaming_output is True
        assert caps.tool_allowlist is True
        assert caps.sandbox_support is False
        assert caps.agent_profiles is True
        assert caps.parallel_safe is True


class TestVibeRuntimeRoleMappings:
    """Test role to agent profile mappings."""

    def test_role_agent_map(self, vibe_runtime: VibeRuntime):
        """Test role to agent profile mapping."""
        assert vibe_runtime.ROLE_AGENT_MAP["scout"] == "plan"
        assert vibe_runtime.ROLE_AGENT_MAP["developer"] == "auto-approve"
        assert vibe_runtime.ROLE_AGENT_MAP["builder"] == "accept-edits"
        assert vibe_runtime.ROLE_AGENT_MAP["reviewer"] == "default"
        assert vibe_runtime.ROLE_AGENT_MAP["merger"] == "auto-approve"

    def test_role_tool_policy(self, vibe_runtime: VibeRuntime):
        """Test role tool policy mappings."""
        # Scout should have read-only tools
        scout_tools = vibe_runtime.ROLE_TOOL_POLICY["scout"]
        assert "read_file" in scout_tools
        assert "list_directory" in scout_tools
        assert "search_files" in scout_tools
        assert "bash" not in scout_tools

        # Developer should have unrestricted tools (empty list)
        dev_tools = vibe_runtime.ROLE_TOOL_POLICY["developer"]
        assert dev_tools == []

        # Builder should have file tools + bash
        builder_tools = vibe_runtime.ROLE_TOOL_POLICY["builder"]
        assert "bash" in builder_tools
        assert "write_file" in builder_tools
        assert "edit_file" in builder_tools

    def test_role_max_price(self, vibe_runtime: VibeRuntime):
        """Test role max price mappings."""
        assert vibe_runtime.ROLE_MAX_PRICE["scout"] == 0.15
        assert vibe_runtime.ROLE_MAX_PRICE["developer"] == 1.00
        assert vibe_runtime.ROLE_MAX_PRICE["builder"] == 0.75

    def test_role_max_turns(self, vibe_runtime: VibeRuntime):
        """Test role max turns mappings."""
        assert vibe_runtime.ROLE_MAX_TURNS["scout"] == 20
        assert vibe_runtime.ROLE_MAX_TURNS["developer"] == 80
        assert vibe_runtime.ROLE_MAX_TURNS["builder"] == 60


class TestVibeRuntimePromptBuilding:
    """Test prompt building functionality."""

    def test_build_full_prompt_without_system_prompt(self, vibe_runtime: VibeRuntime, sample_config: AgentConfig):
        """Test prompt building without system prompt file."""
        prompt = vibe_runtime._build_full_prompt(sample_config)
        
        # Should contain role contract and task
        assert "ROLE CONTRACT (non-negotiable)" in prompt
        assert "You are test-agent, a scout agent in a multi-agent swarm" in prompt
        assert "Explore the codebase and identify key components" in prompt
        assert '"role":"scout","status":"done"' in prompt

    def test_build_full_prompt_with_system_prompt(self, vibe_runtime: VibeRuntime, sample_config: AgentConfig, tmp_path: Path):
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
        
        prompt = vibe_runtime._build_full_prompt(config_with_prompt)
        
        # Should contain system prompt content
        assert "This is a system prompt" in prompt
        assert "with multiple lines" in prompt

    def test_role_behavioral_constraints(self, vibe_runtime: VibeRuntime):
        """Test role-specific behavioral constraints."""
        # Scout constraints
        scout_constraints = vibe_runtime._role_behavioral_constraints("scout")
        assert "MUST NOT edit, write, or delete any files" in scout_constraints
        assert "MUST NOT run bash commands that modify state" in scout_constraints
        
        # Reviewer constraints
        reviewer_constraints = vibe_runtime._role_behavioral_constraints("reviewer")
        assert "MUST NOT edit, write, or delete any files" in reviewer_constraints
        assert "MUST NOT run any bash commands" in reviewer_constraints
        
        # Developer should have no specific constraints (empty string)
        dev_constraints = vibe_runtime._role_behavioral_constraints("developer")
        assert dev_constraints == ""


class TestVibeRuntimeToolFlags:
    """Test tool flag building functionality."""

    def test_build_tool_flags_empty_for_developer(self, vibe_runtime: VibeRuntime, sample_config: AgentConfig):
        """Test that developer role has no tool flags (unrestricted)."""
        dev_config = AgentConfig(
            name=sample_config.name,
            role="developer",
            task=sample_config.task,
            worktree_path=sample_config.worktree_path,
            model=sample_config.model,
            runtime=sample_config.runtime,
            system_prompt_path=sample_config.system_prompt_path,
            allowed_tools=sample_config.allowed_tools,
            blocked_tools=sample_config.blocked_tools,
            extra_env=sample_config.extra_env,
        )
        flags = vibe_runtime._build_tool_flags(dev_config)
        assert flags == []

    def test_build_tool_flags_for_scout(self, vibe_runtime: VibeRuntime, sample_config: AgentConfig):
        """Test tool flags for scout role."""
        scout_config = AgentConfig(
            name=sample_config.name,
            role="scout",
            task=sample_config.task,
            worktree_path=sample_config.worktree_path,
            model=sample_config.model,
            runtime=sample_config.runtime,
            system_prompt_path=sample_config.system_prompt_path,
            allowed_tools=sample_config.allowed_tools,
            blocked_tools=sample_config.blocked_tools,
            extra_env=sample_config.extra_env,
        )
        flags = vibe_runtime._build_tool_flags(scout_config)
        
        # Should have read-only tools
        assert "--enabled-tools" in flags
        assert "read_file" in flags
        assert "list_directory" in flags
        assert "search_files" in flags
        # Should NOT have bash
        assert "bash" not in flags

    def test_build_tool_flags_with_allowed_tools_override(self, vibe_runtime: VibeRuntime, sample_config: AgentConfig):
        """Test that allowed_tools config overrides role defaults."""
        config_with_override = AgentConfig(
            name=sample_config.name,
            role="scout",
            task=sample_config.task,
            worktree_path=sample_config.worktree_path,
            model=sample_config.model,
            runtime=sample_config.runtime,
            system_prompt_path=sample_config.system_prompt_path,
            allowed_tools=["read_file", "bash"],  # Override scout's default
            blocked_tools=sample_config.blocked_tools,
            extra_env=sample_config.extra_env,
        )
        flags = vibe_runtime._build_tool_flags(config_with_override)
        
        # Should respect the override
        assert "--enabled-tools" in flags
        assert "read_file" in flags
        assert "bash" in flags  # This overrides the scout default


class TestVibeRuntimeStreamingParsing:
    """Test streaming output parsing."""

    def test_parse_assistant_text_message(self, vibe_runtime: VibeRuntime):
        """Test parsing assistant text messages."""
        line = '{"role": "assistant", "content": "Hello, I am exploring the codebase"}'
        result = vibe_runtime._parse_streaming_line("test-session", line)
        assert result == "Hello, I am exploring the codebase"

    def test_parse_tool_call_message(self, vibe_runtime: VibeRuntime):
        """Test parsing tool call messages."""
        line = '''{
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "bash", "arguments": "{\\"command\\":\\\"ls -la\\\"}"}},
                {"function": {"name": "read_file", "arguments": "{\\"path\\":\\\"README.md\\\"}"}}
            ]
        }'''
        result = vibe_runtime._parse_streaming_line("test-session", line)
        # The arguments field contains escaped JSON, so we need to parse it
        assert "[bash] $ ls -la" in result
        assert "[read] README.md" in result

    def test_parse_tool_result_message(self, vibe_runtime: VibeRuntime):
        """Test parsing tool result messages."""
        # Use proper escaping for newlines in JSON
        line = r'{"role": "tool", "content": "command: ls -la\nstdout: file1.txt\nfile2.txt\nstderr: \nreturncode: 0"}'
        result = vibe_runtime._parse_streaming_line("test-session", line)
        # Should extract stdout from the tool result
        assert "[result] file1.txt" in result
        assert "file2.txt" in result

    def test_parse_cost_message(self, vibe_runtime: VibeRuntime):
        """Test parsing cost messages."""
        line = '{"total_cost": 0.1234}'
        result = vibe_runtime._parse_streaming_line("test-session", line)
        assert result == "[cost] $0.1234"

    def test_parse_error_message(self, vibe_runtime: VibeRuntime):
        """Test parsing error messages."""
        line = '{"type": "error", "message": "File not found"}'
        result = vibe_runtime._parse_streaming_line("test-session", line)
        assert result == "[error] File not found"

    def test_parse_session_id_capture(self, vibe_runtime: VibeRuntime):
        """Test that session ID is captured from streaming output."""
        line = '{"session_id": "abc123", "role": "assistant", "content": "test"}'
        result = vibe_runtime._parse_streaming_line("test-session", line)
        
        # Should capture session ID
        assert vibe_runtime._session_ids["test-session"] == "abc123"
        assert result == "test"

    def test_parse_plain_text_line(self, vibe_runtime: VibeRuntime):
        """Test parsing plain text lines."""
        line = "This is a plain text line"
        result = vibe_runtime._parse_streaming_line("test-session", line)
        assert result == "This is a plain text line"

    def test_parse_empty_line(self, vibe_runtime: VibeRuntime):
        """Test parsing empty lines."""
        line = ""
        result = vibe_runtime._parse_streaming_line("test-session", line)
        assert result is None


class TestVibeRuntimeStatus:
    """Test status reporting."""

    async def test_get_status_not_found(self, vibe_runtime: VibeRuntime):
        """Test status for non-existent session."""
        status = await vibe_runtime.get_status("non-existent-session")
        assert status.state == "error"
        assert status.name == "non-existent-session"
        assert status.role == "unknown"

    async def test_get_status_running(self, vibe_runtime: VibeRuntime, sample_config: AgentConfig):
        """Test status for running session (mocked)."""
        # This is a simplified test - in reality spawn would start a process
        # For testing purposes, we'll manually set up the state
        session_id = "test-session"
        
        # Mock a running process
        class MockProcess:
            def __init__(self):
                self.pid = 12345
                self.returncode = None
                self.stdout = None
        
        vibe_runtime._sessions[session_id] = MockProcess()
        vibe_runtime._configs[session_id] = sample_config
        vibe_runtime._last_output[session_id] = "Exploring..."
        
        status = await vibe_runtime.get_status(session_id)
        assert status.state == "running"
        assert status.name == "test-agent"
        assert status.role == "scout"
        assert status.current_task == "Explore the codebase and identify key components"
        assert status.runtime == "vibe"
        assert status.last_output == "Exploring..."
        assert status.pid == 12345


class TestVibeRuntimeLifecycle:
    """Test runtime lifecycle operations."""

    async def test_spawn_and_kill(self, vibe_runtime: VibeRuntime, sample_config: AgentConfig):
        """Test spawn and kill operations."""
        # Note: This is a basic test that verifies the method structure
        # In a real environment, this would actually spawn a vibe process
        # For testing, we'll mock the subprocess creation
        
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
                    self.returncode = -15  # SIGTERM
                
                def kill(self):
                    self.returncode = -9  # SIGKILL
            
            return MockProcess()
        
        # Patch the subprocess creation
        asyncio.create_subprocess_exec = mock_create_subprocess_exec
        
        try:
            # Test spawn
            session_id = await vibe_runtime.spawn(sample_config)
            assert session_id.startswith("vibe-test-agent-")
            assert session_id in vibe_runtime._sessions
            assert session_id in vibe_runtime._configs
            
            # Test kill
            await vibe_runtime.kill(session_id)
            assert session_id not in vibe_runtime._sessions
            assert session_id not in vibe_runtime._configs
            
        finally:
            # Restore original function
            asyncio.create_subprocess_exec = original_create_subprocess

    async def test_stream_output_empty(self, vibe_runtime: VibeRuntime):
        """Test streaming output for non-existent session."""
        stream = vibe_runtime.stream_output("non-existent-session")
        
        # Should return immediately with no output
        output = []
        async for item in stream:
            output.append(item)
        
        assert len(output) == 0


class TestVibeRuntimeEventCallbacks:
    """Test event callback functionality."""

    def test_event_callback_on_spawn(self, vibe_runtime: VibeRuntime, sample_config: AgentConfig):
        """Test that event callback is called on spawn."""
        callback_called = []
        
        def mock_callback(event_type, agent_name, message):
            callback_called.append((event_type, agent_name, message))
        
        vibe_runtime._event_callback = mock_callback
        
        # Mock the subprocess creation to avoid actual spawn
        original_create_subprocess = asyncio.create_subprocess_exec
        
        async def mock_create_subprocess_exec(*args, **kwargs):
            class MockProcess:
                def __init__(self):
                    self.pid = 12345
                    self.returncode = None
                    self.stdout = None
                    self.stderr = None
            
            return MockProcess()
        
        asyncio.create_subprocess_exec = mock_create_subprocess_exec
        
        try:
            # Run spawn in event loop
            asyncio.run(vibe_runtime.spawn(sample_config))
            
            # Check that callback was called
            assert len(callback_called) == 1
            event_type, agent_name, message = callback_called[0]
            assert event_type == "spawn"
            assert agent_name == "test-agent"
            assert "spawned as scout via vibe" in message
            
        finally:
            asyncio.create_subprocess_exec = original_create_subprocess


class TestVibeRuntimeCommandBuilding:
    """Test command line building."""

    async def test_spawn_command_building(self, vibe_runtime: VibeRuntime, sample_config: AgentConfig):
        """Test that spawn builds correct command line."""
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
            
            return MockProcess()
        
        asyncio.create_subprocess_exec = mock_create_subprocess_exec
        
        try:
            await vibe_runtime.spawn(sample_config)
            
            # Check that command was built correctly
            assert len(captured_commands) == 1
            cmd_info = captured_commands[0]
            args = cmd_info["args"]
            
            # Should start with vibe command
            assert args[0] == "vibe"
            
            # Should have -p flag with prompt
            assert "-p" in args
            
            # Should have output streaming
            assert "--output" in args
            assert "streaming" in args
            
            # Should have agent profile
            assert "--agent" in args
            assert "plan" in args  # scout maps to plan
            
            # Should have max-turns and max-price
            assert "--max-turns" in args
            assert "--max-price" in args
            
            # Should have workdir
            assert "--workdir" in args
            assert "/tmp/test-worktree" in args
            
        finally:
            asyncio.create_subprocess_exec = original_create_subprocess


class TestVibeRuntimeEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_invalid_json(self, vibe_runtime: VibeRuntime):
        """Test parsing invalid JSON lines."""
        line = "not valid json"
        result = vibe_runtime._parse_streaming_line("test-session", line)
        assert result == "not valid json"

    def test_parse_json_with_missing_fields(self, vibe_runtime: VibeRuntime):
        """Test parsing JSON with missing expected fields."""
        line = '{"role": "unknown", "content": "test"}'
        result = vibe_runtime._parse_streaming_line("test-session", line)
        assert result is None  # Unknown role should return None

    def test_build_tool_flags_with_empty_list(self, vibe_runtime: VibeRuntime, sample_config: AgentConfig):
        """Test tool flags with empty allowed_tools list."""
        # When allowed_tools is an empty list [], it's falsy so it falls back to role policy
        config = AgentConfig(
            name=sample_config.name,
            role=sample_config.role,
            task=sample_config.task,
            worktree_path=sample_config.worktree_path,
            model=sample_config.model,
            runtime=sample_config.runtime,
            system_prompt_path=sample_config.system_prompt_path,
            allowed_tools=[],  # Empty list is falsy, falls back to role policy
            blocked_tools=sample_config.blocked_tools,
            extra_env=sample_config.extra_env,
        )
        flags = vibe_runtime._build_tool_flags(config)
        # Should fall back to role policy (scout tools)
        expected_tools = vibe_runtime.ROLE_TOOL_POLICY.get("scout", [])
        expected_flags = []
        for tool in expected_tools:
            expected_flags += ["--enabled-tools", tool]
        assert flags == expected_flags

    def test_role_not_in_mappings(self, vibe_runtime: VibeRuntime, sample_config: AgentConfig):
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
        
        # Should default to "default" agent
        agent_name = vibe_runtime.ROLE_AGENT_MAP.get("unknown-role", "default")
        assert agent_name == "default"
        
        # Should default to 0.50 max price
        max_price = vibe_runtime.ROLE_MAX_PRICE.get("unknown-role", 0.50)
        assert max_price == 0.50
        
        # Should default to 40 max turns
        max_turns = vibe_runtime.ROLE_MAX_TURNS.get("unknown-role", 40)
        assert max_turns == 40
