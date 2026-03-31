"""
Cache Service for KoraPay Integration

This module provides caching capabilities with fallback when Redis is unavailable.
Supports in-memory caching as fallback for development/testing.

Requirements: 52.21-52.26
"""

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CacheBackend(Enum):
    """Available cache backends."""
    REDIS = "redis"
    MEMORY = "memory"


@dataclass
class CacheConfig:
    """Cache configuration."""
    backend: CacheBackend = CacheBackend.MEMORY
    redis_url: Optional[str] = None
    default_ttl_seconds: int = 300
    max_memory_items: int = 1000
    redis_timeout_seconds: int = 5


class MemoryCache:
    """
    In-memory cache with LRU eviction and TTL support.

    Used as fallback when Redis is unavailable.
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize memory cache.

        Args:
            max_size: Maximum number of items before LRU eviction
        """
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            value, expiry = self._cache[key]

            # Check expiry
            if expiry > 0 and time.time() > expiry:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (0 = no expiry)
        """
        with self._lock:
            # Calculate expiry time
            expiry = time.time() + ttl if ttl and ttl > 0 else 0

            # Evict oldest if at capacity
            if key not in self._cache and len(self._cache) >= self._max_size:
                self._evict_oldest()

            self._cache[key] = (value, expiry)
            self._cache.move_to_end(key)

    def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        """Clear all cached values."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def clear_pattern(self, pattern: str):
        """
        Clear all keys matching pattern.

        Args:
            pattern: Pattern to match (supports * wildcard)
        """
        with self._lock:
            if pattern == "*":
                self.clear()
                return

            # Convert wildcard pattern to regex
            import re
            regex_pattern = pattern.replace("*", ".*")
            regex = re.compile(regex_pattern)

            keys_to_delete = [k for k in self._cache.keys() if regex.match(k)]
            for key in keys_to_delete:
                del self._cache[key]

    def _evict_oldest(self):
        """Evict oldest (least recently used) item."""
        if self._cache:
            self._cache.popitem(last=False)

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with hits, misses, size
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0

            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "hit_rate_percent": round(hit_rate, 2)
            }


class RedisCache:
    """
    Redis cache client with fallback to memory cache.

    Used when Redis is available and configured.
    """

    def __init__(self, redis_url: str, ttl: int = 300, timeout: int = 5):
        """
        Initialize Redis cache.

        Args:
            redis_url: Redis connection URL
            ttl: Default TTL in seconds
            timeout: Connection timeout in seconds
        """
        self._redis_url = redis_url
        self._default_ttl = ttl
        self._timeout = timeout
        self._redis = None
        self._memory_fallback = MemoryCache()
        self._connected = False
        self._connect()

    def _connect(self):
        """Connect to Redis with error handling."""
        try:
            import redis
            self._redis = redis.from_url(
                self._redis_url,
                socket_timeout=self._timeout,
                socket_connect_timeout=self._timeout,
                decode_responses=True
            )
            self._redis.ping()
            self._connected = True
            logger.info("Redis cache connected")
        except Exception as e:
            logger.warning(f"Redis connection failed, using memory fallback: {e}")
            self._connected = False

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if self._connected:
            try:
                import json
                value = self._redis.get(key)
                if value:
                    return json.loads(value)
                return None
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
                self._connected = False

        return self._memory_fallback.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
        """
        ttl = ttl or self._default_ttl

        if self._connected:
            try:
                import json
                serialized = json.dumps(value)
                self._redis.setex(key, ttl, serialized)
                return
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
                self._connected = False

        self._memory_fallback.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        if self._connected:
            try:
                self._redis.delete(key)
                return True
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")
                self._connected = False

        return self._memory_fallback.delete(key)

    def clear(self):
        """Clear all cached values."""
        if self._connected:
            try:
                self._redis.flushdb()
                return
            except Exception as e:
                logger.warning(f"Redis clear failed: {e}")
                self._connected = False

        self._memory_fallback.clear()

    def clear_pattern(self, pattern: str):
        """
        Clear keys matching pattern.

        Args:
            pattern: Pattern with * wildcard
        """
        if self._connected:
            try:
                import re
                regex_pattern = pattern.replace("*", ".*")
                keys = self._redis.keys(pattern)
                if keys:
                    self._redis.delete(*keys)
                return
            except Exception as e:
                logger.warning(f"Redis clear_pattern failed: {e}")
                self._connected = False

        self._memory_fallback.clear_pattern(pattern)


# Global cache instance
_cache: Optional[RedisCache | MemoryCache] = None
_cache_lock = threading.Lock()


def get_cache(config: Optional[CacheConfig] = None) -> RedisCache | MemoryCache:
    """
    Get cache instance.

    Args:
        config: Cache configuration

    Returns:
        Cache instance (Redis with fallback or MemoryCache)
    """
    global _cache

    with _cache_lock:
        if _cache is None:
            config = config or CacheConfig()
            if config.backend == CacheBackend.REDIS and config.redis_url:
                _cache = RedisCache(
                    config.redis_url,
                    config.default_ttl_seconds,
                    config.redis_timeout_seconds
                )
            else:
                _cache = MemoryCache(config.max_memory_items)

        return _cache


def reset_cache():
    """Reset global cache instance (for testing)."""
    global _cache
    with _cache_lock:
        if _cache:
            _cache.clear()
        _cache = None


# Convenience functions

def cache_get(key: str) -> Optional[Any]:
    """Get value from cache."""
    return get_cache().get(key)


def cache_set(key: str, value: Any, ttl: Optional[int] = None):
    """Set value in cache."""
    get_cache().set(key, value, ttl)


def cache_delete(key: str) -> bool:
    """Delete value from cache."""
    return get_cache().delete(key)


def cache_clear():
    """Clear all cached values."""
    get_cache().clear()


def cache_clear_pattern(pattern: str):
    """Clear keys matching pattern."""
    get_cache().clear_pattern(pattern)
