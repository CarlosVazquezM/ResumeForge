"""Unit tests for provider implementations."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock

from resumeforge.providers import (
    BaseProvider,
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    GroqProvider,
    create_provider,
    create_provider_from_alias,
    resolve_model_alias,
)
from resumeforge.config import load_config
from resumeforge.exceptions import ConfigError, ProviderError


class TestBaseProvider:
    """Tests for BaseProvider interface."""

    def test_base_provider_is_abstract(self):
        """Test that BaseProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseProvider(api_key="test", model="test")


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_openai_provider_init(self):
        """Test OpenAIProvider initialization."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4o")
        assert provider.model == "gpt-4o"
        assert provider.api_key == "test-key"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_count_tokens(self):
        """Test token counting with tiktoken."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4o")
        # Simple test - should return some token count
        count = provider.count_tokens("Hello world")
        assert isinstance(count, int)
        assert count > 0


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_anthropic_provider_init(self):
        """Test AnthropicProvider initialization."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")
        assert provider.model == "claude-sonnet-4-20250514"
        assert provider.api_key == "test-key"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_count_tokens_estimation(self):
        """Test token counting estimation."""
        provider = AnthropicProvider(api_key="test-key")
        text = "Hello world " * 10  # 120 characters
        count = provider.count_tokens(text)
        assert count == 30  # 120 // 4 = 30


class TestProviderFactory:
    """Tests for provider factory functions."""

    def test_resolve_model_alias(self):
        """Test resolving model alias to provider and model."""
        config = load_config("config.yaml")
        provider_name, model_id = resolve_model_alias("writer_default", config)
        assert provider_name == "openai"
        assert model_id == "gpt-4o"

    def test_resolve_model_alias_not_found(self):
        """Test that invalid alias raises ConfigError."""
        config = load_config("config.yaml")
        with pytest.raises(ConfigError) as exc_info:
            resolve_model_alias("nonexistent_alias", config)
        assert "not found" in str(exc_info.value).lower()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_create_provider(self):
        """Test creating provider from provider name and model."""
        config = load_config("config.yaml")
        provider = create_provider("openai", "gpt-4o", config)
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4o"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_create_provider_from_alias(self):
        """Test creating provider from model alias."""
        config = load_config("config.yaml")
        provider = create_provider_from_alias("writer_default", config)
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4o"

    @patch.dict(os.environ, {}, clear=True)
    def test_create_provider_missing_api_key(self):
        """Test that missing API key raises ConfigError."""
        config = load_config("config.yaml")
        with pytest.raises(ConfigError) as exc_info:
            create_provider("openai", "gpt-4o", config)
        assert "missing api key" in str(exc_info.value).lower()

    def test_create_provider_unknown_provider(self):
        """Test that unknown provider raises ConfigError."""
        config = load_config("config.yaml")
        with pytest.raises(ConfigError) as exc_info:
            create_provider("unknown_provider", "model", config)
        assert "unknown provider" in str(exc_info.value).lower()


class TestProviderErrorHandling:
    """Tests for provider error handling."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("resumeforge.providers.openai_provider.OpenAI")
    def test_openai_rate_limit_error(self, mock_openai_class):
        """Test that rate limit errors are converted to ProviderError."""
        from openai import RateLimitError
        
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RateLimitError(
            message="Rate limit exceeded",
            response=Mock(status_code=429),
            body={}
        )
        
        provider = OpenAIProvider(api_key="test-key", model="gpt-4o")
        
        with pytest.raises(ProviderError) as exc_info:
            provider.generate_text("test prompt")
        assert "rate limit" in str(exc_info.value).lower()
