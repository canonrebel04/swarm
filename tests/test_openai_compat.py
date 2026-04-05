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
