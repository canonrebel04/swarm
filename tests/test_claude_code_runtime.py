"""
Test Claude Code Runtime Adapter
"""

import pytest
import asyncio
from src.runtimes.claude_code import ClaudeCodeRuntime
from src.runtimes.base import AgentConfig, RuntimeCapabilities


class TestClaudeCodeRuntime:
    """Test the Claude Code runtime adapter"""
    
    def test_runtime_properties(self):
        """Test that Claude Code runtime has correct properties"""
        runtime = ClaudeCodeRuntime()
        
        assert runtime.runtime_name == "claude-code"
        
        capabilities = runtime.capabilities
        assert isinstance(capabilities, RuntimeCapabilities)
        assert capabilities.interactive_chat == True
        assert capabilities.headless_run == True
        assert capabilities.resume_session == True
        assert capabilities.streaming_output == True
        assert capabilities.tool_allowlist == True
        assert capabilities.parallel_safe == True
    
    def test_role_tool_policies(self):
        """Test that role tool policies are defined"""
        runtime = ClaudeCodeRuntime()
        
        # Check that all expected roles have tool policies
        expected_roles = ["scout", "developer", "builder", "tester", 
                         "reviewer", "merger", "monitor", "coordinator"]
        
        for role in expected_roles:
            assert role in runtime.ROLE_TOOL_POLICY
            policy = runtime.ROLE_TOOL_POLICY[role]
            assert "allowed" in policy
            assert "disallowed" in policy
            assert isinstance(policy["allowed"], list)
            assert isinstance(policy["disallowed"], list)
    
    def test_tool_policy_examples(self):
        """Test specific tool policy examples"""
        runtime = ClaudeCodeRuntime()
        
        # Scout should be read-only
        scout_policy = runtime.ROLE_TOOL_POLICY["scout"]
        assert "Edit" in scout_policy["disallowed"]
        assert "Write" in scout_policy["disallowed"]
        
        # Developer should have full access (default)
        dev_policy = runtime.ROLE_TOOL_POLICY["developer"]
        assert dev_policy["allowed"] == ["default"]
        
        # Merger should have git access
        merger_policy = runtime.ROLE_TOOL_POLICY["merger"]
        assert "Bash(git:*)" in merger_policy["allowed"]
        assert len(merger_policy["disallowed"]) == 0
    
    def test_build_tool_flags(self):
        """Test tool flag generation"""
        runtime = ClaudeCodeRuntime()
        
        # Test with scout role (read-only)
        scout_config = AgentConfig(
            name="scout-1",
            role="scout",
            task="Explore codebase",
            worktree_path=".swarm/worktrees",
            model="sonnet",
            runtime="claude-code",
            system_prompt_path="src/agents/definitions/scout.md"
        )
        
        flags = runtime._build_tool_flags(scout_config)
        assert "--allowedTools" in flags
        assert "--disallowedTools" in flags
        assert "Edit" in flags  # Should be in disallowed
        assert "Write" in flags  # Should be in disallowed
    
    def test_effort_for_role(self):
        """Test effort level mapping"""
        runtime = ClaudeCodeRuntime()
        
        # High effort roles
        assert runtime._effort_for_role("developer") == "high"
        assert runtime._effort_for_role("reviewer") == "high"
        assert runtime._effort_for_role("coordinator") == "high"
        
        # Low effort roles
        assert runtime._effort_for_role("scout") == "low"
        assert runtime._effort_for_role("monitor") == "low"
        
        # Medium effort roles
        assert runtime._effort_for_role("builder") == "medium"
        assert runtime._effort_for_role("tester") == "medium"
        assert runtime._effort_for_role("merger") == "medium"
    
    def test_system_prompt_building(self):
        """Test system prompt construction"""
        runtime = ClaudeCodeRuntime()
        
        config = AgentConfig(
            name="test-agent",
            role="developer",
            task="Implement feature",
            worktree_path=".swarm/worktrees",
            model="sonnet",
            runtime="claude-code",
            system_prompt_path="src/agents/definitions/developer.md"
        )
        
        prompt = runtime._build_system_prompt(config)
        
        # Should contain role contract
        assert "ROLE CONTRACT (non-negotiable)" in prompt
        assert "test-agent" in prompt
        assert "developer" in prompt
        assert "Do not self-reassign" in prompt
        assert "structured JSON summary" in prompt
    
    def test_extract_text_methods(self):
        """Test JSON line extraction methods"""
        runtime = ClaudeCodeRuntime()
        
        # Test text event
        text_line = '{"type":"text","text":"Hello world"}'
        result = runtime._extract_text("test-session", text_line)
        assert result == "Hello world"
        
        # Test tool use event
        tool_line = '{"type":"tool_use","name":"bash","input":{"command":"ls"}}'
        result = runtime._extract_text("test-session", tool_line)
        assert result.startswith("[tool] bash")
        
        # Test tool result event
        result_line = '{"type":"tool_result","content":"Success"}'
        result = runtime._extract_text("test-session", result_line)
        assert result.startswith("[result] Success")
        
        # Test system event with session_id
        system_line = '{"type":"system","session_id":"abc123"}'
        result = runtime._extract_text("test-session", system_line)
        assert result is None  # Should capture session_id, not return text
        
        # Verify session_id was captured
        assert runtime._session_ids["test-session"] == "abc123"
    
    async def test_spawn_method_signature(self):
        """Test that spawn method has correct signature"""
        runtime = ClaudeCodeRuntime()
        
        # Should accept AgentConfig and return session_id string
        import inspect
        sig = inspect.signature(runtime.spawn)
        
        assert len(sig.parameters) == 1
        assert 'config' in sig.parameters
        assert sig.parameters['config'].annotation == AgentConfig
        
        # Should be async
        assert asyncio.iscoroutinefunction(runtime.spawn)
    
    async def test_stream_output_method_signature(self):
        """Test that stream_output method has correct signature"""
        runtime = ClaudeCodeRuntime()
        
        import inspect
        sig = inspect.signature(runtime.stream_output)
        
        assert len(sig.parameters) == 1
        assert 'session_id' in sig.parameters
        assert sig.parameters['session_id'].annotation == str
        
        # Should be async generator
        assert inspect.isasyncgenfunction(runtime.stream_output)
    
    async def test_get_status_method_signature(self):
        """Test that get_status method has correct signature"""
        runtime = ClaudeCodeRuntime()
        
        import inspect
        sig = inspect.signature(runtime.get_status)
        
        assert len(sig.parameters) == 1
        assert 'session_id' in sig.parameters
        assert sig.parameters['session_id'].annotation == str
        
        # Should be async
        assert asyncio.iscoroutinefunction(runtime.get_status)
    
    async def test_kill_method_signature(self):
        """Test that kill method has correct signature"""
        runtime = ClaudeCodeRuntime()
        
        import inspect
        sig = inspect.signature(runtime.kill)
        
        assert len(sig.parameters) == 1
        assert 'session_id' in sig.parameters
        assert sig.parameters['session_id'].annotation == str
        
        # Should be async
        assert asyncio.iscoroutinefunction(runtime.kill)


class TestClaudeCodeIntegration:
    """Test Claude Code integration with the runtime registry"""
    
    def test_runtime_registration(self):
        """Test that Claude Code runtime is properly registered"""
        from src.runtimes.registry import registry
        
        # Should be registered
        assert registry.has_runtime("claude-code")
        
        # Should be able to get the runtime class
        runtime_class = registry.get("claude-code")
        assert runtime_class is not None
        assert runtime_class().runtime_name == "claude-code"
        
        # Should be in available list
        available_runtimes = registry.list_available()
        assert "claude-code" in available_runtimes
    
    def test_runtime_capabilities_exposed(self):
        """Test that runtime capabilities are accessible through registry"""
        from src.runtimes.registry import registry
        
        runtime_class = registry.get("claude-code")
        runtime_instance = runtime_class()
        
        capabilities = runtime_instance.capabilities
        
        # Verify key capabilities
        assert capabilities.interactive_chat == True
        assert capabilities.headless_run == True
        assert capabilities.resume_session == True
        assert capabilities.tool_allowlist == True
