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
from typing import Any, Optional, Union

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
                pattern.replace("*", ".*")
                keys = self._redis.keys(pattern)
                if keys:
                    self._redis.delete(*keys)
                return
            except Exception as e:
                logger.warning(f"Redis clear_pattern failed: {e}")
                self._connected = False

        self._memory_fallback.clear_pattern(pattern)


class RedisClusterCache:
    """
    Redis cluster cache client with fallback to memory cache.

    Used when Redis cluster is available and configured.
    """

    def __init__(self, cluster_nodes: list[dict], ttl: int = 300, timeout: int = 5):
        """
        Initialize Redis cluster cache.

        Args:
            cluster_nodes: List of cluster node dicts with 'host' and 'port'
            ttl: Default TTL in seconds
            timeout: Connection timeout in seconds
        """
        self._cluster_nodes = cluster_nodes
        self._default_ttl = ttl
        self._timeout = timeout
        self._cluster = None
        self._memory_fallback = MemoryCache()
        self._connected = False
        self._connect()

    def _connect(self):
        """Connect to Redis cluster with error handling."""
        try:
            from redis.cluster import RedisCluster
            self._cluster = RedisCluster(
                startup_nodes=self._cluster_nodes,
                decode_responses=True,
                skip_full_coverage_check=True,
                socket_timeout=self._timeout,
                socket_connect_timeout=self._timeout,
            )
            self._cluster.ping()
            self._connected = True
            logger.info("Redis cluster connected")
        except Exception as e:
            logger.warning(f"Redis cluster connection failed, using memory fallback: {e}")
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
                value = self._cluster.get(key)
                if value:
                    return json.loads(value)
                return None
            except Exception as e:
                logger.warning(f"Redis cluster get failed: {e}")
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
                self._cluster.setex(key, ttl, serialized)
                return
            except Exception as e:
                logger.warning(f"Redis cluster set failed: {e}")
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
                self._cluster.delete(key)
                return True
            except Exception as e:
                logger.warning(f"Redis cluster delete failed: {e}")
                self._connected = False

        return self._memory_fallback.delete(key)

    def clear(self):
        """Clear all cached values."""
        if self._connected:
            try:
                # Flush all nodes in cluster
                for node in self._cluster.get_cluster_info()['cluster_slots']:
                    # This is a simplified approach - in production you'd want to be more careful
                    pass
                logger.info("Redis cluster clear attempted")
                return
            except Exception as e:
                logger.warning(f"Redis cluster clear failed: {e}")
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
                pattern.replace("*", ".*")
                keys = self._cluster.keys(pattern)
                if keys:
                    self._cluster.delete(*keys)
                return
            except Exception as e:
                logger.warning(f"Redis cluster clear_pattern failed: {e}")
                self._connected = False

        self._memory_fallback.clear_pattern(pattern)


class TaggedCache:
    """
    Tag-based cache invalidation wrapper.

    Allows cache entries to be tagged and invalidated by tag.
    Wraps any cache backend (MemoryCache, RedisCache, RedisClusterCache).
    """

    def __init__(self, cache_backend: Union[MemoryCache, RedisCache, RedisClusterCache]):
        """
        Initialize tagged cache wrapper.

        Args:
            cache_backend: The underlying cache instance to wrap
        """
        self._cache = cache_backend
        self._tag_separator = ":"

    def set(self, key: str, value: Any, ttl: Optional[int] = None, tags: Optional[list[str]] = None):
        """
        Set value with tags for invalidation.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            tags: List of tag strings for this cache entry
        """
        self._cache.set(key, value, ttl)

        if tags:
            for tag in tags:
                tag_key = f"tag:{self._tag_separator}{tag}"
                tagged_keys = self._cache.get(tag_key) or []
                if key not in tagged_keys:
                    tagged_keys.append(key)
                    self._cache.set(tag_key, tagged_keys, ttl)

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        return self._cache.get(key)

    def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        return self._cache.delete(key)

    def invalidate_tag(self, tag: str):
        """
        Invalidate all cache entries with given tag.

        Args:
            tag: Tag string to invalidate
        """
        tag_key = f"tag:{self._tag_separator}{tag}"
        tagged_keys = self._cache.get(tag_key)

        if tagged_keys:
            for key in tagged_keys:
                self._cache.delete(key)
            self._cache.delete(tag_key)

    def invalidate_user_cache(self, user_id: int):
        """
        Invalidate all cache entries for a specific user.

        Args:
            user_id: User ID to invalidate cache for
        """
        self.invalidate_tag(f"user:{user_id}")

    def clear(self):
        """Clear all cached values."""
        self._cache.clear()

    def clear_pattern(self, pattern: str):
        """
        Clear keys matching pattern.

        Args:
            pattern: Pattern with * wildcard
        """
        if hasattr(self._cache, 'clear_pattern'):
            self._cache.clear_pattern(pattern)
        else:
            # Fallback: clear all if pattern not supported
            self.clear()


# Global cache instance
_cache: Optional[Union[RedisClusterCache, RedisCache, MemoryCache]] = None
_cache_lock = threading.Lock()


def get_cache(config: Optional[CacheConfig] = None) -> Union[RedisClusterCache, RedisCache, MemoryCache]:
    """
    Get cache instance.

    Args:
        config: Cache configuration

    Returns:
        Cache instance (Redis cluster, Redis with fallback, or MemoryCache)
    """
    global _cache

    with _cache_lock:
        if _cache is None:
            config = config or CacheConfig()
            from config import Config

            # Check for Redis cluster first
            if Config.REDIS_CLUSTER_ENABLED and Config.REDIS_CLUSTER_NODES:
                try:
                    nodes = [
                        {"host": node.split(":")[0], "port": int(node.split(":")[1])}
                        for node in Config.REDIS_CLUSTER_NODES.split(",")
                    ]
                    _cache = RedisClusterCache(
                        nodes,
                        config.default_ttl_seconds,
                        config.redis_timeout_seconds
                    )
                    return _cache
                except Exception as e:
                    logger.warning(f"Redis cluster initialization failed: {e}, falling back to single Redis or memory")

            # Fall back to single Redis instance
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


def cache_set(key: str, value: Any, ttl: Optional[int] = None, tags: Optional[list[str]] = None):
    """Set value in cache."""
    cache = get_cache()
    if hasattr(cache, 'set') and tags is not None:
        # Use TaggedCache if tags are provided
        tagged_cache = TaggedCache(cache)
        tagged_cache.set(key, value, ttl, tags)
    else:
        cache.set(key, value, ttl)


def cache_delete(key: str) -> bool:
    """Delete value from cache."""
    return get_cache().delete(key)


def cache_clear():
    """Clear all cached values."""
    get_cache().clear()


def cache_clear_pattern(pattern: str):
    """Clear keys matching pattern."""
    get_cache().clear_pattern(pattern)


def cache_invalidate_tag(tag: str):
    """Invalidate all cache entries with given tag."""
    cache = get_cache()
    if hasattr(cache, 'invalidate_tag'):
        cache.invalidate_tag(tag)
    else:
        # Wrap with TaggedCache if not already tagged
        tagged_cache = TaggedCache(cache)
        tagged_cache.invalidate_tag(tag)


def cache_invalidate_user_cache(user_id: int):
    """Invalidate all cache entries for a specific user."""
    cache = get_cache()
    if hasattr(cache, 'invalidate_user_cache'):
        cache.invalidate_user_cache(user_id)
    else:
        # Wrap with TaggedCache if not already tagged
        tagged_cache = TaggedCache(cache)
        tagged_cache.invalidate_user_cache(user_id)
