"""Test secure input functionality."""
import pytest
from unittest.mock import patch
from src.cli.setup import _secure_input


def test_secure_input_with_getpass():
    """Test secure input using getpass."""
    with patch('getpass.getpass', return_value='test_key_123'):
        result = _secure_input("Enter API key: ")
        assert result == 'test_key_123'


def test_secure_input_with_fallback():
    """Test secure input fallback when getpass fails."""
    with patch('getpass.getpass', side_effect=Exception('getpass failed')):
        with patch('builtins.input', return_value='test_key_456'):
            result = _secure_input("Enter API key: ")
            assert result == 'test_key_456'


def test_secure_input_empty():
    """Test secure input with empty result."""
    with patch('getpass.getpass', return_value=''):
        result = _secure_input("Enter API key: ")
        assert result == ''


def test_secure_input_strips_whitespace():
    """Test secure input strips whitespace."""
    with patch('getpass.getpass', return_value='  test_key_789  '):
        result = _secure_input("Enter API key: ")
        assert result == 'test_key_789'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
