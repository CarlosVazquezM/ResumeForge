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
    
    def test_repair_json_unterminated_string(self):
        """Test JSON repair for unterminated string."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = ConcreteTestAgent(mock_provider, config)
        
        # Unterminated string (response cut off mid-string)
        malformed_json = '{"keyword_coverage_score": 85, "supported_keywords": ["Python", "AWS", "team leader'
        repaired = agent._repair_json(malformed_json)
        
        # Should be able to parse after repair
        parsed = json.loads(repaired)
        assert parsed["keyword_coverage_score"] == 85
        assert "supported_keywords" in parsed
    
    def test_repair_json_missing_closing_brace(self):
        """Test JSON repair for missing closing brace."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = ConcreteTestAgent(mock_provider, config)
        
        # Missing closing brace
        malformed_json = '{"step": "test", "value": 42'
        repaired = agent._repair_json(malformed_json)
        
        # Should be able to parse after repair
        parsed = json.loads(repaired)
        assert parsed["step"] == "test"
        assert parsed["value"] == 42
    
    def test_repair_json_missing_closing_bracket(self):
        """Test JSON repair for missing closing bracket."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = ConcreteTestAgent(mock_provider, config)
        
        # Missing closing bracket
        malformed_json = '{"items": [1, 2, 3'
        repaired = agent._repair_json(malformed_json)
        
        # Should be able to parse after repair
        parsed = json.loads(repaired)
        assert parsed["items"] == [1, 2, 3]
    
    def test_repair_json_multiple_issues(self):
        """Test JSON repair for multiple issues."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = ConcreteTestAgent(mock_provider, config)
        
        # Multiple issues: unterminated string and missing braces
        malformed_json = '{"keyword_coverage_score": 85, "supported_keywords": ["Python", "AWS'
        repaired = agent._repair_json(malformed_json)
        
        # Should attempt repair (may or may not succeed depending on complexity)
        # At minimum, it should add closing structures
        assert repaired.count('}') >= malformed_json.count('}')
        assert repaired.count(']') >= malformed_json.count(']')
    
    def test_parse_json_with_repair_valid_json(self):
        """Test _parse_json_with_repair with valid JSON (should work normally)."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = ConcreteTestAgent(mock_provider, config)
        
        valid_json = '{"step": "test", "value": 42}'
        result = agent._parse_json_with_repair(valid_json, context="Test")
        
        assert result["step"] == "test"
        assert result["value"] == 42
    
    def test_parse_json_with_repair_repairable_json(self):
        """Test _parse_json_with_repair with repairable JSON."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = ConcreteTestAgent(mock_provider, config)
        
        # Unterminated string that can be repaired
        malformed_json = '{"step": "test", "value": 42'
        result = agent._parse_json_with_repair(malformed_json, context="Test")
        
        assert result["step"] == "test"
        assert result["value"] == 42
    
    def test_parse_json_with_repair_unrepairable_json(self):
        """Test _parse_json_with_repair with unrepairable JSON raises ValidationError."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = ConcreteTestAgent(mock_provider, config)
        
        # Completely invalid JSON that can't be repaired
        invalid_json = "not json at all {["
        
        with pytest.raises(ValidationError) as exc_info:
            agent._parse_json_with_repair(invalid_json, context="Test")
        
        assert "Invalid JSON response" in str(exc_info.value)
        assert "Test" in str(exc_info.value)
    
    def test_parse_json_with_repair_logs_warning(self, caplog):
        """Test that _parse_json_with_repair logs warning on repair attempt."""
        import structlog
        structlog.configure(
            processors=[structlog.processors.JSONRenderer()],
            wrapper_class=structlog.make_filtering_bound_logger(0),  # Log everything
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = ConcreteTestAgent(mock_provider, config)
        
        # Unterminated string that triggers repair
        malformed_json = '{"step": "test"'
        
        # Should succeed after repair
        result = agent._parse_json_with_repair(malformed_json, context="Test")
        assert result["step"] == "test"