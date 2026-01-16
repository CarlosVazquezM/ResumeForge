"""OpenAI provider implementation."""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

from openai import OpenAI, APIError, APITimeoutError, RateLimitError
import tiktoken

from resumeforge.exceptions import ProviderError
from resumeforge.providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    """OpenAI provider using GPT models."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o", timeout_seconds: int = 45, max_retries: int = 2):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            model: Model identifier (e.g., "gpt-4o")
            timeout_seconds: Request timeout
            max_retries: Maximum retries
        """
        super().__init__(api_key, model, timeout_seconds, max_retries)
        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base for unknown models
            self.encoding = tiktoken.get_encoding("cl100k_base")
            self.logger.warning(f"Unknown model {model}, using cl100k_base encoding")
    
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
        Generate text completion using OpenAI API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments (e.g., response_format)
            
        Returns:
            Generated text response
            
        Raises:
            ProviderError: If API call fails
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            self.logger.info(
                "generating_text",
                temperature=temperature,
                max_tokens=max_tokens,
                prompt_length=len(prompt),
                system_prompt_length=len(system_prompt) if system_prompt else 0
            )
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            result = response.choices[0].message.content
            if not result:
                raise ProviderError("OpenAI returned empty response")
            
            self.logger.info("text_generated", response_length=len(result))
            return result
            
        except RateLimitError as e:
            self.logger.error("rate_limit_exceeded", error=str(e))
            raise ProviderError(f"OpenAI rate limit exceeded: {e}") from e
        except APITimeoutError as e:
            self.logger.error("timeout", error=str(e))
            raise ProviderError(f"OpenAI request timeout: {e}") from e
        except APIError as e:
            self.logger.error("api_error", error=str(e), error_type=type(e).__name__)
            raise ProviderError(f"OpenAI API error: {e}") from e
        except Exception as e:
            self.logger.error("unexpected_error", error=str(e), error_type=type(e).__name__)
            raise ProviderError(f"Unexpected error calling OpenAI: {e}") from e
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))
