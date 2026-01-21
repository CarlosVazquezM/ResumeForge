"""Caching utilities for performance optimization with pluggable backends."""

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog

from resumeforge.exceptions import OrchestrationError
from resumeforge.schemas.evidence_card import EvidenceCard

logger = structlog.get_logger(__name__)


# ============================================================================
# Abstract Cache Backend Interface
# ============================================================================

class CacheBackend(ABC):
    """
    Abstract base class for cache backends.
    
    This interface allows swapping between local file-based caching
    and distributed caching (e.g., Redis) without changing agent code.
    """
    
    @abstractmethod
    def get(self, key: str, namespace: str) -> dict | None:
        """
        Retrieve cached value.
        
        Args:
            key: Cache key (typically a hash)
            namespace: Namespace/prefix for the key (e.g., "jd_analyst")
            
        Returns:
            Cached data dict if found, None otherwise
        """
        pass
    
    @abstractmethod
    def set(self, key: str, namespace: str, value: dict, ttl_seconds: int | None = None) -> None:
        """
        Store value in cache.
        
        Args:
            key: Cache key
            namespace: Namespace/prefix for the key
            value: Data to cache (must be JSON-serializable)
            ttl_seconds: Optional time-to-live in seconds (None = no expiration)
        """
        pass
    
    @abstractmethod
    def delete(self, key: str, namespace: str) -> None:
        """
        Delete cached value.
        
        Args:
            key: Cache key
            namespace: Namespace/prefix
        """
        pass
    
    @abstractmethod
    def clear(self, namespace: str | None = None) -> None:
        """
        Clear cache entries.
        
        Args:
            namespace: If provided, only clear this namespace.
                      If None, clear all entries.
        """
        pass
    
    @abstractmethod
    def exists(self, key: str, namespace: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            namespace: Namespace/prefix
            
        Returns:
            True if key exists, False otherwise
        """
        pass


# ============================================================================
# No-Op Cache Backend (Disables Caching)
# ============================================================================

class NoOpCacheBackend(CacheBackend):
    """
    No-operation cache backend that disables caching.
    
    All operations are no-ops - get() always returns None,
    set() does nothing, etc. This is used when --no-cache
    flag is set to ensure no caching occurs.
    """
    
    def __init__(self):
        """Initialize no-op cache backend."""
        self.logger = logger.bind(backend="NoOpCache")
    
    def get(self, key: str, namespace: str) -> dict | None:
        """Always return None (no caching)."""
        return None
    
    def set(self, key: str, namespace: str, value: dict, ttl_seconds: int | None = None) -> None:
        """Do nothing (no caching)."""
        pass
    
    def delete(self, key: str, namespace: str) -> None:
        """Do nothing (no caching)."""
        pass
    
    def clear(self, namespace: str | None = None) -> None:
        """Do nothing (no caching)."""
        pass
    
    def exists(self, key: str, namespace: str) -> bool:
        """Always return False (no caching)."""
        return False


# ============================================================================
# File-Based Cache Backend (Current Implementation)
# ============================================================================

class FileCacheBackend(CacheBackend):
    """
    Local file-based cache backend.
    
    Stores cache entries as JSON files in a directory structure:
    {cache_dir}/{namespace}-{key_short}.json
    
    This is the default implementation for local development.
    """
    
    def __init__(self, cache_dir: Path | str = "./outputs/.cache"):
        """
        Initialize file cache backend.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger.bind(backend="FileCache")
    
    def _get_cache_path(self, key: str, namespace: str) -> Path:
        """Get file path for cache entry."""
        # Use first 16 chars of key for filename (collision risk is minimal)
        key_short = key[:16]
        return self.cache_dir / f"{namespace}-{key_short}.json"
    
    def get(self, key: str, namespace: str) -> dict | None:
        """Retrieve from file cache."""
        cache_file = self._get_cache_path(key, namespace)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file) as f:
                data = json.load(f)
            
            # Verify hash matches (sanity check)
            if data.get("hash") != key:
                self.logger.warning(
                    "Cache hash mismatch, ignoring",
                    namespace=namespace,
                    cache_file=str(cache_file),
                    expected=key[:16],
                    found=data.get("hash", "")[:16] if data.get("hash") else None
                )
                return None
            
            # Check TTL if set
            if "expires_at" in data:
                expires_at = datetime.fromisoformat(data["expires_at"])
                if datetime.now() > expires_at:
                    self.logger.debug("Cache entry expired", namespace=namespace, key=key[:16])
                    cache_file.unlink()  # Delete expired entry
                    return None
            
            self.logger.debug("Cache hit", namespace=namespace, key=key[:16])
            return data.get("result")
            
        except Exception as e:
            self.logger.warning(
                "Failed to load cache",
                namespace=namespace,
                cache_file=str(cache_file),
                error=str(e)
            )
            return None
    
    def set(self, key: str, namespace: str, value: dict, ttl_seconds: int | None = None) -> None:
        """Store in file cache."""
        cache_file = self._get_cache_path(key, namespace)
        
        try:
            cache_data = {
                "hash": key,
                "namespace": namespace,
                "result": value,
                "cached_at": datetime.now().isoformat()
            }
            
            # Add expiration if TTL provided
            if ttl_seconds:
                expires_at = datetime.now().timestamp() + ttl_seconds
                cache_data["expires_at"] = datetime.fromtimestamp(expires_at).isoformat()
            
            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2, default=str)
            
            self.logger.debug(
                "Cache saved",
                namespace=namespace,
                key=key[:16],
                ttl_seconds=ttl_seconds
            )
        except Exception as e:
            self.logger.warning(
                "Failed to save cache",
                namespace=namespace,
                cache_file=str(cache_file),
                error=str(e)
            )
    
    def delete(self, key: str, namespace: str) -> None:
        """Delete from file cache."""
        cache_file = self._get_cache_path(key, namespace)
        if cache_file.exists():
            cache_file.unlink()
            self.logger.debug("Cache deleted", namespace=namespace, key=key[:16])
    
    def clear(self, namespace: str | None = None) -> None:
        """Clear cache entries."""
        if namespace:
            pattern = f"{namespace}-*.json"
            deleted = 0
            for cache_file in self.cache_dir.glob(pattern):
                cache_file.unlink()
                deleted += 1
            self.logger.info("Cache cleared", namespace=namespace, deleted=deleted)
        else:
            deleted = 0
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                deleted += 1
            self.logger.info("All caches cleared", deleted=deleted)
    
    def exists(self, key: str, namespace: str) -> bool:
        """Check if cache entry exists."""
        cache_file = self._get_cache_path(key, namespace)
        return cache_file.exists()


# ============================================================================
# Redis Cache Backend (Future Implementation)
# ============================================================================

class RedisCacheBackend(CacheBackend):
    """
    Redis-based cache backend for distributed caching.
    
    This implementation will be used when running in a multi-user
    or distributed environment where cache sharing is beneficial.
    
    Note: Requires 'redis' package (not installed by default).
    Install with: pip install redis
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        key_prefix: str = "resumeforge:cache:"
    ):
        """
        Initialize Redis cache backend.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Optional Redis password
            key_prefix: Prefix for all cache keys
        """
        try:
            import redis
        except ImportError:
            raise ImportError(
                "Redis backend requires 'redis' package. "
                "Install with: pip install redis"
            )
        
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=False  # We'll handle JSON encoding/decoding
        )
        self.key_prefix = key_prefix
        self.logger = logger.bind(backend="RedisCache")
        
        # Test connection
        try:
            self.client.ping()
            self.logger.info("Redis connection established", host=host, port=port)
        except Exception as e:
            raise OrchestrationError(f"Failed to connect to Redis: {e}") from e
    
    def _make_key(self, key: str, namespace: str) -> bytes:
        """Create full Redis key."""
        return f"{self.key_prefix}{namespace}:{key}".encode()
    
    def get(self, key: str, namespace: str) -> dict | None:
        """Retrieve from Redis."""
        redis_key = self._make_key(key, namespace)
        
        try:
            data = self.client.get(redis_key)
            if data is None:
                return None
            
            cache_data = json.loads(data)
            
            # Verify hash matches
            if cache_data.get("hash") != key:
                self.logger.warning("Cache hash mismatch", namespace=namespace, key=key[:16])
                return None
            
            self.logger.debug("Cache hit", namespace=namespace, key=key[:16])
            return cache_data.get("result")
            
        except Exception as e:
            self.logger.warning("Failed to load from Redis", namespace=namespace, error=str(e))
            return None
    
    def set(self, key: str, namespace: str, value: dict, ttl_seconds: int | None = None) -> None:
        """Store in Redis."""
        redis_key = self._make_key(key, namespace)
        
        try:
            cache_data = {
                "hash": key,
                "namespace": namespace,
                "result": value,
                "cached_at": datetime.now().isoformat()
            }
            
            data = json.dumps(cache_data, default=str)
            
            if ttl_seconds:
                self.client.setex(redis_key, ttl_seconds, data)
            else:
                self.client.set(redis_key, data)
            
            self.logger.debug("Cache saved to Redis", namespace=namespace, key=key[:16])
            
        except Exception as e:
            self.logger.warning("Failed to save to Redis", namespace=namespace, error=str(e))
    
    def delete(self, key: str, namespace: str) -> None:
        """Delete from Redis."""
        redis_key = self._make_key(key, namespace)
        self.client.delete(redis_key)
        self.logger.debug("Cache deleted from Redis", namespace=namespace, key=key[:16])
    
    def clear(self, namespace: str | None = None) -> None:
        """Clear cache entries."""
        if namespace:
            pattern = f"{self.key_prefix}{namespace}:*"
        else:
            pattern = f"{self.key_prefix}*"
        
        # Redis SCAN is safer for production than KEYS
        deleted = 0
        cursor = 0
        while True:
            cursor, keys = self.client.scan(cursor, match=pattern, count=100)
            if keys:
                self.client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        
        self.logger.info("Cache cleared", namespace=namespace or "all", deleted=deleted)
    
    def exists(self, key: str, namespace: str) -> bool:
        """Check if key exists in Redis."""
        redis_key = self._make_key(key, namespace)
        return bool(self.client.exists(redis_key))


# ============================================================================
# Cache Manager (High-Level Interface)
# ============================================================================

class LLMResultCache:
    """
    High-level cache manager for LLM agent results.
    
    Provides a simple interface for agents to cache/retrieve results,
    abstracting away the backend implementation.
    """
    
    def __init__(self, backend: CacheBackend | None = None):
        """
        Initialize cache manager.
        
        Args:
            backend: Cache backend to use. If None, uses FileCacheBackend by default.
        """
        self.backend = backend or FileCacheBackend()
        self.logger = logger.bind(cache="LLMResultCache")
    
    def compute_hash(self, *args: Any) -> str:
        """
        Compute SHA256 hash of input arguments.
        
        Args:
            *args: Arguments to hash (will be JSON-serialized)
            
        Returns:
            Hex digest of hash
        """
        # Serialize to JSON for consistent hashing
        json_str = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def get(self, agent_name: str, *cache_inputs: Any) -> dict | None:
        """
        Get cached result for agent.
        
        Args:
            agent_name: Name of agent (e.g., "jd_analyst")
            *cache_inputs: Input arguments that determine cache key
            
        Returns:
            Cached result dict if found, None otherwise
        """
        cache_key = self.compute_hash(*cache_inputs)
        return self.backend.get(cache_key, agent_name)
    
    def set(self, agent_name: str, result: dict, *cache_inputs: Any, ttl_seconds: int | None = None) -> None:
        """
        Store result in cache.
        
        Args:
            agent_name: Name of agent
            result: Result dict to cache
            *cache_inputs: Input arguments that determine cache key
            ttl_seconds: Optional time-to-live in seconds
        """
        cache_key = self.compute_hash(*cache_inputs)
        self.backend.set(cache_key, agent_name, result, ttl_seconds=ttl_seconds)
    
    def clear(self, agent_name: str | None = None) -> None:
        """
        Clear cache entries.
        
        Args:
            agent_name: If provided, only clear cache for this agent.
                       If None, clear all caches.
        """
        self.backend.clear(agent_name)
    
    def delete(self, agent_name: str, *cache_inputs: Any) -> None:
        """
        Delete specific cache entry.
        
        Args:
            agent_name: Name of agent
            *cache_inputs: Input arguments that determine cache key
        """
        cache_key = self.compute_hash(*cache_inputs)
        self.backend.delete(cache_key, agent_name)


# ============================================================================
# Factory Function
# ============================================================================

_global_cache: LLMResultCache | None = None
_cache_disabled: bool = False


def get_llm_cache(config: dict | None = None, disable_cache: bool = False) -> LLMResultCache:
    """
    Get or create global LLM result cache.
    
    Creates cache backend based on configuration:
    - If disable_cache is True, uses NoOpCacheBackend (no caching)
    - If config has "cache.backend" = "redis", uses RedisCacheBackend
    - Otherwise, uses FileCacheBackend
    
    Args:
        config: Optional config dict with cache settings.
                Expected keys:
                - cache.backend: "file" or "redis"
                - cache.file_dir: Directory for file cache (default: ./outputs/.cache)
                - cache.redis.host: Redis host (default: localhost)
                - cache.redis.port: Redis port (default: 6379)
                - cache.redis.db: Redis DB (default: 0)
                - cache.redis.password: Redis password (optional)
        disable_cache: If True, returns a cache with NoOpCacheBackend that doesn't cache
    
    Returns:
        LLMResultCache instance
    """
    global _global_cache, _cache_disabled
    
    # If cache is disabled, always return a new NoOp cache (don't reuse global)
    if disable_cache:
        _cache_disabled = True
        backend = NoOpCacheBackend()
        return LLMResultCache(backend)
    
    # If cache was previously disabled, clear the global cache to force recreation
    if _cache_disabled and _global_cache is not None:
        _global_cache = None
        _cache_disabled = False
    
    if _global_cache is not None:
        return _global_cache
    
    if config is None:
        # Default: file-based cache
        backend = FileCacheBackend()
    else:
        cache_config = config.get("cache", {})
        backend_type = cache_config.get("backend", "file")
        
        if backend_type == "redis":
            redis_config = cache_config.get("redis", {})
            backend = RedisCacheBackend(
                host=redis_config.get("host", "localhost"),
                port=redis_config.get("port", 6379),
                db=redis_config.get("db", 0),
                password=redis_config.get("password"),
                key_prefix=redis_config.get("key_prefix", "resumeforge:cache:")
            )
        else:  # file or default
            cache_dir = cache_config.get("file_dir", "./outputs/.cache")
            backend = FileCacheBackend(cache_dir)
    
    _global_cache = LLMResultCache(backend)
    return _global_cache


def clear_global_cache() -> None:
    """Clear the global cache instance (useful for testing or --no-cache flag)."""
    global _global_cache, _cache_disabled
    _global_cache = None
    _cache_disabled = False


# ============================================================================
# Evidence Cards Cache (Existing - Keep for backward compatibility)
# ============================================================================

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
