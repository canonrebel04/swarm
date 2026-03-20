"""
Test suite for Gemini runtime adapter.
"""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.runtimes.gemini import GeminiRuntime
from src.runtimes.base import AgentConfig, AgentStatus


@pytest.fixture
def gemini_runtime():
    return GeminiRuntime()


@pytest.fixture
def mock_config():
    return AgentConfig(
        name="test-agent",
        role="developer",
        task="Implement feature X",
        worktree_path="/tmp/worktree",
        model="gemini-2.5-pro",
        runtime="gemini",
        system_prompt_path="/tmp/prompt.md",
        extra_env={"TEST": "1"},
    )


def test_runtime_name(gemini_runtime):
    assert gemini_runtime.runtime_name == "gemini"


def test_capabilities(gemini_runtime):
    caps = gemini_runtime.capabilities
    assert caps.interactive_chat is True
    assert caps.headless_run is True
    assert caps.resume_session is True
    assert caps.streaming_output is True
    assert caps.tool_allowlist is True
    assert caps.sandbox_support is False
    assert caps.agent_profiles is False
    assert caps.parallel_safe is True


def test_role_approval_modes(gemini_runtime):
    assert gemini_runtime.ROLE_APPROVAL["scout"] == "plan"
    assert gemini_runtime.ROLE_APPROVAL["reviewer"] == "plan"
    assert gemini_runtime.ROLE_APPROVAL["builder"] == "auto_edit"
    assert gemini_runtime.ROLE_APPROVAL["developer"] == "yolo"
    assert gemini_runtime.ROLE_APPROVAL["merger"] == "yolo"


def test_role_models(gemini_runtime):
    assert gemini_runtime.ROLE_MODEL["scout"] == "gemini-2.5-flash"
    assert gemini_runtime.ROLE_MODEL["reviewer"] == "gemini-2.5-pro"
    assert gemini_runtime.ROLE_MODEL["developer"] == "gemini-2.5-pro"


def test_known_tools(gemini_runtime):
    expected_tools = {
        "read_file", "write_file", "edit_file",
        "list_directory", "glob", "grep",
        "run_shell_command",
        "web_search", "web_fetch",
        "read_many_files", "find_files",
    }
    assert gemini_runtime.KNOWN_TOOLS == expected_tools


@pytest.mark.asyncio
async def test_spawn_success(gemini_runtime, mock_config):
    # Mock system prompt file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("Test prompt")
        mock_config.system_prompt_path = f.name

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await gemini_runtime.spawn(mock_config)

    assert session_id == "gemini-test-agent-12345"
    assert len(gemini_runtime._sessions) == 1
    assert len(gemini_runtime._configs) == 1

    # Clean up
    Path(mock_config.system_prompt_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_spawn_with_policy_file(gemini_runtime, mock_config):
    # Test builder role which should generate policy file
    builder_config = AgentConfig(
        name="builder-agent",
        role="builder",
        task="Build project",
        worktree_path="/tmp/worktree",
        model="gemini-2.5-flash",
        runtime="gemini",
        system_prompt_path="/tmp/prompt.md",
    )

    mock_proc = MagicMock()
    mock_proc.pid = 54321
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await gemini_runtime.spawn(builder_config)

    assert session_id == "gemini-builder-agent-54321"
    # Builder role should have policy file
    assert f"gemini-{builder_config.name}" in gemini_runtime._policy_files


@pytest.mark.asyncio
async def test_spawn_event_callback(gemini_runtime, mock_config):
    callback_called = []
    
    def mock_callback(event_type, agent_name, message):
        callback_called.append((event_type, agent_name, message))
    
    gemini_runtime._event_callback = mock_callback
    
    mock_proc = MagicMock()
    mock_proc.pid = 11111
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        await gemini_runtime.spawn(mock_config)

    assert len(callback_called) == 1
    assert callback_called[0][0] == "spawn"
    assert callback_called[0][1] == "test-agent"
    assert "spawned as developer via gemini" in callback_called[0][2]


@pytest.mark.asyncio
async def test_send_message(gemini_runtime, mock_config):
    # First spawn an agent
    mock_proc = MagicMock()
    mock_proc.pid = 22222
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await gemini_runtime.spawn(mock_config)

    # Now send a message
    mock_proc2 = MagicMock()
    mock_proc2.pid = 33333
    mock_proc2.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc2):
        await gemini_runtime.send_message(session_id, "Follow up message")

    # Should have replaced the process
    assert gemini_runtime._sessions[session_id] == mock_proc2


@pytest.mark.asyncio
async def test_stream_output(gemini_runtime, mock_config):
    # Create a mock process with stdout
    mock_stdout = AsyncMock()
    mock_stdout.__aiter__.return_value = [
        b'{"type":"message","role":"assistant","content":"Hello"}\n',
        b'{"type":"message","role":"assistant","content":"World"}\n',
    ]

    mock_proc = MagicMock()
    mock_proc.pid = 44444
    mock_proc.returncode = None
    mock_proc.stdout = mock_stdout

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await gemini_runtime.spawn(mock_config)

    # Stream the output
    outputs = []
    async for text in gemini_runtime.stream_output(session_id):
        outputs.append(text)

    assert len(outputs) == 2
    assert outputs[0] == "Hello"
    assert outputs[1] == "World"


@pytest.mark.asyncio
async def test_stream_output_tool_events(gemini_runtime, mock_config):
    # Create a mock process with tool events
    mock_stdout = AsyncMock()
    mock_stdout.__aiter__.return_value = [
        b'{"type":"tool_use","tool":"run_shell_command","args":{"command":"ls -la"}}\n',
        b'{"type":"tool_result","tool":"run_shell_command","result":{"output":"file1 file2"}}\n',
    ]

    mock_proc = MagicMock()
    mock_proc.pid = 55555
    mock_proc.returncode = None
    mock_proc.stdout = mock_stdout

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await gemini_runtime.spawn(mock_config)

    # Stream the output
    outputs = []
    async for text in gemini_runtime.stream_output(session_id):
        outputs.append(text)

    assert len(outputs) == 2
    assert outputs[0] == "[shell] $ ls -la"
    assert outputs[1] == "[result] file1 file2"


@pytest.mark.asyncio
async def test_get_status_running(gemini_runtime, mock_config):
    mock_proc = MagicMock()
    mock_proc.pid = 66666
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await gemini_runtime.spawn(mock_config)

    status = await gemini_runtime.get_status(session_id)
    assert status.name == "test-agent"
    assert status.role == "developer"
    assert status.state == "running"
    assert status.runtime == "gemini"
    assert status.pid == 66666


@pytest.mark.asyncio
async def test_get_status_done(gemini_runtime, mock_config):
    mock_proc = MagicMock()
    mock_proc.pid = 77777
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await gemini_runtime.spawn(mock_config)

    status = await gemini_runtime.get_status(session_id)
    assert status.state == "done"


@pytest.mark.asyncio
async def test_get_status_error(gemini_runtime, mock_config):
    mock_proc = MagicMock()
    mock_proc.pid = 88888
    mock_proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await gemini_runtime.spawn(mock_config)

    status = await gemini_runtime.get_status(session_id)
    assert status.state == "error"


@pytest.mark.asyncio
async def test_kill_process(gemini_runtime, mock_config):
    mock_proc = MagicMock()
    mock_proc.pid = 99999
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await gemini_runtime.spawn(mock_config)

    # Kill the process
    await gemini_runtime.kill(session_id)

    # Should be removed from tracking
    assert session_id not in gemini_runtime._sessions
    assert session_id not in gemini_runtime._configs
    assert session_id not in gemini_runtime._session_ids
    assert session_id not in gemini_runtime._last_output

    # Process should have been terminated
    mock_proc.terminate.assert_called_once()


@pytest.mark.asyncio
async def test_kill_with_policy_file(gemini_runtime):
    # Test with builder role that creates policy file
    builder_config = AgentConfig(
        name="builder-test",
        role="builder",
        task="Build",
        worktree_path="/tmp/worktree",
        model="gemini-2.5-flash",
        runtime="gemini",
        system_prompt_path="/tmp/prompt.md",
    )

    mock_proc = MagicMock()
    mock_proc.pid = 111222
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await gemini_runtime.spawn(builder_config)

    # Verify policy file was created
    key = f"gemini-{builder_config.name}"
    assert key in gemini_runtime._policy_files
    policy_path = gemini_runtime._policy_files[key]
    assert policy_path.exists()

    # Kill should clean up policy file
    await gemini_runtime.kill(session_id)

    assert key not in gemini_runtime._policy_files
    assert not policy_path.exists()


@pytest.mark.asyncio
async def test_kill_force_kill_on_timeout(gemini_runtime, mock_config):
    mock_proc = MagicMock()
    mock_proc.pid = 333444
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_proc.kill = MagicMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await gemini_runtime.spawn(mock_config)

    # Kill should force kill on timeout
    await gemini_runtime.kill(session_id)

    mock_proc.terminate.assert_called_once()
    mock_proc.kill.assert_called_once()


def test_build_full_prompt(gemini_runtime, mock_config):
    # Create a temporary system prompt file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("System prompt content")
        mock_config.system_prompt_path = f.name

    prompt = gemini_runtime._build_full_prompt(mock_config)

    assert "System prompt content" in prompt
    assert "ROLE CONTRACT:" in prompt
    assert "You are test-agent, a developer agent." in prompt
    assert "TASK:" in prompt
    assert "Implement feature X" in prompt

    # Clean up
    Path(mock_config.system_prompt_path).unlink(missing_ok=True)


def test_role_behavioral_constraints(gemini_runtime):
    constraints = {
        "scout": "You MUST NOT edit, write, or delete any files.",
        "reviewer": "You MUST NOT edit, write, or delete any files.",
        "builder": "You MAY edit files and run build/test commands.",
        "tester": "You MAY write test files and run pytest/test commands.",
        "developer": "You MAY implement features and write code.",
        "merger": "You handle merge operations only.",
        "monitor": "You MUST NOT edit or write any files.",
    }

    for role, expected in constraints.items():
        result = gemini_runtime._role_behavioral_constraints(role)
        assert expected in result


def test_get_policy_rules(gemini_runtime):
    # Test builder policy rules
    builder_rules = gemini_runtime._get_policy_rules("builder")
    assert "deny_git_push" in builder_rules
    assert "allow_file_ops" in builder_rules

    # Test tester policy rules
    tester_rules = gemini_runtime._get_policy_rules("tester")
    assert "allow_test_commands" in tester_rules
    assert "deny_git_write" in tester_rules

    # Test developer policy rules
    dev_rules = gemini_runtime._get_policy_rules("developer")
    assert "deny_git_push" in dev_rules

    # Test monitor policy rules
    monitor_rules = gemini_runtime._get_policy_rules("monitor")
    assert "deny_write_file" in monitor_rules

    # Test roles without policy rules
    assert gemini_runtime._get_policy_rules("scout") == ""
    assert gemini_runtime._get_policy_rules("reviewer") == ""
    assert gemini_runtime._get_policy_rules("merger") == ""


def test_parse_stream_event_message(gemini_runtime):
    event = '{"type":"message","role":"assistant","content":"Hello World"}'
    result = gemini_runtime._parse_stream_event("test-session", event)
    assert result == "Hello World"


def test_parse_stream_event_tool_use(gemini_runtime):
    event = '{"type":"tool_use","tool":"run_shell_command","args":{"command":"echo test"}}'
    result = gemini_runtime._parse_stream_event("test-session", event)
    assert result == "[shell] $ echo test"


def test_parse_stream_event_tool_result(gemini_runtime):
    event = '{"type":"tool_result","tool":"run_shell_command","result":{"output":"test output"}}'
    result = gemini_runtime._parse_stream_event("test-session", event)
    assert result == "[result] test output"


def test_parse_stream_event_error(gemini_runtime):
    event = '{"type":"error","message":"Something went wrong","fatal":false}'
    result = gemini_runtime._parse_stream_event("test-session", event)
    assert result == "[error] Something went wrong"


def test_parse_stream_event_fatal_error(gemini_runtime):
    event = '{"type":"error","message":"Fatal error","fatal":true}'
    result = gemini_runtime._parse_stream_event("test-session", event)
    assert result == "[fatal] Fatal error"


def test_parse_stream_event_result(gemini_runtime):
    event = '{"type":"result","response":"Task completed","stats":{"model":{"turns":3},"tools":{"calls":5}}}'
    result = gemini_runtime._parse_stream_event("test-session", event)
    assert result == "Task completed\n[done] 3 turns, 5 tool calls"


def test_parse_stream_event_init(gemini_runtime):
    event = '{"type":"init","sessionId":"abc123","model":"gemini-2.5-pro"}'
    result = gemini_runtime._parse_stream_event("test-session", event)
    assert result == "[init] session started (gemini-2.5-pro)"


def test_parse_stream_event_unknown_type(gemini_runtime):
    event = '{"type":"unknown","data":"test"}'
    result = gemini_runtime._parse_stream_event("test-session", event)
    assert result is None


def test_parse_stream_event_invalid_json(gemini_runtime):
    event = "invalid json"
    result = gemini_runtime._parse_stream_event("test-session", event)
    assert result == "invalid json"


def test_parse_stream_event_empty_line(gemini_runtime):
    event = ""
    result = gemini_runtime._parse_stream_event("test-session", event)
    assert result is None