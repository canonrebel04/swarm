import pytest
import json
from src.messaging.module_bindings.insert_event_reducer import _decode_args

def test_decode_args_valid_json():
    """Test _decode_args with a valid JSON string."""
    args = '{"event_id": 1, "sender": "test", "payload": "hello", "timestamp": 123456789}'
    expected = {"event_id": 1, "sender": "test", "payload": "hello", "timestamp": 123456789}
    assert _decode_args(args) == expected

def test_decode_args_invalid_json():
    """Test _decode_args with an invalid JSON string."""
    args = '{"event_id": 1, "sender": "test", "payload": "hello", "timestamp": 123456789' # Missing closing brace
    with pytest.raises(json.JSONDecodeError):
        _decode_args(args)

def test_decode_args_none():
    """Test _decode_args with None."""
    with pytest.raises(TypeError):
        _decode_args(None)

def test_decode_args_non_string():
    """Test _decode_args with a non-string input."""
    with pytest.raises(TypeError):
        _decode_args(123)
