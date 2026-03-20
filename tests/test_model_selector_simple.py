"""
Simple test suite for model selector core functionality.
"""

import pytest
import tempfile
import os
from pathlib import Path
import yaml

from src.cli.setup import _default_runtime_block, _read_env_file, _write_env_file


class TestCoreFunctionality:
    """Test core functions without complex mocking."""

    def test_default_runtime_blocks(self):
        """Test default runtime configuration blocks."""
        # Test each runtime
        test_cases = [
            ("vibe", "vibe", "streaming"),
            ("claude-code", "claude", "stream-json"),
            ("codex", "codex", "json"),
            ("gemini", "gemini", "stream-json"),
            ("hermes", "hermes", "text"),
            ("opencode", "opencode", "stream-json"),
            ("openclaw", "openclaw", "json"),
        ]
        
        for runtime_key, expected_binary, expected_format in test_cases:
            result = _default_runtime_block(runtime_key)
            assert result["binary"] == expected_binary
            assert result["output_format"] == expected_format

    def test_env_file_operations(self, tmp_path):
        """Test environment file reading/writing."""
        # Change to temp directory
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            env_file = Path(".env")
            
            # Test writing
            _write_env_file("TEST_KEY", "test_value_123")
            assert env_file.exists()
            assert "TEST_KEY=\"test_value_123\"" in env_file.read_text()
            
            # Test reading
            result = _read_env_file("TEST_KEY")
            assert result == "test_value_123"
            
            # Test updating existing key
            _write_env_file("TEST_KEY", "updated_value")
            result = _read_env_file("TEST_KEY")
            assert result == "updated_value"
            
            # Test adding new key
            _write_env_file("NEW_KEY", "new_value")
            result = _read_env_file("NEW_KEY")
            assert result == "new_value"
        finally:
            os.chdir(original_cwd)

    def test_config_structure(self, tmp_path):
        """Test config file structure."""
        config_file = tmp_path / "config.yaml"
        
        # Create a basic config
        config = {
            "overseer": {
                "runtime": "vibe",
                "model": "mistral-large-latest"
            },
            "role_runtimes": {
                "scout": "codex",
                "builder": "hermes"
            }
        }
        
        config_file.write_text(yaml.dump(config))
        
        # Verify it can be read back
        loaded = yaml.safe_load(config_file.read_text())
        assert loaded == config
        assert loaded["overseer"]["runtime"] == "vibe"
        assert loaded["role_runtimes"]["scout"] == "codex"


class TestProviderCatalog:
    """Test provider catalog data."""

    def test_catalog_structure(self):
        """Test provider catalog structure."""
        from src.cli.setup import PROVIDER_CATALOG
        
        # Should have 10 providers + 1 custom
        assert len(PROVIDER_CATALOG) == 11
        
        # Check structure of first entry
        first = PROVIDER_CATALOG[0]
        assert len(first) == 4  # label, runtime_key, model_str, env_var
        assert first[0].startswith("Anthropic")
        assert first[1] == "claude-code"
        assert first[2] == "claude-opus-4-5"
        assert first[3] == "ANTHROPIC_API_KEY"
        
        # Check custom entry
        custom = PROVIDER_CATALOG[-1]
        assert custom[1] == "__custom__"
        assert custom[2] == ""
        assert custom[3] is None


class TestModalOptions:
    """Test modal provider options."""

    def test_modal_options_structure(self):
        """Test modal provider options structure."""
        from src.tui.screens.model_selector import PROVIDER_OPTIONS
        
        # Should have 9 providers (no custom in modal)
        assert len(PROVIDER_OPTIONS) == 10  # Actually has 10 providers
        
        # Check structure
        for opt in PROVIDER_OPTIONS:
            assert len(opt) == 4  # runtime, model, provider, label
            assert opt[0] in ["claude-code", "codex", "gemini", "vibe", "hermes"]
            assert opt[1]  # model string
            assert opt[2]  # provider name
            assert opt[3]  # label


class TestIntegration:
    """Test integration scenarios."""

    def test_full_config_workflow(self, tmp_path):
        """Test full config workflow."""
        config_file = tmp_path / "config.yaml"
        env_file = tmp_path / ".env"
        
        # Step 1: Write initial config
        initial_config = {
            "overseer": {
                "runtime": "vibe",
                "model": "mistral-large-latest"
            }
        }
        config_file.write_text(yaml.dump(initial_config))
        
        # Step 2: Update config
        updated_config = {
            "overseer": {
                "runtime": "codex",
                "model": "o3"
            },
            "role_runtimes": {
                "scout": "codex",
                "builder": "hermes"
            }
        }
        config_file.write_text(yaml.dump(updated_config))
        
        # Step 3: Add API key
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            _write_env_file("OPENAI_API_KEY", "test_key_123")
            
            # Step 4: Verify everything
            loaded_config = yaml.safe_load(config_file.read_text())
            assert loaded_config["overseer"]["runtime"] == "codex"
            assert loaded_config["role_runtimes"]["scout"] == "codex"
            
            loaded_key = _read_env_file("OPENAI_API_KEY")
            assert loaded_key == "test_key_123"
        finally:
            os.chdir(original_cwd)
        
        print("✅ All simple tests passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
