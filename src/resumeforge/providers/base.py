"""Base provider interface."""

from abc import ABC, abstractmethod
import structlog

logger = structlog.get_logger(__name__)


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, api_key: str, model: str, timeout_seconds: int = 45, max_retries: int = 2):
        """
        Initialize provider.
        
        Args:
            api_key: API key for the provider
            model: Model identifier
            timeout_seconds: Request timeout in seconds
            max_retries: Maximum number of retries
        """
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.logger = logger.bind(provider=self.__class__.__name__, model=model)
    
    @abstractmethod
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
        Generate a text completion from the model.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific arguments
            
        Returns:
            Generated text response
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in the given text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        pass
