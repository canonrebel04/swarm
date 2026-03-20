"""
Test suite for Hermes runtime adapter.
"""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.runtimes.hermes import HermesRuntime
from src.runtimes.base import AgentConfig, AgentStatus


@pytest.fixture
def hermes_runtime():
    return HermesRuntime()


@pytest.fixture
def mock_config():
    return AgentConfig(
        name="test-agent",
        role="developer",
        task="Implement feature X",
        worktree_path="/tmp/worktree",
        model="hermes-2-pro",
        runtime="hermes",
        system_prompt_path="/tmp/prompt.md",
        extra_env={"TEST": "1"},
    )


def test_runtime_name(hermes_runtime):
    assert hermes_runtime.runtime_name == "hermes"


def test_capabilities(hermes_runtime):
    caps = hermes_runtime.capabilities
    assert caps.interactive_chat is True
    assert caps.headless_run is True
    assert caps.resume_session is True
    assert caps.streaming_output is True
    assert caps.tool_allowlist is True
    assert caps.sandbox_support is False
    assert caps.agent_profiles is False
    assert caps.parallel_safe is True


def test_role_toolsets(hermes_runtime):
    assert hermes_runtime.ROLE_TOOLSETS["scout"] == ["files", "memory"]
    assert hermes_runtime.ROLE_TOOLSETS["reviewer"] == ["files", "memory"]
    assert hermes_runtime.ROLE_TOOLSETS["builder"] == ["files", "terminal", "skills", "memory"]
    assert hermes_runtime.ROLE_TOOLSETS["developer"] == ["files", "terminal", "skills", "memory", "web", "github"]
    assert hermes_runtime.ROLE_TOOLSETS["merger"] == ["files", "terminal", "github"]


def test_role_skills(hermes_runtime):
    assert hermes_runtime.ROLE_SKILLS["scout"] == []
    assert hermes_runtime.ROLE_SKILLS["developer"] == []
    assert hermes_runtime.ROLE_SKILLS["merger"] == ["github-auth"]


def test_role_use_worktree(hermes_runtime):
    assert hermes_runtime.ROLE_USE_WORKTREE["scout"] is True
    assert hermes_runtime.ROLE_USE_WORKTREE["reviewer"] is True
    assert hermes_runtime.ROLE_USE_WORKTREE["coordinator"] is False
    assert hermes_runtime.ROLE_USE_WORKTREE["builder"] is True
    assert hermes_runtime.ROLE_USE_WORKTREE["developer"] is True
    assert hermes_runtime.ROLE_USE_WORKTREE["merger"] is False


@pytest.mark.asyncio
async def test_spawn_success(hermes_runtime, mock_config):
    # Mock system prompt file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("Test prompt")
        mock_config.system_prompt_path = f.name

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(mock_config)

    assert session_id == "hermes-test-agent-12345"
    assert len(hermes_runtime._sessions) == 1
    assert len(hermes_runtime._configs) == 1

    # Clean up
    Path(mock_config.system_prompt_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_spawn_with_worktree_disabled(hermes_runtime):
    # Test coordinator role which should have worktree disabled
    coord_config = AgentConfig(
        name="coord-agent",
        role="coordinator",
        task="Coordinate tasks",
        worktree_path="/tmp/worktree",
        model="hermes-2-pro",
        runtime="hermes",
        system_prompt_path="/tmp/prompt.md",
    )

    mock_proc = MagicMock()
    mock_proc.pid = 54321
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(coord_config)

    assert session_id == "hermes-coord-agent-54321"
    # Coordinator role should have worktree disabled
    assert hermes_runtime.ROLE_USE_WORKTREE["coordinator"] is False


@pytest.mark.asyncio
async def test_spawn_with_skills(hermes_runtime):
    # Test merger role which should have github-auth skill
    merger_config = AgentConfig(
        name="merger-agent",
        role="merger",
        task="Merge branches",
        worktree_path="/tmp/worktree",
        model="hermes-2-pro",
        runtime="hermes",
        system_prompt_path="/tmp/prompt.md",
    )

    mock_proc = MagicMock()
    mock_proc.pid = 67890
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(merger_config)

    assert session_id == "hermes-merger-agent-67890"
    # Merger role should have github-auth skill
    assert hermes_runtime.ROLE_SKILLS["merger"] == ["github-auth"]


@pytest.mark.asyncio
async def test_spawn_event_callback(hermes_runtime, mock_config):
    callback_called = []
    
    def mock_callback(event_type, agent_name, message):
        callback_called.append((event_type, agent_name, message))
    
    hermes_runtime._event_callback = mock_callback
    
    mock_proc = MagicMock()
    mock_proc.pid = 11111
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        await hermes_runtime.spawn(mock_config)

    assert len(callback_called) == 1
    assert callback_called[0][0] == "spawn"
    assert callback_called[0][1] == "test-agent"
    assert "spawned as developer via hermes" in callback_called[0][2]
    assert "toolsets: files,terminal,skills,memory,web,github" in callback_called[0][2]


@pytest.mark.asyncio
async def test_send_message(hermes_runtime, mock_config):
    # First spawn an agent
    mock_proc = MagicMock()
    mock_proc.pid = 22222
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(mock_config)

    # Now send a message
    mock_proc2 = MagicMock()
    mock_proc2.pid = 33333
    mock_proc2.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc2):
        await hermes_runtime.send_message(session_id, "Follow up message")

    # Should have replaced the process
    assert hermes_runtime._sessions[session_id] == mock_proc2


@pytest.mark.asyncio
async def test_stream_output(hermes_runtime, mock_config):
    # Create a mock process with stdout
    mock_stdout = AsyncMock()
    mock_stdout.__aiter__.return_value = [
        b'[tool:bash] $ ls -la\n',
        b'[tool:read] src/main.py\n',
        b'This is a plain text response\n',
    ]

    mock_proc = MagicMock()
    mock_proc.pid = 44444
    mock_proc.returncode = None
    mock_proc.stdout = mock_stdout

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(mock_config)

    # Stream the output
    outputs = []
    async for text in hermes_runtime.stream_output(session_id):
        outputs.append(text)

    assert len(outputs) == 3
    assert outputs[0] == "[tool:bash] $ ls -la"
    assert outputs[1] == "[tool:read] src/main.py"
    assert outputs[2] == "This is a plain text response"


@pytest.mark.asyncio
async def test_stream_output_handoff_json(hermes_runtime, mock_config):
    # Create a mock process with handoff JSON
    mock_stdout = AsyncMock()
    mock_stdout.__aiter__.return_value = [
        b'Working on the task...\n',
        b'{"role":"developer","status":"done","summary":"Task completed successfully","files_changed":["src/feature.py"],"handoff_to":"tester"}\n',
    ]

    mock_proc = MagicMock()
    mock_proc.pid = 55555
    mock_proc.returncode = None
    mock_proc.stdout = mock_stdout

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(mock_config)

    # Stream the output
    outputs = []
    async for text in hermes_runtime.stream_output(session_id):
        outputs.append(text)

    assert len(outputs) == 2
    assert outputs[0] == "Working on the task..."
    assert "[done] Task completed successfully" in outputs[1]
    assert "[files] src/feature.py" in outputs[1]
    assert "[handoff→] tester" in outputs[1]


@pytest.mark.asyncio
async def test_stream_output_session_id(hermes_runtime, mock_config):
    # Create a mock process with session ID
    mock_stdout = AsyncMock()
    mock_stdout.__aiter__.return_value = [
        b'Session ID: abc123-def456\n',
        b'Task processing...\n',
    ]

    mock_proc = MagicMock()
    mock_proc.pid = 66666
    mock_proc.returncode = None
    mock_proc.stdout = mock_stdout

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(mock_config)

    # Stream the output
    outputs = []
    async for text in hermes_runtime.stream_output(session_id):
        outputs.append(text)

    # Session ID should be captured but not output
    assert len(outputs) == 1
    assert outputs[0] == "Task processing..."
    assert hermes_runtime._session_ids[session_id] == "abc123-def456"


@pytest.mark.asyncio
async def test_stream_output_noise_filtering(hermes_runtime, mock_config):
    # Create a mock process with noise lines
    mock_stdout = AsyncMock()
    mock_stdout.__aiter__.return_value = [
        b'Hermes Agent v2.0\n',
        b'Model: hermes-2-pro\n',
        b'Provider: NousResearch\n',
        b'Using worktree: /tmp/worktree\n',
        b'Worktree path: /tmp/worktree\n',
        b'Actual response content\n',
    ]

    mock_proc = MagicMock()
    mock_proc.pid = 77777
    mock_proc.returncode = None
    mock_proc.stdout = mock_stdout

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(mock_config)

    # Stream the output
    outputs = []
    async for text in hermes_runtime.stream_output(session_id):
        outputs.append(text)

    # Noise lines should be filtered out
    assert len(outputs) == 1
    assert outputs[0] == "Actual response content"


@pytest.mark.asyncio
async def test_get_status_running(hermes_runtime, mock_config):
    mock_proc = MagicMock()
    mock_proc.pid = 88888
    mock_proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(mock_config)

    status = await hermes_runtime.get_status(session_id)
    assert status.name == "test-agent"
    assert status.role == "developer"
    assert status.state == "running"
    assert status.runtime == "hermes"
    assert status.pid == 88888


@pytest.mark.asyncio
async def test_get_status_done(hermes_runtime, mock_config):
    mock_proc = MagicMock()
    mock_proc.pid = 99999
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(mock_config)

    status = await hermes_runtime.get_status(session_id)
    assert status.state == "done"


@pytest.mark.asyncio
async def test_get_status_error(hermes_runtime, mock_config):
    mock_proc = MagicMock()
    mock_proc.pid = 111222
    mock_proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(mock_config)

    status = await hermes_runtime.get_status(session_id)
    assert status.state == "error"


@pytest.mark.asyncio
async def test_kill_process(hermes_runtime, mock_config):
    mock_proc = MagicMock()
    mock_proc.pid = 222333
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(mock_config)

    # Kill the process
    await hermes_runtime.kill(session_id)

    # Should be removed from tracking
    assert session_id not in hermes_runtime._sessions
    assert session_id not in hermes_runtime._configs
    assert session_id not in hermes_runtime._session_ids
    assert session_id not in hermes_runtime._last_output

    # Process should have been terminated
    mock_proc.terminate.assert_called_once()


@pytest.mark.asyncio
async def test_kill_force_kill_on_timeout(hermes_runtime, mock_config):
    mock_proc = MagicMock()
    mock_proc.pid = 333444
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_proc.kill = MagicMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        session_id = await hermes_runtime.spawn(mock_config)

    # Kill should force kill on timeout
    await hermes_runtime.kill(session_id)

    mock_proc.terminate.assert_called_once()
    mock_proc.kill.assert_called_once()


def test_build_full_prompt(hermes_runtime, mock_config):
    # Create a temporary system prompt file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("System prompt content")
        mock_config.system_prompt_path = f.name

    prompt = hermes_runtime._build_full_prompt(mock_config)

    assert "System prompt content" in prompt
    assert "ROLE CONTRACT:" in prompt
    assert "You are test-agent, a developer agent." in prompt
    assert "TASK:" in prompt
    assert "Implement feature X" in prompt
    assert '"role":"developer"' in prompt
    assert '"status":"done"' in prompt

    # Clean up
    Path(mock_config.system_prompt_path).unlink(missing_ok=True)


def test_role_behavioral_constraints(hermes_runtime):
    constraints = {
        "scout": "You MUST NOT edit, write, or delete any files.",
        "reviewer": "You MUST NOT edit, write, or delete any files.",
        "builder": "You MAY edit files and run build/test commands.",
        "tester": "You MAY write test files and run test commands.",
        "developer": "You MAY implement features and write code.",
        "merger": "You handle merge operations only.",
        "monitor": "You MUST NOT edit or write any files.",
    }

    for role, expected in constraints.items():
        result = hermes_runtime._role_behavioral_constraints(role)
        assert expected in result


def test_parse_output_line_tool_activity(hermes_runtime):
    line = "[tool:bash] $ pytest tests/"
    result = hermes_runtime._parse_output_line("test-session", line)
    assert result == "[tool:bash] $ pytest tests/"


def test_parse_output_line_handoff_json(hermes_runtime):
    line = '{"role":"developer","status":"done","summary":"Task done","files_changed":["src/file.py"],"handoff_to":"tester"}'
    result = hermes_runtime._parse_output_line("test-session", line)
    assert result == "[done] Task done\n[files] src/file.py\n[handoff→] tester"


def test_parse_output_line_session_id(hermes_runtime):
    line = "Session ID: abc123-def456"
    result = hermes_runtime._parse_output_line("test-session", line)
    assert result is None  # Session ID is internal, not surfaced


def test_parse_output_line_noise_filtering(hermes_runtime):
    noise_lines = [
        "Hermes Agent v2.0",
        "Model: hermes-2-pro",
        "Provider: NousResearch",
        "Using worktree: /tmp/worktree",
        "Worktree path: /tmp/worktree",
    ]
    
    for line in noise_lines:
        result = hermes_runtime._parse_output_line("test-session", line)
        assert result is None, f"Noise line '{line}' should be filtered out"


def test_parse_output_line_plain_text(hermes_runtime):
    line = "This is a normal response line"
    result = hermes_runtime._parse_output_line("test-session", line)
    assert result == "This is a normal response line"


def test_parse_output_line_empty(hermes_runtime):
    line = ""
    result = hermes_runtime._parse_output_line("test-session", line)
    assert result is None


def test_parse_output_line_invalid_json(hermes_runtime):
    line = "{\"invalid\" json"
    result = hermes_runtime._parse_output_line("test-session", line)
    assert result == "{\"invalid\" json"  # Not valid JSON, pass through as plain text


def test_parse_output_line_json_without_status(hermes_runtime):
    line = '{"role":"developer","message":"working"}'
    result = hermes_runtime._parse_output_line("test-session", line)
    assert result == '{"role":"developer","message":"working"}'  # Not a handoff JSON, pass through