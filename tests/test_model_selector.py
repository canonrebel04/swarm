"""
Test suite for model selector functionality.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
import yaml

from src.cli.setup import run_setup, _read_config, _write_config
from src.tui.screens.model_selector import ModelSelectorModal


@pytest.fixture
def temp_config():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"overseer": {"runtime": "vibe", "model": "mistral-large-latest"}}, f)
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_env():
    """Create a temporary env file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        yield f.name
    os.unlink(f.name)


class TestCLISetup:
    """Test the CLI setup wizard functionality."""

    def test_read_config_empty(self, temp_config):
        """Test reading empty config."""
        # Override CONFIG_PATH
        original_path = Path("config.yaml")
        try:
            Path("config.yaml").unlink()  # Remove if exists
        except FileNotFoundError:
            pass
        
        result = _read_config()
        assert result == {}

    def test_write_config(self, temp_config):
        """Test writing config."""
        # Override CONFIG_PATH
        config_path = Path(temp_config)
        cfg = {"overseer": {"runtime": "codex", "model": "o3"}}
        config_path.write_text(yaml.dump(cfg))
        
        result = _read_config()
        assert result == cfg

    def test_default_runtime_block(self):
        """Test default runtime configuration."""
        from src.cli.setup import _default_runtime_block
        
        result = _default_runtime_block("vibe")
        assert result["binary"] == "vibe"
        assert result["output_format"] == "streaming"

    @patch('builtins.input', side_effect=['1', '', ''])
    @patch('builtins.print')
    def test_setup_basic_flow(self, mock_print, mock_input, temp_config, temp_env):
        """Test basic setup flow."""
        # Mock config path
        config_path = Path(temp_config)
        env_path = Path(temp_env)
        
        # Mock os.environ and path operations
        with patch('os.environ', {}), \
             patch('src.cli.setup.CONFIG_PATH', config_path), \
             patch('src.cli.setup.Path') as mock_path:
            
            mock_path.return_value = config_path
            
            # Run setup
            run_setup()
            
            # Verify config was written
            assert config_path.exists()
            config = yaml.safe_load(config_path.read_text())
            assert 'overseer' in config


class TestModelSelectorModal:
    """Test the TUI model selector modal."""

    @pytest.fixture
    def modal(self):
        """Create a model selector modal for testing."""
        return ModelSelectorModal()

    def test_modal_initialization(self, modal):
        """Test modal initialization."""
        from src.tui.screens.model_selector import PROVIDER_OPTIONS
        assert modal._filtered == PROVIDER_OPTIONS
        assert not modal._custom_mode

    def test_populate_list(self, modal):
        """Test list population."""
        from src.tui.screens.model_selector import PROVIDER_OPTIONS
        modal._populate_list()
        # Should have all options plus custom
        assert len(modal._filtered) == len(PROVIDER_OPTIONS)

    def test_populate_list_filtered(self, modal):
        """Test filtered list population."""
        from src.tui.screens.model_selector import PROVIDER_OPTIONS
        modal._populate_list("openai")
        # Should only show OpenAI options
        assert len(modal._filtered) == 2  # o3 and o4-mini

    def test_save_action(self, modal, temp_config):
        """Test save action."""
        # Mock config path
        config_path = Path(temp_config)
        
        with patch('src.tui.screens.model_selector.CONFIG_PATH', config_path):
            # Set custom values
            modal.query_one("#custom-runtime", Input).value = "codex"
            modal.query_one("#custom-model",   Input).value = "o3"
            
            # Mock dismiss
            with patch.object(modal, 'dismiss'):
                modal._do_save()
                
                # Verify config was written
                assert config_path.exists()
                config = yaml.safe_load(config_path.read_text())
                assert config['overseer']['runtime'] == 'codex'
                assert config['overseer']['model'] == 'o3'


class TestIntegration:
    """Test integration between components."""

    def test_config_persistence(self, temp_config):
        """Test config persistence across reads/writes."""
        config_path = Path(temp_config)
        
        # Write initial config
        initial = {"overseer": {"runtime": "vibe", "model": "mistral-large-latest"}}
        config_path.write_text(yaml.dump(initial))
        
        # Read and verify
        result = _read_config()
        assert result == initial
        
        # Update config
        updated = {"overseer": {"runtime": "codex", "model": "o3"}}
        config_path.write_text(yaml.dump(updated))
        
        # Read and verify update
        result = _read_config()
        assert result == updated

    def test_env_file_handling(self, temp_env):
        """Test environment file handling."""
        env_path = Path(temp_env)
        
        # Write test env file
        env_path.write_text('ANTHROPIC_API_KEY="test_key_123"\n')
        
        # Test reading
        from src.cli.setup import _read_env_file
        result = _read_env_file("ANTHROPIC_API_KEY")
        assert result == "test_key_123"
        
        # Test writing
        from src.cli.setup import _write_env_file
        _write_env_file("OPENAI_API_KEY", "test_key_456")
        
        # Verify written
        content = env_path.read_text()
        assert 'OPENAI_API_KEY="test_key_456"' in content


@pytest.mark.asyncio
async def test_tui_integration():
    """Test TUI integration (basic smoke test)."""
    from src.tui.screens.model_selector import ModelSelectorModal
    
    # Create modal
    modal = ModelSelectorModal()
    
    # Verify it has expected attributes
    assert hasattr(modal, 'BINDINGS')
    assert hasattr(modal, 'CSS')
    assert hasattr(modal, '_filtered')
    assert hasattr(modal, '_custom_mode')
    
    # Verify bindings
    assert any(b.key == 'escape' for b in modal.BINDINGS)
    assert any(b.key == 'ctrl+s' for b in modal.BINDINGS)
    
    print("✅ All model selector tests passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
