"""
Integration tests for provider implementations.

These tests make real API calls to LLM providers and require valid API keys.
They are excluded from the default test run. To run them:

    # Run only integration tests
    pytest -m integration
    
    # Run all tests including integration (requires API keys)
    pytest -m ""
    
    # Run integration tests for a specific provider
    pytest -m integration tests/integration/test_providers_integration.py::TestOpenAIProviderIntegration
"""

import os
import pytest

from resumeforge.providers import (
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    GroqProvider,
    create_provider_from_alias,
)
from resumeforge.config import load_config
from resumeforge.exceptions import ProviderError


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestOpenAIProviderIntegration:
    """Integration tests for OpenAIProvider (requires OPENAI_API_KEY)."""

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY environment variable"
    )
    def test_openai_generate_text(self):
        """Test real API call to OpenAI."""
        api_key = os.environ["OPENAI_API_KEY"]
        provider = OpenAIProvider(api_key=api_key, model="gpt-4o-mini")
        
        response = provider.generate_text(
            prompt="Say 'Hello, World!' in one sentence.",
            temperature=0.0,
            max_tokens=50
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        assert "Hello" in response or "hello" in response.lower()

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY environment variable"
    )
    def test_openai_count_tokens_accuracy(self):
        """Test token counting accuracy with known text."""
        api_key = os.environ["OPENAI_API_KEY"]
        provider = OpenAIProvider(api_key=api_key, model="gpt-4o-mini")
        
        text = "Hello, world!"
        count = provider.count_tokens(text)
        
        assert count > 0
        assert count <= len(text)  # Tokens should be <= characters for simple text


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestAnthropicProviderIntegration:
    """Integration tests for AnthropicProvider (requires ANTHROPIC_API_KEY)."""

    @pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="Requires ANTHROPIC_API_KEY environment variable"
    )
    def test_anthropic_generate_text(self):
        """Test real API call to Anthropic."""
        api_key = os.environ["ANTHROPIC_API_KEY"]
        provider = AnthropicProvider(api_key=api_key, model="claude-3-5-sonnet-20241022")
        
        response = provider.generate_text(
            prompt="Say 'Hello, World!' in one sentence.",
            system_prompt="You are a helpful assistant.",
            temperature=0.0,
            max_tokens=50
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        assert "Hello" in response or "hello" in response.lower()


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestGoogleProviderIntegration:
    """Integration tests for GoogleProvider (requires GOOGLE_API_KEY)."""

    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY"),
        reason="Requires GOOGLE_API_KEY environment variable"
    )
    def test_google_generate_text(self):
        """Test real API call to Google AI."""
        api_key = os.environ["GOOGLE_API_KEY"]
        provider = GoogleProvider(api_key=api_key, model="gemini-1.5-flash")
        
        response = provider.generate_text(
            prompt="Say 'Hello, World!' in one sentence.",
            system_prompt="You are a helpful assistant.",
            temperature=0.0,
            max_tokens=50
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        assert "Hello" in response or "hello" in response.lower()


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestGroqProviderIntegration:
    """Integration tests for GroqProvider (requires GROQ_API_KEY)."""

    @pytest.mark.skipif(
        not os.getenv("GROQ_API_KEY"),
        reason="Requires GROQ_API_KEY environment variable"
    )
    def test_groq_generate_text(self):
        """Test real API call to Groq."""
        api_key = os.environ["GROQ_API_KEY"]
        provider = GroqProvider(api_key=api_key, model="llama-3.1-70b-versatile")
        
        response = provider.generate_text(
            prompt="Say 'Hello, World!' in one sentence.",
            system_prompt="You are a helpful assistant.",
            temperature=0.0,
            max_tokens=50
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        assert "Hello" in response or "hello" in response.lower()


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestProviderFactoryIntegration:
    """Integration tests for provider factory (requires API keys)."""

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY environment variable"
    )
    def test_create_provider_from_alias_openai(self):
        """Test creating OpenAI provider from alias with real API key."""
        config = load_config("config.yaml")
        provider = create_provider_from_alias("writer_default", config)
        
        assert isinstance(provider, OpenAIProvider)
        
        # Make a real API call
        response = provider.generate_text(
            prompt="Say 'Test'",
            temperature=0.0,
            max_tokens=10
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
