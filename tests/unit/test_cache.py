"""
Unit tests for cache service.

Tests Requirements: 52.21, 52.22, 52.23, 52.26
"""

import time
from unittest.mock import Mock, patch

import pytest

from services.cache import (
    CacheBackend,
    CacheConfig,
    MemoryCache,
    RedisCache,
    cache_clear,
    cache_clear_pattern,
    cache_delete,
    cache_get,
    cache_set,
    get_cache,
    reset_cache,
)


class TestMemoryCache:
    """Tests for MemoryCache class."""

    @pytest.fixture(autouse=True)
    def reset(self):
        """Reset cache before each test."""
        reset_cache()
        yield
        reset_cache()

    def test_get_returns_none_for_missing_key(self):
        """Test get returns None for missing key."""
        cache = MemoryCache()

        result = cache.get("nonexistent")

        assert result is None

    def test_set_and_get(self):
        """Test set and get of value."""
        cache = MemoryCache()

        cache.set("key1", "value1")
        result = cache.get("key1")

        assert result == "value1"

    def test_get_returns_none_for_expired(self):
        """Test get returns None for expired key."""
        cache = MemoryCache()

        cache.set("key1", "value1", ttl=1)
        time.sleep(1.1)

        result = cache.get("key1")

        assert result is None

    def test_set_with_no_ttl(self):
        """Test set with no TTL (never expires)."""
        cache = MemoryCache()

        cache.set("key1", "value1", ttl=0)
        time.sleep(0.1)

        result = cache.get("key1")

        assert result == "value1"

    def test_delete(self):
        """Test delete removes value."""
        cache = MemoryCache()

        cache.set("key1", "value1")
        result = cache.delete("key1")

        assert result is True
        assert cache.get("key1") is None

    def test_delete_returns_false_for_missing(self):
        """Test delete returns False for missing key."""
        cache = MemoryCache()

        result = cache.delete("nonexistent")

        assert result is False

    def test_clear(self):
        """Test clear removes all values."""
        cache = MemoryCache()

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_lru_eviction(self):
        """Test LRU eviction when at capacity."""
        cache = MemoryCache(max_size=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict key1

        assert cache.get("key1") is None
        assert cache.get("key4") == "value4"

    def test_lru_on_access(self):
        """Test LRU updates on access."""
        cache = MemoryCache(max_size=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.get("key1")  # Access key1
        cache.set("key4", "value4")  # Should evict key2 (not key1)

        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None

    def test_clear_pattern(self):
        """Test clear pattern removes matching keys."""
        cache = MemoryCache()

        cache.set("user:1", "data1")
        cache.set("user:2", "data2")
        cache.set("order:1", "data3")
        cache.clear_pattern("user:*")

        assert cache.get("user:1") is None
        assert cache.get("user:2") is None
        assert cache.get("order:1") == "data3"

    def test_clear_pattern_all(self):
        """Test clear pattern with * clears all."""
        cache = MemoryCache()

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear_pattern("*")

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_get_stats(self):
        """Test get stats returns hit/miss counts."""
        cache = MemoryCache()

        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("nonexistent")  # Miss

        stats = cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate_percent"] == 50.0

    def test_thread_safety(self):
        """Test thread-safe operations."""
        import threading

        cache = MemoryCache()
        errors = []

        def worker():
            try:
                for i in range(100):
                    cache.set(f"key{i}", f"value{i}")
                    cache.get(f"key{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestCacheConfig:
    """Tests for CacheConfig."""

    def test_default_config(self):
        """Test default cache config."""
        config = CacheConfig()

        assert config.backend == CacheBackend.MEMORY
        assert config.redis_url is None
        assert config.default_ttl_seconds == 300
        assert config.max_memory_items == 1000
        assert config.redis_timeout_seconds == 5


class TestGetCache:
    """Tests for get_cache function."""

    @pytest.fixture(autouse=True)
    def reset(self):
        """Reset cache before each test."""
        reset_cache()
        yield
        reset_cache()

    def test_returns_memory_cache_by_default(self):
        """Test get_cache returns MemoryCache by default."""
        cache = get_cache()

        assert isinstance(cache, MemoryCache)

    def test_returns_same_instance(self):
        """Test get_cache returns singleton."""
        cache1 = get_cache()
        cache2 = get_cache()

        assert cache1 is cache2

    def test_reset_cache_clears_and_returns_new(self):
        """Test reset_cache clears singleton."""
        cache1 = get_cache()
        cache1.set("key", "value")

        reset_cache()

        cache2 = get_cache()
        assert cache2.get("key") is None


class TestCacheFunctions:
    """Tests for convenience cache functions."""

    @pytest.fixture(autouse=True)
    def reset(self):
        """Reset cache before each test."""
        reset_cache()
        yield
        reset_cache()

    def test_cache_set_and_get(self):
        """Test cache_set and cache_get functions."""
        cache_set("key1", "value1")
        result = cache_get("key1")

        assert result == "value1"

    def test_cache_delete(self):
        """Test cache_delete function."""
        cache_set("key1", "value1")
        result = cache_delete("key1")

        assert result is True
        assert cache_get("key1") is None

    def test_cache_clear(self):
        """Test cache_clear function."""
        cache_set("key1", "value1")
        cache_set("key2", "value2")
        cache_clear()

        assert cache_get("key1") is None
        assert cache_get("key2") is None

    def test_cache_clear_pattern(self):
        """Test cache_clear_pattern function."""
        cache_set("user:1", "data1")
        cache_set("user:2", "data2")
        cache_set("order:1", "data3")
        cache_clear_pattern("user:*")

        assert cache_get("user:1") is None
        assert cache_get("order:1") == "data3"


class TestRedisCache:
    """Tests for RedisCache class."""

    @pytest.mark.skip(reason="Redis library not installed, RedisCache uses fallback")
    def test_redis_cache_fallback_to_memory(self):
        """Test RedisCache falls back to memory on connection failure."""
        with patch("services.cache.redis") as mock_redis:
            mock_redis.from_url.side_effect = Exception("Connection failed")

            cache = RedisCache("redis://localhost:6379", ttl=300, timeout=1)

            # Should fall back to memory
            cache.set("key1", "value1")
            assert cache.get("key1") == "value1"

    @pytest.mark.skip(reason="Redis library not installed, RedisCache uses fallback")
    def test_redis_cache_handles_connection_error_on_get(self):
        """Test RedisCache handles connection error on get."""
        with patch("services.cache.redis") as mock_redis:
            mock_redis.from_url.return_value.ping.side_effect = Exception("Connection failed")

            cache = RedisCache("redis://localhost:6379", ttl=300, timeout=1)
            cache._connected = True  # Pretend we were connected

            # Should fall back to memory
            assert cache.get("key1") is None

    @pytest.mark.skip(reason="Redis library not installed, RedisCache uses fallback")
    def test_redis_cache_handles_connection_error_on_set(self):
        """Test RedisCache handles connection error on set."""
        with patch("services.cache.redis") as mock_redis:
            mock_redis.from_url.return_value.ping.side_effect = Exception("Connection failed")

            cache = RedisCache("redis://localhost:6379", ttl=300, timeout=1)
            cache._connected = True

            # Should fall back to memory - no exception
            cache.set("key1", "value1")
