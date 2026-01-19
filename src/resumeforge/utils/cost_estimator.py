"""Cost estimation utilities for LLM API calls."""

# Pricing as of January 2025 (per 1M tokens)
# Input/Output pricing may differ
PRICING = {
    "anthropic": {
        "claude-sonnet-4-20250514": {
            "input": 3.00,  # $3 per 1M input tokens
            "output": 15.00,  # $15 per 1M output tokens
        },
        "claude-3-5-sonnet-20241022": {
            "input": 3.00,
            "output": 15.00,
        },
    },
    "openai": {
        "gpt-4o": {
            "input": 2.50,  # $2.50 per 1M input tokens
            "output": 10.00,  # $10 per 1M output tokens
        },
        "gpt-4o-mini": {
            "input": 0.15,
            "output": 0.60,
        },
    },
    "google": {
        "gemini-1.5-flash": {
            "input": 0.075,  # $0.075 per 1M input tokens
            "output": 0.30,  # $0.30 per 1M output tokens
        },
    },
    "groq": {
        "llama-3.1-70b-versatile": {
            "input": 0.00,  # Free tier
            "output": 0.00,
        },
    },
}


def estimate_cost(
    provider_name: str,
    model: str,
    input_tokens: int,
    output_tokens: int | None = None,
) -> dict[str, float | int]:
    """
    Estimate cost for an LLM API call.
    
    Args:
        provider_name: Provider name (e.g., "anthropic")
        model: Model identifier
        input_tokens: Estimated input tokens
        output_tokens: Estimated output tokens (if None, estimates based on max_tokens)
        
    Returns:
        Dictionary with cost breakdown
    """
    if provider_name not in PRICING:
        return {
            "estimated_cost_usd": 0.0,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens or 0,
            "provider": provider_name,
            "model": model,
            "note": "Pricing not available for this provider/model",
        }
    
    provider_pricing = PRICING[provider_name]
    
    # Try exact model match first, then fallback
    model_pricing = None
    for model_key in [model, model.split("-")[0] + "-*"]:
        if model_key in provider_pricing:
            model_pricing = provider_pricing[model_key]
            break
    
    if not model_pricing:
        return {
            "estimated_cost_usd": 0.0,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens or 0,
            "provider": provider_name,
            "model": model,
            "note": "Pricing not available for this model",
        }
    
    input_cost = (input_tokens / 1_000_000) * model_pricing["input"]
    output_cost = 0.0
    if output_tokens:
        output_cost = (output_tokens / 1_000_000) * model_pricing["output"]
    
    total_cost = input_cost + output_cost
    
    return {
        "estimated_cost_usd": total_cost,
        "input_cost_usd": input_cost,
        "output_cost_usd": output_cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens or 0,
        "provider": provider_name,
        "model": model,
    }
