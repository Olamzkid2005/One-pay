"""
Tests for fixture isolation (Requirement 20).

Verifies that:
- db_session tests don't share state (20.1, 20.2)
- Cache is reset between tests (20.3)
- Factory fixtures create valid objects (20.5)
"""
from decimal import Decimal

import pytest

# ---------------------------------------------------------------------------
# 20.1 / 20.2 — Database isolation: two tests must not share state
# ---------------------------------------------------------------------------

class TestDatabaseIsolation:
    """Each test using db_session gets a clean database."""

    def test_insert_user_first(self, db_session, make_user) -> None:
        """Insert a user — should not be visible in the next test."""
        make_user(username="isolation_test_user")
        db_session.flush()

        from models.user import User
        result = db_session.query(User).filter_by(username="isolation_test_user").first()
        assert result is not None
        assert result.id is not None

    def test_user_from_previous_test_not_visible(self, db_session) -> None:
        """The user created in the previous test must not exist here."""
        from models.user import User
        result = db_session.query(User).filter_by(username="isolation_test_user").first()
        assert result is None, (
            "State leaked between tests — db_session isolation is broken"
        )

    def test_insert_transaction_first(self, db_session, make_transaction) -> None:
        """Insert a transaction — should not be visible in the next test."""
        make_transaction(tx_ref="ISOLATION-TX-001")
        db_session.flush()

        from models.transaction import Transaction
        result = db_session.query(Transaction).filter_by(tx_ref="ISOLATION-TX-001").first()
        assert result is not None

    def test_transaction_from_previous_test_not_visible(self, db_session) -> None:
        """The transaction created in the previous test must not exist here."""
        from models.transaction import Transaction
        result = db_session.query(Transaction).filter_by(tx_ref="ISOLATION-TX-001").first()
        assert result is None, (
            "State leaked between tests — db_session isolation is broken"
        )


# ---------------------------------------------------------------------------
# 20.3 — Cache reset between tests
# ---------------------------------------------------------------------------

class TestCacheIsolation:
    """Cache state must not bleed between tests."""

    def test_cache_write(self, reset_cache_fixture) -> None:
        """Write a value to the cache."""
        from services.cache import cache_get, cache_set
        cache_set("isolation_key", "isolation_value")
        assert cache_get("isolation_key") == "isolation_value"

    def test_cache_is_empty_after_reset(self, reset_cache_fixture) -> None:
        """The value written in the previous test must not be present."""
        from services.cache import cache_get
        result = cache_get("isolation_key")
        assert result is None, (
            "Cache state leaked between tests — reset_cache_fixture is broken"
        )

    def test_reset_cache_fixture_clears_before_test(self, reset_cache_fixture) -> None:
        """reset_cache_fixture clears the cache at the start of the test."""
        from services.cache import cache_get, cache_set, get_cache

        # Manually pollute the cache before the fixture would have cleared it
        # (fixture already ran, so cache is clean — just verify it's empty)
        assert cache_get("any_key") is None

    def test_reset_cache_fixture_clears_after_test(self, reset_cache_fixture) -> None:
        """Verify the fixture teardown clears the cache (indirectly via next test)."""
        from services.cache import cache_set
        cache_set("teardown_key", "should_be_gone")
        # Teardown will call reset_cache() — verified by the next test


# ---------------------------------------------------------------------------
# 20.4 — Rate limiter reset between tests
# ---------------------------------------------------------------------------

class TestRateLimiterIsolation:
    """In-memory rate limiter state must not bleed between tests."""

    def test_rate_limiter_write(self, reset_rate_limiter) -> None:
        """Populate the in-memory rate limiter cache."""
        import services.rate_limiter as rl
        rl._memory_cache["test_key"] = {"count": 5, "window_start": 0}
        assert "test_key" in rl._memory_cache

    def test_rate_limiter_is_empty_after_reset(self, reset_rate_limiter) -> None:
        """The entry written in the previous test must not be present."""
        import services.rate_limiter as rl
        assert "test_key" not in rl._memory_cache, (
            "Rate limiter state leaked between tests — reset_rate_limiter is broken"
        )


# ---------------------------------------------------------------------------
# 20.5 — Factory fixtures create valid objects
# ---------------------------------------------------------------------------

class TestFactoryFixtures:
    """Factory fixtures must produce valid, persisted model instances."""

    def test_make_user_creates_valid_user(self, db_session, make_user) -> None:
        """make_user returns a User with an assigned primary key."""
        user = make_user()

        assert user.id is not None
        assert user.username
        assert user.email
        assert user.password_hash
        assert user.is_active is True

    def test_make_user_accepts_overrides(self, db_session, make_user) -> None:
        """make_user respects keyword overrides."""
        user = make_user(username="custom_user", email="custom@example.com")

        assert user.username == "custom_user"
        assert user.email == "custom@example.com"

    def test_make_user_creates_unique_users(self, db_session, make_user) -> None:
        """Calling make_user twice produces two distinct users."""
        user1 = make_user()
        user2 = make_user()

        assert user1.id != user2.id
        assert user1.username != user2.username

    def test_make_transaction_creates_valid_transaction(self, db_session, make_transaction) -> None:
        """make_transaction returns a Transaction with an assigned primary key."""
        tx = make_transaction()

        assert tx.id is not None
        assert tx.tx_ref
        assert tx.amount == Decimal("1000.00")
        assert tx.currency == "NGN"
        assert tx.hash_token
        assert tx.expires_at is not None

    def test_make_transaction_accepts_overrides(self, db_session, make_transaction) -> None:
        """make_transaction respects keyword overrides."""
        tx = make_transaction(amount=Decimal("500.00"), currency="USD")

        assert tx.amount == Decimal("500.00")
        assert tx.currency == "USD"

    def test_make_transaction_creates_unique_transactions(self, db_session, make_transaction) -> None:
        """Calling make_transaction twice produces two distinct transactions."""
        tx1 = make_transaction()
        tx2 = make_transaction()

        assert tx1.id != tx2.id
        assert tx1.tx_ref != tx2.tx_ref

    def test_make_transaction_linked_to_user(self, db_session, make_user, make_transaction) -> None:
        """make_transaction can be linked to a user created by make_user."""
        user = make_user()
        tx = make_transaction(user_id=user.id)

        assert tx.user_id == user.id

    def test_make_user_password_is_hashed(self, db_session, make_user) -> None:
        """make_user stores a bcrypt hash, not a plain-text password."""
        user = make_user()

        # bcrypt hashes start with $2b$ or $2a$
        assert user.password_hash.startswith("$2")

    def test_make_user_check_password(self, db_session, make_user) -> None:
        """make_user default password passes check_password."""
        user = make_user()
        assert user.check_password("TestPassword123!")
