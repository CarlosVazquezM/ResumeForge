"""Unit tests for Base Agent implementation."""

import json
import pytest
from unittest.mock import MagicMock

from resumeforge.agents.base import BaseAgent
from resumeforge.exceptions import ProviderError, ValidationError
from resumeforge.schemas.blackboard import Blackboard
from tests.fixtures import create_mock_provider, create_sample_blackboard


class ConcreteTestAgent(BaseAgent):
    """Concrete agent implementation for testing BaseAgent."""
    
    def get_system_prompt(self) -> str:
        return "You are a test agent."
    
    def build_user_prompt(self, blackboard: Blackboard) -> str:
        return f"Test prompt for {blackboard.inputs.target_title}"
    
    def parse_response(self, response: str, blackboard: Blackboard) -> Blackboard:
        data = json.loads(response)
        blackboard.current_step = data.get("step", "test_complete")
        return blackboard


class TestBaseAgent:
    """Tests for BaseAgent abstract class."""
    
    def test_base_agent_is_abstract(self):
        """Test that BaseAgent cannot be instantiated directly."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        
        with pytest.raises(TypeError):
            BaseAgent(mock_provider, config)
    
    def test_concrete_agent_initialization(self):
        """Test that concrete agent can be initialized."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        
        agent = ConcreteTestAgent(mock_provider, config)
        assert agent.provider == mock_provider
        assert agent.temperature == 0.3
        assert agent.max_tokens == 4096
    
    def test_execute_flow(self):
        """Test complete execute() flow with mocked provider."""
        response_json = '{"step": "test_complete"}'
        mock_provider = create_mock_provider(response=response_json)
        config = {"temperature": 0.3, "max_tokens": 4096}
        
        agent = ConcreteTestAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        result = agent.execute(blackboard)
        
        assert result.current_step == "test_complete"
        mock_provider.generate_text.assert_called_once()
        mock_provider.count_tokens.assert_called()
    
    def test_extract_json_from_markdown_code_block(self):
        """Test JSON extraction from markdown code blocks."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = ConcreteTestAgent(mock_provider, config)
        
        # Test with ```json wrapper
        text_with_json = '```json\n{"step": "test"}\n```'
        result = agent._extract_json(text_with_json)
        assert result == '{"step": "test"}'
        
        # Test with plain ``` wrapper
        text_with_plain = '```\n{"step": "test"}\n```'
        result = agent._extract_json(text_with_plain)
        assert result == '{"step": "test"}'
    
    def test_extract_json_plain(self):
        """Test JSON extraction from plain JSON."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = ConcreteTestAgent(mock_provider, config)
        
        plain_json = '{"step": "test"}'
        result = agent._extract_json(plain_json)
        assert result == '{"step": "test"}'
    
    def test_extract_json_no_markdown(self):
        """Test JSON without markdown wrappers."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = ConcreteTestAgent(mock_provider, config)
        
        json_text = '{"step": "test"}'
        result = agent._extract_json(json_text)
        assert result == '{"step": "test"}'
    
    def test_provider_error_handling(self):
        """Test ProviderError raised on LLM failures."""
        mock_provider = create_mock_provider()
        mock_provider.generate_text.side_effect = Exception("API error")
        config = {"temperature": 0.3, "max_tokens": 4096}
        
        agent = ConcreteTestAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        with pytest.raises(ProviderError) as exc_info:
            agent.execute(blackboard)
        
        assert "Failed to execute" in str(exc_info.value)
        assert "ConcreteTestAgent" in str(exc_info.value)
    
    def test_validation_error_on_invalid_json(self):
        """Test ValidationError on JSON parse failures."""
        invalid_json = "not valid json"
        mock_provider = create_mock_provider(response=invalid_json)
        config = {"temperature": 0.3, "max_tokens": 4096}
        
        agent = ConcreteTestAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        with pytest.raises(ValidationError) as exc_info:
            agent.execute(blackboard)
        
        assert "Invalid JSON response" in str(exc_info.value)
    
    def test_token_counting(self):
        """Test token counting is logged."""
        response_json = '{"step": "test"}'
        mock_provider = create_mock_provider(response=response_json, token_count=150)
        config = {"temperature": 0.3, "max_tokens": 4096}
        
        agent = ConcreteTestAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        agent.execute(blackboard)
        
        # Verify count_tokens was called
        assert mock_provider.count_tokens.called
    
    def test_json_mode_openai(self):
        """Test JSON mode enabled for OpenAI models."""
        response_json = '{"step": "test"}'
        mock_provider = create_mock_provider(model="gpt-4o", response=response_json)
        config = {"temperature": 0.3, "max_tokens": 4096}
        
        agent = ConcreteTestAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        agent.execute(blackboard)
        
        # Check that response_format was passed
        call_kwargs = mock_provider.generate_text.call_args[1]
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}
    
    def test_json_mode_not_enabled_for_non_openai(self):
        """Test JSON mode not enabled for non-OpenAI models."""
        response_json = '{"step": "test"}'
        mock_provider = create_mock_provider(model="claude-sonnet-4", response=response_json)
        config = {"temperature": 0.3, "max_tokens": 4096}
        
        agent = ConcreteTestAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        agent.execute(blackboard)
        
        # Check that response_format was NOT passed
        call_kwargs = mock_provider.generate_text.call_args[1]
        assert "response_format" not in call_kwargs
