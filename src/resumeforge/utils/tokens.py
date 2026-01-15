"""Token counting utilities."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from resumeforge.providers.base import BaseProvider


def estimate_tokens(text: str, provider: "BaseProvider | None" = None) -> int:
    """
    Estimate token count for text.
    
    Args:
        text: Text to count tokens for
        provider: Optional provider for accurate counting
        
    Returns:
        Estimated token count
    """
    if provider:
        return provider.count_tokens(text)
    
    # Fallback: rough estimate (4 chars per token)
    return len(text) // 4
