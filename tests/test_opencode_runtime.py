"""
Test suite for OpenCode runtime adapter.
"""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.runtimes.opencode import OpenCodeRuntime
from src.runtimes.base import AgentConfig, AgentStatus


class MockResponse:
    """Mock aiohttp response with async context manager support."""
    def __init__(self, status=200, json_data=None):
        self.status = status
        self._json_data = json_data or {}
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def json(self):
        return self._json_data


def create_mock_http_client(status=200, json_response=None):
    """Helper to create a properly mocked aiohttp ClientSession."""
    mock_http = MagicMock()
    
    # Mock get method
    mock_resp = MockResponse(status=status, json_data=json_response)
    mock_http.get.return_value = mock_resp
    
    # Mock post method
    mock_post_resp = MockResponse(status=status, json_data=json_response)
    mock_http.post.return_value = mock_post_resp
    
    # Mock delete method
    mock_delete_resp = MockResponse(status=status)
    mock_http.delete.return_value = mock_delete_resp
    
    return mock_http


@pytest.fixture
def opencode_runtime():
    return OpenCodeRuntime()


@pytest.fixture
def mock_config():
    return AgentConfig(
        name="test-agent",
        role="developer",
        task="Implement feature X",
        worktree_path="/tmp/worktree",
        model="anthropic/claude-opus-4-5",
        runtime="opencode",
        system_prompt_path="/tmp/prompt.md",
        extra_env={"TEST": "1"},
    )


def test_runtime_name(opencode_runtime):
    assert opencode_runtime.runtime_name == "opencode"


def test_capabilities(opencode_runtime):
    caps = opencode_runtime.capabilities
    assert caps.interactive_chat is True
    assert caps.headless_run is True
    assert caps.resume_session is True
    assert caps.streaming_output is True
    assert caps.tool_allowlist is True
    assert caps.sandbox_support is False
    assert caps.agent_profiles is False
    assert caps.parallel_safe is True


def test_role_tools(opencode_runtime):
    assert opencode_runtime.ROLE_TOOLS["scout"] == ["read", "glob", "grep", "ls"]
    assert opencode_runtime.ROLE_TOOLS["reviewer"] == ["read", "glob", "grep", "ls"]
    assert "bash" not in opencode_runtime.ROLE_TOOLS["scout"]  # scout cannot run bash
    assert "bash" in opencode_runtime.ROLE_TOOLS["builder"]
    assert opencode_runtime.ROLE_TOOLS["developer"] == []  # unrestricted
    assert opencode_runtime.ROLE_TOOLS["merger"] == []  # unrestricted


def test_role_models(opencode_runtime):
    assert opencode_runtime.ROLE_MODEL["scout"] == "anthropic/claude-sonnet-4-5"
    assert opencode_runtime.ROLE_MODEL["reviewer"] == "anthropic/claude-opus-4-5"
    assert opencode_runtime.ROLE_MODEL["developer"] == "anthropic/claude-opus-4-5"
    assert opencode_runtime.ROLE_MODEL["monitor"] == "anthropic/claude-haiku-3-5"


def test_known_tools(opencode_runtime):
    expected_tools = {
        "read", "write", "edit", "bash", "glob", "grep", "ls",
        "todo_read", "todo_write", "fetch", "task",
    }
    assert opencode_runtime.KNOWN_TOOLS == expected_tools


def test_base_port(opencode_runtime):
    assert opencode_runtime.BASE_PORT == 9100


@pytest.mark.asyncio
async def test_ensure_server_new(opencode_runtime):
    worktree = "/tmp/test-worktree"
    
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.pid = 12345
    
    mock_http = create_mock_http_client(status=200)
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        port, http = await opencode_runtime._ensure_server(worktree)
        
        assert port == 9100
        assert http == mock_http
        assert worktree in opencode_runtime._servers


@pytest.mark.asyncio
async def test_ensure_server_existing(opencode_runtime):
    worktree = "/tmp/test-worktree"
    
    # First call - create server
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.pid = 12345
    
    mock_http = create_mock_http_client(status=200)
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        port1, http1 = await opencode_runtime._ensure_server(worktree)
        assert port1 == 9100

    # Second call - should reuse existing server
    port2, http2 = await opencode_runtime._ensure_server(worktree)
    assert port2 == 9100
    assert http2 == mock_http
    assert len(opencode_runtime._servers) == 1  # only one server created


@pytest.mark.asyncio
async def test_ensure_server_port_increment(opencode_runtime):
    worktree1 = "/tmp/test-worktree1"
    worktree2 = "/tmp/test-worktree2"
    
    mock_proc1 = MagicMock()
    mock_proc1.returncode = None
    mock_proc1.pid = 11111
    
    mock_proc2 = MagicMock()
    mock_proc2.returncode = None
    mock_proc2.pid = 22222
    
    # Create proper async context manager mocks for aiohttp responses
    class MockResponse:
        def __init__(self, status):
            self.status = status
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    mock_response1 = MockResponse(200)
    mock_response2 = MockResponse(200)
    
    # Mock the ClientSession to return our mock responses
    # Use regular Mock instead of AsyncMock to avoid coroutine issues
    mock_http1 = MagicMock()
    mock_http1.get.return_value = mock_response1
    
    mock_http2 = MagicMock()
    mock_http2.get.return_value = mock_response2
    
    with patch("asyncio.create_subprocess_exec", side_effect=[mock_proc1, mock_proc2]), \
         patch("aiohttp.ClientSession", side_effect=[mock_http1, mock_http2]):
        
        port1, http1 = await opencode_runtime._ensure_server(worktree1)
        port2, http2 = await opencode_runtime._ensure_server(worktree2)
        
        assert port1 == 9100
        assert port2 == 9101  # incremented
        assert len(opencode_runtime._servers) == 2  # two servers created


@pytest.mark.asyncio
async def test_wait_for_health_success(opencode_runtime):
    mock_http = create_mock_http_client(status=200)
    
    await opencode_runtime._wait_for_health(mock_http, timeout=1.0)
    
    # Should have called health endpoint
    mock_http.get.assert_called_with("/global/health")


@pytest.mark.asyncio
async def test_wait_for_health_timeout(opencode_runtime):
    mock_http = create_mock_http_client(status=500)
    
    with pytest.raises(TimeoutError):
        await opencode_runtime._wait_for_health(mock_http, timeout=0.1)


@pytest.mark.asyncio
async def test_spawn_success(opencode_runtime, mock_config):
    # Mock system prompt file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("Test prompt")
        mock_config.system_prompt_path = f.name

    # Mock server and HTTP responses
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.pid = 12345
    
    mock_http = AsyncMock()
    
    # Mock session creation response
    session_response = {"id": "test-session-123"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    # Mock health check
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(mock_config)

    assert session_id.startswith("opencode-test-agent-")
    assert len(opencode_runtime._sessions) == 1
    assert len(opencode_runtime._configs) == 1
    assert len(opencode_runtime._session_worktree) == 1

    # Clean up
    Path(mock_config.system_prompt_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_spawn_with_tool_restrictions(opencode_runtime):
    # Test scout role which has tool restrictions
    scout_config = AgentConfig(
        name="scout-agent",
        role="scout",
        task="Explore codebase",
        worktree_path="/tmp/worktree",
        model="anthropic/claude-sonnet-4-5",
        runtime="opencode",
        system_prompt_path="/tmp/prompt.md",
    )

    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "scout-session-456"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(scout_config)

    # Scout should have tool restrictions
    assert opencode_runtime.ROLE_TOOLS["scout"] == ["read", "glob", "grep", "ls"]
    assert "bash" not in opencode_runtime.ROLE_TOOLS["scout"]


@pytest.mark.asyncio
async def test_spawn_event_callback(opencode_runtime, mock_config):
    callback_called = []
    
    def mock_callback(event_type, agent_name, message):
        callback_called.append((event_type, agent_name, message))
    
    opencode_runtime._event_callback = mock_callback
    
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "callback-session-789"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        await opencode_runtime.spawn(mock_config)

    assert len(callback_called) == 2  # server start + spawn
    spawn_event = callback_called[1]
    assert spawn_event[0] == "spawn"
    assert spawn_event[1] == "test-agent"
    assert "spawned as developer via opencode" in spawn_event[2]


@pytest.mark.asyncio
async def test_send_message(opencode_runtime, mock_config):
    # First spawn an agent
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "message-session-111"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(mock_config)

    # Now send a message
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value={"parts": []})
    
    await opencode_runtime.send_message(session_id, "Follow up message")
    
    # Should have called the message endpoint
    mock_http.post.assert_called_with(
        f"/session/message-session-111/message",
        json={
            "parts": [{"type": "text", "text": "Follow up message"}],
            "model": {"providerID": "anthropic", "modelID": "claude-opus-4-5"},
        }
    )


@pytest.mark.asyncio
async def test_stream_output(opencode_runtime, mock_config):
    # First spawn an agent
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "stream-session-222"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(mock_config)

    # Mock message response with parts
    message_data = [{
        "parts": [
            {"type": "text", "content": "Hello world"},
            {"type": "tool-use", "toolName": "bash", "input": {"command": "ls -la"}}
        ]
    }]
    mock_http.get.return_value.__aenter__.return_value.json = AsyncMock(return_value=message_data)
    mock_http.get.return_value.__aenter__.return_value.status = 200

    # Stream the output
    outputs = []
    async for text in opencode_runtime.stream_output(session_id):
        outputs.append(text)
        if len(outputs) >= 2:  # Get both parts
            break

    assert len(outputs) == 2
    assert outputs[0] == "Hello world"
    assert outputs[1] == "[bash] $ ls -la"


@pytest.mark.asyncio
async def test_stream_output_text_part(opencode_runtime, mock_config):
    # Setup
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "text-session-333"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(mock_config)

    # Mock text part
    message_data = [{
        "parts": [
            {"type": "text", "content": "This is a text response"}
        ]
    }]
    mock_http.get.return_value.__aenter__.return_value.json = AsyncMock(return_value=message_data)
    mock_http.get.return_value.__aenter__.return_value.status = 200

    # Stream the output
    outputs = []
    async for text in opencode_runtime.stream_output(session_id):
        outputs.append(text)
        break

    assert len(outputs) == 1
    assert outputs[0] == "This is a text response"


@pytest.mark.asyncio
async def test_stream_output_tool_use(opencode_runtime, mock_config):
    # Setup
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "tool-session-444"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(mock_config)

    # Mock tool-use parts
    message_data = [{
        "parts": [
            {"type": "tool-use", "toolName": "write", "input": {"filePath": "src/file.py"}},
            {"type": "tool-use", "toolName": "read", "input": {"filePath": "src/config.json"}},
            {"type": "tool-use", "toolName": "bash", "input": {"command": "python -m pytest"}},
        ]
    }]
    mock_http.get.return_value.__aenter__.return_value.json = AsyncMock(return_value=message_data)
    mock_http.get.return_value.__aenter__.return_value.status = 200

    # Stream the output
    outputs = []
    async for text in opencode_runtime.stream_output(session_id):
        outputs.append(text)
        if len(outputs) >= 3:
            break

    assert len(outputs) == 3
    assert outputs[0] == "[write] src/file.py"
    assert outputs[1] == "[read] src/config.json"
    assert outputs[2] == "[bash] $ python -m pytest"


@pytest.mark.asyncio
async def test_stream_output_tool_result(opencode_runtime, mock_config):
    # Setup
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "result-session-555"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(mock_config)

    # Mock tool-result parts
    message_data = [{
        "parts": [
            {
                "type": "tool-result",
                "toolUseID": "tool-123",
                "content": [{"type": "text", "text": "Command executed successfully"}],
                "isError": False
            },
            {
                "type": "tool-result",
                "toolUseID": "tool-456",
                "content": [{"type": "text", "text": "File not found"}],
                "isError": True
            }
        ]
    }]
    mock_http.get.return_value.__aenter__.return_value.json = AsyncMock(return_value=message_data)
    mock_http.get.return_value.__aenter__.return_value.status = 200

    # Stream the output
    outputs = []
    async for text in opencode_runtime.stream_output(session_id):
        outputs.append(text)
        if len(outputs) >= 2:
            break

    assert len(outputs) == 2
    assert outputs[0] == "[result] Command executed successfully"
    assert outputs[1] == "[error] File not found"


@pytest.mark.asyncio
async def test_stream_output_step_finish(opencode_runtime, mock_config):
    # Setup
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "step-session-666"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(mock_config)

    # Mock step-finish part
    message_data = [{
        "parts": [
            {
                "type": "step-finish",
                "finishReason": "stop",
                "usage": {"inputTokens": 100, "outputTokens": 50}
            }
        ]
    }]
    mock_http.get.return_value.__aenter__.return_value.json = AsyncMock(return_value=message_data)
    mock_http.get.return_value.__aenter__.return_value.status = 200

    # Stream the output
    outputs = []
    async for text in opencode_runtime.stream_output(session_id):
        outputs.append(text)
        break

    assert len(outputs) == 1
    assert outputs[0] == "[step] done — 100 in / 50 out tokens"


@pytest.mark.asyncio
async def test_get_status_running(opencode_runtime, mock_config):
    # Setup
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "status-session-777"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(mock_config)

    # Mock status response
    status_data = {
        "status-session-777": {
            "status": "running"
        }
    }
    mock_http.get.return_value.__aenter__.return_value.json = AsyncMock(return_value=status_data)
    mock_http.get.return_value.__aenter__.return_value.status = 200

    status = await opencode_runtime.get_status(session_id)
    assert status.name == "test-agent"
    assert status.role == "developer"
    assert status.state == "running"
    assert status.runtime == "opencode"


@pytest.mark.asyncio
async def test_get_status_done(opencode_runtime, mock_config):
    # Setup
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "done-session-888"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(mock_config)

    # Mock status response - idle means done
    status_data = {
        "done-session-888": {
            "status": "idle"
        }
    }
    mock_http.get.return_value.__aenter__.return_value.json = AsyncMock(return_value=status_data)
    mock_http.get.return_value.__aenter__.return_value.status = 200

    status = await opencode_runtime.get_status(session_id)
    assert status.state == "done"


@pytest.mark.asyncio
async def test_get_status_error(opencode_runtime, mock_config):
    # Setup
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "error-session-999"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(mock_config)

    # Mock status response - error
    status_data = {
        "error-session-999": {
            "status": "error"
        }
    }
    mock_http.get.return_value.__aenter__.return_value.json = AsyncMock(return_value=status_data)
    mock_http.get.return_value.__aenter__.return_value.status = 200

    status = await opencode_runtime.get_status(session_id)
    assert status.state == "error"


@pytest.mark.asyncio
async def test_kill_session(opencode_runtime, mock_config):
    # Setup
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "kill-session-111"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        session_id = await opencode_runtime.spawn(mock_config)

    # Kill the session
    mock_http.post.return_value.__aenter__.return_value.status = 200
    mock_http.delete.return_value.__aenter__.return_value.status = 200
    
    await opencode_runtime.kill(session_id)

    # Should be removed from tracking
    assert session_id not in opencode_runtime._configs
    assert session_id not in opencode_runtime._oc_sessions
    assert session_id not in opencode_runtime._session_worktree
    assert session_id not in opencode_runtime._last_output

    # Should have called abort and delete endpoints
    mock_http.post.assert_called_with("/session/kill-session-111/abort")
    mock_http.delete.assert_called_with("/session/kill-session-111")


@pytest.mark.asyncio
async def test_kill_server(opencode_runtime, mock_config):
    # Setup
    worktree = "/tmp/test-worktree"
    mock_proc = MagicMock()
    mock_proc.returncode = None
    
    mock_http = AsyncMock()
    session_response = {"id": "server-session-222"}
    mock_http.post.return_value.__aenter__.return_value.json = AsyncMock(return_value=session_response)
    mock_http.post.return_value.__aenter__.return_value.status = 200
    
    health_response = MagicMock()
    health_response.status = 200
    mock_http.get.return_value.__aenter__.return_value = health_response

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("aiohttp.ClientSession", return_value=mock_http):
        
        await opencode_runtime.spawn(mock_config)
        assert worktree in opencode_runtime._servers

    # Kill the server
    await opencode_runtime.kill_server(worktree)
    
    # Should be removed from servers
    assert worktree not in opencode_runtime._servers
    
    # Should have closed HTTP session and terminated process
    mock_http.close.assert_called_once()
    mock_proc.terminate.assert_called_once()


def test_build_system_prompt(opencode_runtime, mock_config):
    # Create a temporary system prompt file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("System prompt content")
        mock_config.system_prompt_path = f.name

    prompt = opencode_runtime._build_system_prompt(mock_config)

    assert "System prompt content" in prompt
    assert "ROLE CONTRACT:" in prompt
    assert "You are test-agent, a developer agent." in prompt
    assert '"role":"developer"' in prompt
    assert '"status":"done"' in prompt

    # Clean up
    Path(mock_config.system_prompt_path).unlink(missing_ok=True)


def test_role_behavioral_constraints(opencode_runtime):
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
        result = opencode_runtime._role_behavioral_constraints(role)
        assert expected in result


def test_parse_part_text(opencode_runtime):
    part = {"type": "text", "content": "Hello world"}
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "Hello world"


def test_parse_part_text_empty(opencode_runtime):
    part = {"type": "text", "content": ""}
    result = opencode_runtime._parse_part("test-session", part)
    assert result is None


def test_parse_part_tool_use_bash(opencode_runtime):
    part = {"type": "tool-use", "toolName": "bash", "input": {"command": "echo test"}}
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[bash] $ echo test"


def test_parse_part_tool_use_write(opencode_runtime):
    part = {"type": "tool-use", "toolName": "write", "input": {"filePath": "src/file.py"}}
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[write] src/file.py"


def test_parse_part_tool_use_read(opencode_runtime):
    part = {"type": "tool-use", "toolName": "read", "input": {"filePath": "config.json"}}
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[read] config.json"


def test_parse_part_tool_use_ls(opencode_runtime):
    part = {"type": "tool-use", "toolName": "ls", "input": {"path": "src"}}
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[ls] src"


def test_parse_part_tool_use_glob(opencode_runtime):
    part = {"type": "tool-use", "toolName": "glob", "input": {"pattern": "*.py"}}
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[glob] *.py"


def test_parse_part_tool_use_grep(opencode_runtime):
    part = {"type": "tool-use", "toolName": "grep", "input": {"pattern": "test", "path": "src"}}
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[grep] test in src"


def test_parse_part_tool_use_fetch(opencode_runtime):
    part = {"type": "tool-use", "toolName": "fetch", "input": {"url": "https://example.com"}}
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[fetch] https://example.com"


def test_parse_part_tool_use_task(opencode_runtime):
    part = {"type": "tool-use", "toolName": "task", "input": {"description": "Implement feature X"}}
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[task] spawning: Implement feature X"


def test_parse_part_tool_use_todo(opencode_runtime):
    part = {"type": "tool-use", "toolName": "todo_read", "input": {}}
    result = opencode_runtime._parse_part("test-session", part)
    assert result is None  # todo operations are internal


def test_parse_part_tool_use_unknown(opencode_runtime):
    part = {"type": "tool-use", "toolName": "unknown", "input": {"data": "test"}}
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[unknown] {'data': 'test'}"


def test_parse_part_tool_result_success(opencode_runtime):
    part = {
        "type": "tool-result",
        "toolUseID": "tool-123",
        "content": [{"type": "text", "text": "Success"}],
        "isError": False
    }
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[result] Success"


def test_parse_part_tool_result_error(opencode_runtime):
    part = {
        "type": "tool-result",
        "toolUseID": "tool-456",
        "content": [{"type": "text", "text": "Failed"}],
        "isError": True
    }
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[error] Failed"


def test_parse_part_tool_result_multiline(opencode_runtime):
    part = {
        "type": "tool-result",
        "toolUseID": "tool-789",
        "content": [{"type": "text", "text": "Line 1\nLine 2\nLine 3"}],
        "isError": False
    }
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[result] Line 1\nLine 2\nLine 3"


def test_parse_part_tool_result_long(opencode_runtime):
    part = {
        "type": "tool-result",
        "toolUseID": "tool-999",
        "content": [{"type": "text", "text": "\n".join([f"Line {i}" for i in range(20)])}],
        "isError": False
    }
    result = opencode_runtime._parse_part("test-session", part)
    # Should be truncated to 10 lines
    lines = result.split("\n")
    assert len(lines) <= 11  # [result] prefix + 10 lines


def test_parse_part_tool_result_empty(opencode_runtime):
    part = {
        "type": "tool-result",
        "toolUseID": "tool-000",
        "content": [],
        "isError": False
    }
    result = opencode_runtime._parse_part("test-session", part)
    assert result is None


def test_parse_part_step_finish_stop(opencode_runtime):
    part = {
        "type": "step-finish",
        "finishReason": "stop",
        "usage": {"inputTokens": 100, "outputTokens": 50}
    }
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[step] done — 100 in / 50 out tokens"


def test_parse_part_step_finish_error(opencode_runtime):
    part = {
        "type": "step-finish",
        "finishReason": "error",
        "usage": {"inputTokens": 50, "outputTokens": 25}
    }
    result = opencode_runtime._parse_part("test-session", part)
    assert result == "[step] failed"


def test_parse_part_step_finish_length(opencode_runtime):
    part = {
        "type": "step-finish",
        "finishReason": "length",
        "usage": {"inputTokens": 200, "outputTokens": 100}
    }
    result = opencode_runtime._parse_part("test-session", part)
    assert result is None  # length reason is skipped


def test_parse_part_step_start(opencode_runtime):
    part = {"type": "step-start"}
    result = opencode_runtime._parse_part("test-session", part)
    assert result is None  # step-start is not surfaced


def test_parse_part_unknown_type(opencode_runtime):
    part = {"type": "unknown", "data": "test"}
    result = opencode_runtime._parse_part("test-session", part)
    assert result is None  # unknown types are skipped