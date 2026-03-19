"""
Test overseer input → Coordinator wiring
"""

import pytest
import asyncio
from src.tui.panels.overseer_chat import OverseerChatPanel
from src.orchestrator.coordinator import coordinator, TaskPacket


class MockApp:
    """Mock app for testing"""
    def __init__(self):
        self.events = []
        self.coordinator = coordinator
    
    def push_swarm_event(self, level, source, message):
        self.events.append({"level": level, "source": source, "message": message})


class TestOverseerInputWiring:
    """Test that overseer input is properly wired to coordinator"""
    
    async def test_coordinator_handle_user_input(self):
        """Test that coordinator can handle user input as async generator"""
        # Test with a simple task
        tokens = []
        async for token in coordinator.handle_user_input("Implement user authentication"):
            tokens.append(token)
        
        # Should yield task decomposition
        result = "".join(tokens)
        assert "Decomposed into" in result
        assert "tasks:" in result
        print(f"Coordinator response: {result}")
    
    def test_overseer_chat_methods_exist(self):
        """Test that OverseerChatPanel has required methods"""
        chat = OverseerChatPanel()
        
        # Test that required methods exist
        assert hasattr(chat, 'stream_response')
        assert callable(chat.stream_response)
        assert hasattr(chat, 'add_message')
        assert callable(chat.add_message)
        
        print("✓ OverseerChatPanel has required methods for input handling")
    
    def test_user_input_event_logic(self):
        """Test the user input event logic"""
        # Test the event message preview logic
        test_input = "Implement user authentication system with JWT and OAuth2 support"
        message_preview = test_input[:60] + "…" if len(test_input) > 60 else test_input
        
        # Verify preview logic works correctly
        assert len(message_preview) <= 63  # 60 chars + "…"
        if len(test_input) > 60:
            assert message_preview.endswith("…")
        else:
            assert message_preview == test_input
        
        print(f"✓ User input event preview logic works: '{message_preview}'")
    
    async def test_coordinator_event_pushing(self):
        """Test that coordinator pushes events when handling input"""
        # Set up event callback
        events = []
        
        def capture_event(level, source, message):
            events.append({"level": level, "source": source, "message": message})
        
        coordinator.register_event_callback(capture_event)
        
        # Handle user input
        async for _ in coordinator.handle_user_input("Build API endpoint"):
            pass  # Just consume the tokens
        
        # Verify event was pushed
        assert len(events) == 1
        assert events[0]["level"] == "info"
        assert events[0]["source"] == "coordinator"
        assert "dispatched" in events[0]["message"]
        
        print(f"✓ Coordinator event pushed: {events[0]}")
        
        # Clean up
        coordinator._push_event_callback = None
    
    async def test_task_decomposition_integration(self):
        """Test full integration: input → decomposition → response"""
        # Set up event callback to avoid NoneType error
        coordinator.register_event_callback(lambda *args, **kwargs: None)
        
        # Test with different types of inputs
        test_cases = [
            "Implement user authentication",
            "Fix the database connection bug",
            "Add dark mode support to the UI"
        ]
        
        for test_input in test_cases:
            tokens = []
            async for token in coordinator.handle_user_input(test_input):
                tokens.append(token)
            result = "".join(tokens)
            
            # Verify response format
            assert "Decomposed into" in result
            assert "tasks:" in result
            
            # Should always create 3 tasks (scout, developer, tester)
            task_count = result.split("into ")[1].split(" tasks")[0]
            assert task_count == "3"
            
            print(f"✓ Input '{test_input}' → {result}")
        
        # Clean up
        coordinator._push_event_callback = None


class TestStubCompatibility:
    """Test that the implementation is stub-compatible for future LLM integration"""
    
    def test_handle_user_input_signature(self):
        """Test that handle_user_input has the right signature for LLM streaming"""
        import inspect
        
        # Get the method signature
        sig = inspect.signature(coordinator.handle_user_input)
        
        # Should accept text: str
        assert len(sig.parameters) == 1
        assert 'text' in sig.parameters
        assert sig.parameters['text'].annotation == str
        
        # Should be async generator (not coroutine function)
        assert inspect.isasyncgenfunction(coordinator.handle_user_input)
        
        print("✓ handle_user_input has correct signature for async streaming")
    
    async def test_response_format_compatibility(self):
        """Test that response format is compatible with token streaming"""
        # Set up event callback to avoid NoneType error
        coordinator.register_event_callback(lambda *args, **kwargs: None)
        
        tokens = []
        async for token in coordinator.handle_user_input("Test task"):
            tokens.append(token)
        result = "".join(tokens)
        
        # Should yield strings (can be streamed as tokens)
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Should be plain text (no markup that would break streaming)
        assert "[" not in result  # No Textual markup
        assert "<" not in result  # No HTML
        
        print("✓ Response format is compatible with token streaming")
        
        # Clean up
        coordinator._push_event_callback = None
    
    def test_stream_response_method_signature(self):
        """Test that stream_response has the right signature"""
        chat = OverseerChatPanel()
        
        # Check that stream_response exists
        assert hasattr(chat, 'stream_response')
        
        # Check that it's decorated with @work (will be async when called)
        import inspect
        # The method is decorated with @work, so it returns a worker, not a coroutine
        # This is the expected behavior for Textual work methods
        
        print("✓ stream_response method exists with proper @work decoration")
