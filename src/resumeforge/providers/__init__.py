"""LLM provider abstraction layer."""

import os
from typing import TYPE_CHECKING

from resumeforge.exceptions import ConfigError, ProviderError

if TYPE_CHECKING:
    from resumeforge.providers.base import BaseProvider
    from resumeforge.config import Config

from resumeforge.providers.anthropic_provider import AnthropicProvider
from resumeforge.providers.base import BaseProvider
from resumeforge.providers.google_provider import GoogleProvider
from resumeforge.providers.groq_provider import GroqProvider
from resumeforge.providers.openai_provider import OpenAIProvider

__all__ = [
    "BaseProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleProvider",
    "GroqProvider",
    "create_provider",
    "resolve_model_alias",
]


def resolve_model_alias(model_alias: str, config: "Config") -> tuple[str, str]:
    """
    Resolve a model alias to provider name and model ID.
    
    Args:
        model_alias: Model alias from config (e.g., "writer_default")
        config: Configuration object
        
    Returns:
        Tuple of (provider_name, model_id)
        
    Raises:
        ConfigError: If alias not found
    """
    if model_alias not in config.models:
        raise ConfigError(f"Model alias '{model_alias}' not found in configuration")
    
    model_config = config.models[model_alias]
    provider_name = model_config.get("provider")
    model_id = model_config.get("model")
    
    if not provider_name or not model_id:
        raise ConfigError(f"Invalid model configuration for alias '{model_alias}'")
    
    return provider_name, model_id


def create_provider(provider_name: str, model: str, config: "Config") -> "BaseProvider":
    """
    Create a provider instance from configuration.
    
    Args:
        provider_name: Provider name (e.g., "openai", "anthropic")
        model: Model identifier
        config: Configuration object
        
    Returns:
        Provider instance
        
    Raises:
        ConfigError: If provider not found or API key missing
        ProviderError: If provider initialization fails
    """
    # Validate provider name first
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
        "groq": GroqProvider,
    }
    
    if provider_name not in providers:
        raise ConfigError(f"Unknown provider: {provider_name}")
    
    # Get provider configuration
    provider_config = config.providers.get(provider_name, {})
    timeout_seconds = provider_config.get("timeout_seconds", 45)
    max_retries = provider_config.get("max_retries", 2)
    
    # Get API key from environment
    api_key_env_var = f"{provider_name.upper()}_API_KEY"
    api_key = os.environ.get(api_key_env_var)
    
    if not api_key:
        raise ConfigError(
            f"Missing API key for {provider_name}. "
            f"Set {api_key_env_var} environment variable."
        )
    
    try:
        provider_class = providers[provider_name]
        return provider_class(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries
        )
    except Exception as e:
        raise ProviderError(f"Failed to initialize {provider_name} provider: {e}") from e


def create_provider_from_alias(model_alias: str, config: "Config") -> "BaseProvider":
    """
    Create a provider instance from a model alias.
    
    This is the recommended way to create providers as it resolves
    the alias to the correct provider and model.
    
    Args:
        model_alias: Model alias (e.g., "writer_default")
        config: Configuration object
        
    Returns:
        Provider instance configured with the model from the alias
        
    Raises:
        ConfigError: If alias not found or provider configuration invalid
        ProviderError: If provider initialization fails
    """
    provider_name, model_id = resolve_model_alias(model_alias, config)
    return create_provider(provider_name, model_id, config)
