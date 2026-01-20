"""Google AI provider implementation."""

from tenacity import (
    Retrying,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from google import genai
from google.genai import types

from resumeforge.exceptions import ProviderError
from resumeforge.providers.base import BaseProvider, DEFAULT_TIMEOUT_SECONDS, DEFAULT_MAX_RETRIES

class GoogleProvider(BaseProvider):
    """Google AI provider using Gemini models."""
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS, max_retries: int = DEFAULT_MAX_RETRIES):
        """
        Initialize Google AI provider.
        
        Args:
            api_key: Google AI API key
            model: Model identifier (e.g., "gemini-1.5-flash")
            timeout_seconds: Request timeout
            max_retries: Maximum retries
        """
        super().__init__(api_key, model, timeout_seconds, max_retries)
        self.client = genai.Client(api_key=api_key)
    
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
        Generate text completion using Google AI API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instruction (passed as system_instruction in config)
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments
            
        Returns:
            Generated text response
            
        Raises:
            ProviderError: If API call fails
        """
        # Use Retrying with instance's max_retries for configuration-driven retry behavior
        # max_retries is the number of retries, so total attempts = max_retries + 1
        # This preserves the original behavior of 3 total attempts (1 initial + 2 retries) when max_retries=2
        retry_strategy = Retrying(
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=1, min=2, max=10),
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
                    # Build config with system instruction if provided
                    config_params = {
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                        **kwargs
                    }
                    if system_prompt:
                        config_params["system_instruction"] = system_prompt
                    
                    # Google AI SDK usage
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(**config_params)
                    )
                    
                    if not response.text:
                        raise ProviderError("Google AI returned empty response")
                    
                    self.logger.info("text_generated", response_length=len(response.text))
                    return response.text
            
        except ProviderError:
            # Re-raise ProviderError without wrapping (e.g., from validation checks)
            raise
        except Exception as e:
            error_type = type(e).__name__
            self.logger.error("api_error", error=str(e), error_type=error_type)
            
            # Check for specific error types
            if "429" in str(e) or "rate" in str(e).lower():
                raise ProviderError(f"Google AI rate limit exceeded: {e}") from e
            elif "timeout" in str(e).lower():
                raise ProviderError(f"Google AI request timeout: {e}") from e
            else:
                raise ProviderError(f"Google AI API error: {e}") from e
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Google AI models use ~4 characters per token on average.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated number of tokens
        """
        # Rough estimate: ~4 characters per token
        return len(text) // 4
