"""Groq provider implementation."""

from tenacity import (
    Retrying,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from groq import Groq, GroqError

from resumeforge.exceptions import ProviderError
from resumeforge.providers.base import BaseProvider, DEFAULT_MAX_RETRIES

# Constants
GROQ_TIMEOUT_SECONDS = 30  # Shorter timeout for Groq - fast inference


class GroqProvider(BaseProvider):
    """Groq provider using fast inference models."""
    
    def __init__(self, api_key: str, model: str = "llama-3.1-70b-versatile", timeout_seconds: int = GROQ_TIMEOUT_SECONDS, max_retries: int = DEFAULT_MAX_RETRIES):
        """
        Initialize Groq provider.
        
        Args:
            api_key: Groq API key
            model: Model identifier (e.g., "llama-3.1-70b-versatile")
            timeout_seconds: Request timeout (shorter for Groq - fast inference)
            max_retries: Maximum retries
        """
        super().__init__(api_key, model, timeout_seconds, max_retries)
        self.client = Groq(api_key=api_key, timeout=timeout_seconds)
    
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
        Generate text completion using Groq API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments
            
        Returns:
            Generated text response
            
        Raises:
            ProviderError: If API call fails
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Use Retrying with instance's max_retries for configuration-driven retry behavior
        # max_retries is the number of retries, so total attempts = max_retries + 1
        # This preserves the original behavior of 3 total attempts (1 initial + 2 retries) when max_retries=2
        retry_strategy = Retrying(
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(GroqError),
            reraise=True
        )
        
        try:
            self.logger.info(
                "generating_text",
                temperature=temperature,
                max_tokens=max_tokens,
                prompt_length=len(prompt),
                system_prompt_length=len(system_prompt) if system_prompt else 0,
                max_retries=self.max_retries
            )
            
            # Execute API call with retry strategy
            for attempt in retry_strategy:
                with attempt:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
                    
                    result = response.choices[0].message.content
                    if not result:
                        raise ProviderError("Groq returned empty response")
                    
                    self.logger.info("text_generated", response_length=len(result))
                    return result
            
        except ProviderError:
            # Re-raise ProviderError without wrapping (e.g., from validation checks)
            raise
        except GroqError as e:
            error_str = str(e)
            self.logger.error("api_error", error=error_str, error_type=type(e).__name__)
            
            if "429" in error_str or "rate" in error_str.lower():
                raise ProviderError(f"Groq rate limit exceeded: {e}") from e
            elif "timeout" in error_str.lower():
                raise ProviderError(f"Groq request timeout: {e}") from e
            else:
                raise ProviderError(f"Groq API error: {e}") from e
        except Exception as e:
            self.logger.error("unexpected_error", error=str(e), error_type=type(e).__name__)
            raise ProviderError(f"Unexpected error calling Groq: {e}") from e
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Groq models use ~4 characters per token on average.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated number of tokens
        """
        # Rough estimate: ~4 characters per token
        return len(text) // 4
