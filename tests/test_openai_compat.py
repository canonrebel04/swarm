import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Mock missing dependencies to allow src imports in restricted environments
for module_name in ["aiohttp", "paramiko", "yaml", "websockets", "docker"]:
    if module_name not in sys.modules:
        sys.modules[module_name] = MagicMock()

from src.utils.openai_compat import get_api_key

def test_get_api_key_from_env_present():
    with patch.dict(os.environ, {"MY_TEST_KEY": "test_env_val"}):
        assert get_api_key("MY_TEST_KEY") == "test_env_val"

def test_get_api_key_from_env_file_missing_env_var():
    with patch.dict(os.environ, clear=True):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value='MY_TEST_KEY="test_file_val"'):
                assert get_api_key("MY_TEST_KEY") == "test_file_val"

def test_get_api_key_missing_everywhere():
    with patch.dict(os.environ, clear=True):
        with patch.object(Path, "exists", return_value=False):
            assert get_api_key("MY_TEST_KEY") is None

def test_get_api_key_env_file_no_matching_key():
    with patch.dict(os.environ, clear=True):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value='OTHER_KEY="test_file_val"'):
                assert get_api_key("MY_TEST_KEY") is None

def test_get_api_key_priority():
    """Verify that environment variables take precedence over .env file entries."""
    with patch.dict(os.environ, {"MY_TEST_KEY": "env_val"}):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value='MY_TEST_KEY="file_val"'):
                # Should prioritize environment variable
                assert get_api_key("MY_TEST_KEY") == "env_val"

def test_get_api_key_env_file_parsing_edge_cases():
    """Cover single/double quotes, and various whitespace/format scenarios in .env files."""
    cases = [
        ('MY_KEY=val', 'val'),
        ('MY_KEY="val"', 'val'),
        ("MY_KEY='val'", "val"),
        ('MY_KEY = val ', 'val'),
        ('MY_KEY=" val "', ' val '),
        ('MY_KEY= "val" ', 'val'),
    ]
    for content, expected in cases:
        with patch.dict(os.environ, clear=True):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "read_text", return_value=content):
                    assert get_api_key("MY_KEY") == expected

def test_get_api_key_empty_value():
    """Ensure empty strings in env or .env are handled correctly."""
    # Empty in os.environ - should fall through to .env (if exists) or return None
    with patch.dict(os.environ, {"MY_TEST_KEY": ""}):
        with patch.object(Path, "exists", return_value=False):
            assert get_api_key("MY_TEST_KEY") is None

    # Empty in .env file
    with patch.dict(os.environ, clear=True):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value='MY_TEST_KEY='):
                assert get_api_key("MY_TEST_KEY") == ""
