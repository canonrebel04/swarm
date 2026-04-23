import pytest
from unittest.mock import MagicMock, patch
import paramiko
from src.runtimes.ssh import SSHRuntime
from src.runtimes.base import AgentConfig

@pytest.mark.asyncio
async def test_ssh_runtime_security_policy():
    """
    Test that SSHRuntime does not use AutoAddPolicy and loads system host keys.
    """
    with patch("paramiko.SSHClient") as mock_ssh_client_class:
        mock_client = MagicMock()
        mock_ssh_client_class.return_value = mock_client

        runtime = SSHRuntime()
        config = AgentConfig(
            name="test-agent",
            role="tester",
            task="do something",
            worktree_path="/tmp/test",
            model="gpt-4",
            runtime="ssh",
            system_prompt_path="prompts/system.txt",
            remote_host="example.com",
            remote_user="user"
        )

        # We mock exec_command to avoid further issues in spawn
        mock_client.exec_command.return_value = (MagicMock(), MagicMock(), MagicMock())

        try:
            await runtime.spawn(config)
        except Exception:
            # We don't care if it fails later (e.g. sync_worktree),
            # we just want to check the connection setup.
            pass

        # Verify load_system_host_keys was called
        mock_client.load_system_host_keys.assert_called_once()

        # Verify set_missing_host_key_policy was NOT called with AutoAddPolicy
        for call in mock_client.set_missing_host_key_policy.call_args_list:
            args, kwargs = call
            assert not isinstance(args[0], paramiko.AutoAddPolicy)

        # In fact, with my change, it shouldn't be called at all since I removed the line
        # and didn't replace it with another policy (default is RejectPolicy).
        mock_client.set_missing_host_key_policy.assert_not_called()
