"""Anthropic provider implementation."""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from anthropic import Anthropic, APIError, APITimeoutError, RateLimitError

from resumeforge.exceptions import ProviderError
from resumeforge.providers.base import BaseProvider


class AnthropicProvider(BaseProvider):
    """Anthropic provider using Claude models."""
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514", timeout_seconds: int = 45, max_retries: int = 2):
        """
        Initialize Anthropic provider.
        
        Args:
            api_key: Anthropic API key
            model: Model identifier (e.g., "claude-sonnet-4-20250514")
            timeout_seconds: Request timeout
            max_retries: Maximum retries
        """
        super().__init__(api_key, model, timeout_seconds, max_retries)
        self.client = Anthropic(api_key=api_key, timeout=timeout_seconds)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        reraise=True
    )
    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs
    ) -> str:
        """
        Generate text completion using Anthropic API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt (Anthropic requires this)
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments
            
        Returns:
            Generated text response
            
        Raises:
            ProviderError: If API call fails
        """
        try:
            self.logger.info(
                "generating_text",
                temperature=temperature,
                max_tokens=max_tokens,
                prompt_length=len(prompt),
                system_prompt_length=len(system_prompt) if system_prompt else 0
            )
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                **kwargs
            )
            
            if not response.content or len(response.content) == 0:
                raise ProviderError("Anthropic returned empty response")
            
            result = response.content[0].text
            if not result:
                raise ProviderError("Anthropic returned empty text")
            
            self.logger.info("text_generated", response_length=len(result))
            return result
            
        except RateLimitError as e:
            self.logger.error("rate_limit_exceeded", error=str(e))
            raise ProviderError(f"Anthropic rate limit exceeded: {e}") from e
        except APITimeoutError as e:
            self.logger.error("timeout", error=str(e))
            raise ProviderError(f"Anthropic request timeout: {e}") from e
        except APIError as e:
            self.logger.error("api_error", error=str(e), error_type=type(e).__name__)
            raise ProviderError(f"Anthropic API error: {e}") from e
        except Exception as e:
            self.logger.error("unexpected_error", error=str(e), error_type=type(e).__name__)
            raise ProviderError(f"Unexpected error calling Anthropic: {e}") from e
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Anthropic doesn't expose tokenizer, so we estimate at ~4 chars/token.
        For more accuracy, could use Anthropic's count_tokens endpoint if available.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated number of tokens
        """
        # Rough estimate: Anthropic uses ~4 characters per token on average
        return len(text) // 4
