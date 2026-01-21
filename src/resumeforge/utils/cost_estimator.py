"""Cost estimation utilities for LLM API calls."""

# Constants
TOKENS_PER_MILLION = 1_000_000

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
        "gemini-2.5-flash": {
            "input": 0.075,  # $0.075 per 1M input tokens (same as 1.5 Flash)
            "output": 0.30,  # $0.30 per 1M output tokens (same as 1.5 Flash)
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
    
    # Try exact model match first
    model_pricing = provider_pricing.get(model)
    
    # Fallback: find models with matching prefix or similar version
    # Matches if: requested model starts with available model OR available model starts with requested prefix
    # Also handles version differences (e.g., "gemini-2.5-flash" matches "gemini-1.5-flash")
    # Examples: "gpt-4o-turbo" matches "gpt-4o", "gpt-4" matches "gpt-4o"
    if not model_pricing:
        model_parts = model.split("-")
        if len(model_parts) >= 2:
            prefix = "-".join(model_parts[:2])  # First two parts (e.g., "gpt-4")
            # Find first model that matches:
            # Priority order:
            # 1. For Gemini models: match by base name ignoring version (e.g., "gemini-2.5-flash" matches "gemini-1.5-flash")
            # 2. Requested model starts with available model (e.g., "gpt-4o-turbo" starts with "gpt-4o")
            # 3. Available model starts with requested prefix (e.g., "gpt-4o" starts with "gpt-4")
            for model_key in provider_pricing:
                matched = False
                
                # Special handling for Gemini models: match by base name (gemini-X.X-flash)
                # Check this first as it's more precise than prefix matching
                if provider_name == "google" and "gemini" in model.lower() and "gemini" in model_key.lower():
                    # Extract base name (e.g., "gemini-flash" from "gemini-1.5-flash" or "gemini-2.5-flash")
                    model_base = "-".join([p for p in model.split("-") if p not in ["1.5", "2.5", "1", "2"]])
                    key_base = "-".join([p for p in model_key.split("-") if p not in ["1.5", "2.5", "1", "2"]])
                    if model_base == key_base:
                        model_pricing = provider_pricing[model_key]
                        matched = True
                
                # General prefix matching (for non-Gemini models or if Gemini matching didn't succeed)
                if not matched and (model.startswith(model_key) or model_key.startswith(prefix)):
                    model_pricing = provider_pricing[model_key]
                    matched = True
                
                if matched:
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
    
    input_cost = (input_tokens / TOKENS_PER_MILLION) * model_pricing["input"]
    output_cost = 0.0
    if output_tokens:
        output_cost = (output_tokens / TOKENS_PER_MILLION) * model_pricing["output"]
    
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
