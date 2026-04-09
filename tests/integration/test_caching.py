"""
OnePay — Caching Integration Tests

Tests for the caching layer (Requirement 11):
- Cache miss returns None (Req 11.1)
- Cache hit returns cached data (Req 11.2)
- Cache TTL expiry (Req 11.3, 11.4)
- Cache invalidation via delete (Req 11.5)
- Payment summary cache key pattern
"""

import time

import pytest

from services.cache import (
    cache_delete,
    cache_get,
    cache_set,
    reset_cache,
)


@pytest.fixture(autouse=True)
def isolated_cache():
    """Reset cache before and after each test for isolation (Req 20.3)."""
    reset_cache()
    yield
    reset_cache()


class TestCacheMiss:
    """Tests for cache miss behavior (Requirement 11.1)"""

    def test_cache_get_returns_none_on_miss(self):
        """cache_get returns None when key does not exist."""
        result = cache_get("nonexistent_key")
        assert result is None

    def test_cache_get_returns_none_for_unknown_payment_summary_key(self):
        """cache_get returns None for a payment_summary key that was never set."""
        result = cache_get("payment_summary:user_999")
        assert result is None

    def test_cache_get_returns_none_after_reset(self):
        """cache_get returns None after cache is reset."""
        cache_set("some_key", {"data": "value"})
        reset_cache()
        result = cache_get("some_key")
        assert result is None


class TestCacheHit:
    """Tests for cache hit behavior (Requirement 11.2)"""

    def test_cache_set_then_get_returns_cached_value(self):
        """cache_set followed by cache_get returns the stored value."""
        cache_set("test_key", {"result": 42})
        result = cache_get("test_key")
        assert result == {"result": 42}

    def test_cache_hit_returns_exact_data(self):
        """Cached data is returned unchanged."""
        data = {
            "success": True,
            "all_time": {"total_collected": "5000.00", "total_links": 10},
            "this_month": {"total_collected": "1000.00", "total_links": 3},
        }
        cache_set("payment_summary:user_1", data)
        result = cache_get("payment_summary:user_1")
        assert result == data

    def test_cache_hit_for_string_value(self):
        """Cache works for string values."""
        cache_set("str_key", "hello")
        assert cache_get("str_key") == "hello"

    def test_cache_hit_for_list_value(self):
        """Cache works for list values."""
        cache_set("list_key", [1, 2, 3])
        assert cache_get("list_key") == [1, 2, 3]

    def test_multiple_keys_are_independent(self):
        """Different cache keys store independent values."""
        cache_set("payment_summary:user_1", {"user": 1})
        cache_set("payment_summary:user_2", {"user": 2})

        assert cache_get("payment_summary:user_1") == {"user": 1}
        assert cache_get("payment_summary:user_2") == {"user": 2}


class TestCacheTTL:
    """Tests for cache TTL expiry (Requirements 11.3, 11.4)"""

    def test_cache_set_with_ttl_returns_value_before_expiry(self):
        """Value is accessible before TTL expires."""
        cache_set("ttl_key", "fresh_value", ttl=5)
        result = cache_get("ttl_key")
        assert result == "fresh_value"

    def test_cache_set_with_ttl_expires_after_timeout(self):
        """Value is None after TTL expires."""
        cache_set("expiring_key", "will_expire", ttl=1)
        time.sleep(1.1)
        result = cache_get("expiring_key")
        assert result is None

    def test_payment_summary_ttl_60_seconds_is_accessible(self):
        """Payment summary stored with 60s TTL is accessible immediately."""
        summary = {"success": True, "all_time": {"total_links": 5}}
        cache_set("payment_summary:user_42", summary, ttl=60)
        result = cache_get("payment_summary:user_42")
        assert result == summary

    def test_cache_without_ttl_does_not_expire(self):
        """Value stored without TTL persists."""
        cache_set("persistent_key", "stays_forever")
        # Small sleep to ensure no accidental expiry
        time.sleep(0.1)
        result = cache_get("persistent_key")
        assert result == "stays_forever"


class TestCacheInvalidation:
    """Tests for cache invalidation (Requirement 11.5)"""

    def test_cache_delete_removes_key(self):
        """cache_delete removes the key so subsequent get returns None."""
        cache_set("payment_summary:user_10", {"data": "old"})
        cache_delete("payment_summary:user_10")
        result = cache_get("payment_summary:user_10")
        assert result is None

    def test_cache_delete_returns_true_when_key_exists(self):
        """cache_delete returns True when the key was present."""
        cache_set("delete_me", "value")
        deleted = cache_delete("delete_me")
        assert deleted is True

    def test_cache_delete_returns_false_when_key_missing(self):
        """cache_delete returns False when the key does not exist."""
        deleted = cache_delete("never_set_key")
        assert deleted is False

    def test_cache_delete_only_removes_target_key(self):
        """Deleting one key does not affect other keys."""
        cache_set("payment_summary:user_1", {"user": 1})
        cache_set("payment_summary:user_2", {"user": 2})

        cache_delete("payment_summary:user_1")

        assert cache_get("payment_summary:user_1") is None
        assert cache_get("payment_summary:user_2") == {"user": 2}

    def test_cache_invalidation_allows_fresh_data_to_be_stored(self):
        """After invalidation, new data can be stored and retrieved."""
        cache_set("payment_summary:user_5", {"version": 1})
        cache_delete("payment_summary:user_5")

        cache_set("payment_summary:user_5", {"version": 2})
        result = cache_get("payment_summary:user_5")
        assert result == {"version": 2}


class TestPaymentSummaryCachePattern:
    """Tests for the payment_summary cache key pattern used by the endpoint."""

    def test_payment_summary_cache_key_format(self):
        """Cache key follows the f'payment_summary:{user_id}' pattern."""
        user_id = 123
        cache_key = f"payment_summary:{user_id}"

        summary_data = {
            "success": True,
            "all_time": {
                "total_collected": "10000.00",
                "total_links": 20,
                "total_verified": 15,
                "total_expired": 5,
                "conversion_rate": 75.0,
            },
            "this_month": {
                "total_collected": "2000.00",
                "total_links": 4,
                "total_verified": 3,
                "conversion_rate": 75.0,
            },
            "chart_data": {"labels": ["Jan 01"], "dataset": [100.0]},
        }

        cache_set(cache_key, summary_data, ttl=60)
        result = cache_get(cache_key)
        assert result == summary_data

    def test_different_users_have_independent_cache_entries(self):
        """Each user's payment summary is cached independently."""
        for user_id in [1, 2, 3]:
            cache_set(f"payment_summary:{user_id}", {"user_id": user_id})

        for user_id in [1, 2, 3]:
            result = cache_get(f"payment_summary:{user_id}")
            assert result == {"user_id": user_id}

    def test_invalidating_one_user_cache_does_not_affect_others(self):
        """Invalidating one user's cache leaves other users' caches intact."""
        cache_set("payment_summary:user_a", {"data": "a"})
        cache_set("payment_summary:user_b", {"data": "b"})

        # Simulate invalidation for user_a (e.g., after a new transaction)
        cache_delete("payment_summary:user_a")

        assert cache_get("payment_summary:user_a") is None
        assert cache_get("payment_summary:user_b") == {"data": "b"}

    def test_cache_miss_simulates_database_query_path(self):
        """On cache miss, the caller must query the database (None signals miss)."""
        user_id = 99
        cache_key = f"payment_summary:{user_id}"

        # Simulate the endpoint logic: check cache first
        cached = cache_get(cache_key)
        assert cached is None  # Miss — must query DB

        # Simulate DB result being stored
        db_result = {"success": True, "all_time": {"total_links": 0}}
        cache_set(cache_key, db_result, ttl=60)

        # Next call should hit cache
        cached = cache_get(cache_key)
        assert cached == db_result
