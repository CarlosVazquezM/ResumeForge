"""Caching utilities for performance optimization."""

import json
from functools import lru_cache
from pathlib import Path

import structlog

from resumeforge.exceptions import OrchestrationError
from resumeforge.schemas.evidence_card import EvidenceCard

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def _load_evidence_cards_cached_internal(
    evidence_path_str: str, file_mtime: float
) -> tuple[dict, ...]:
    """
    Internal cached function that loads evidence cards.
    
    Uses tuple of dicts as cache value since EvidenceCard objects aren't hashable.
    The mtime parameter ensures cache invalidation when file is modified.
    
    Args:
        evidence_path_str: Path to evidence cards file (as string for hashing)
        file_mtime: File modification time (used as part of cache key)
        
    Returns:
        Tuple of card dictionaries (for caching)
    """
    evidence_path = Path(evidence_path_str)
    
    if not evidence_path.exists():
        raise OrchestrationError(
            f"Evidence cards file not found: {evidence_path}. "
            "Run 'resumeforge parse' first to generate evidence cards."
        )
    
    try:
        with open(evidence_path) as f:
            loaded_data = json.load(f)
        
        # Handle both formats: direct list or wrapped in dict with "evidence_cards" key
        if isinstance(loaded_data, list):
            cards_data = loaded_data
        elif isinstance(loaded_data, dict) and "evidence_cards" in loaded_data:
            cards_data = loaded_data["evidence_cards"]
        else:
            raise OrchestrationError(
                f"Invalid evidence cards format. Expected list or dict with 'evidence_cards' key, "
                f"got {type(loaded_data).__name__}"
            )
        
        # Return as tuple of dicts for caching (EvidenceCard objects aren't hashable)
        return tuple(cards_data)
        
    except json.JSONDecodeError as e:
        raise OrchestrationError(
            f"Invalid JSON in evidence cards file: {e}"
        ) from e
    except OrchestrationError:
        raise
    except Exception as e:
        raise OrchestrationError(
            f"Error loading evidence cards: {e}"
        ) from e


def load_evidence_cards_cached(evidence_path: Path | str) -> list[EvidenceCard]:
    """
    Load evidence cards with caching based on file modification time.
    
    The cache automatically invalidates when the file is modified (mtime changes).
    Uses LRU cache with maxsize=1 since we typically only have one evidence cards file.
    
    Args:
        evidence_path: Path to evidence cards JSON file
        
    Returns:
        List of EvidenceCard objects
        
    Raises:
        OrchestrationError: If file doesn't exist or can't be parsed
    """
    evidence_path = Path(evidence_path)
    
    # Get file modification time for cache invalidation
    if not evidence_path.exists():
        raise OrchestrationError(
            f"Evidence cards file not found: {evidence_path}. "
            "Run 'resumeforge parse' first to generate evidence cards."
        )
    
    file_mtime = evidence_path.stat().st_mtime
    evidence_path_str = str(evidence_path.resolve())
    
    # Load from cache (includes mtime in cache key)
    cards_data_tuple = _load_evidence_cards_cached_internal(evidence_path_str, file_mtime)
    
    # Convert cached dicts to EvidenceCard objects
    evidence_cards = [
        EvidenceCard(**card_data) for card_data in cards_data_tuple
    ]
    
    logger.debug(
        "Evidence cards loaded",
        path=evidence_path_str,
        count=len(evidence_cards),
        cached=True,
    )
    
    return evidence_cards


def clear_evidence_cache() -> None:
    """
    Clear the evidence cards cache.
    
    Useful for testing or when you want to force reload.
    """
    _load_evidence_cards_cached_internal.cache_clear()
    logger.debug("Evidence cards cache cleared")
