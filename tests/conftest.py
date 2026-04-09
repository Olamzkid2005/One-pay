"""
Pytest configuration for OnePay tests.
Sets up the Python path to include the project root and provides
shared fixtures for test isolation.
"""
import sys
import os
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.base import Base


# ---------------------------------------------------------------------------
# Set testing environment globally - MUST run before any imports
# ---------------------------------------------------------------------------

# Set APP_ENV immediately at module level (before any app imports)
os.environ['APP_ENV'] = 'testing'
os.environ['TESTING'] = 'true'

# Set minimal required config for tests
os.environ.setdefault('SECRET_KEY', 'test-secret-key-32-chars-long-12345')
os.environ.setdefault('HMAC_SECRET', 'test-hmac-secret-32-chars-long-12345')
os.environ.setdefault('INBOUND_WEBHOOK_SECRET', 'test-webhook-secret-32-chars-long-1')
os.environ.setdefault('KORAPAY_SECRET_KEY', 'test-korapay-key')
os.environ.setdefault('KORAPAY_WEBHOOK_SECRET', 'test-korapay-webhook-32-chars-long')


@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """Ensure testing environment is set for all tests."""
    # Already set at module level, but keep fixture for explicit dependency
    yield
    # Don't cleanup - other tests may still need these


# ---------------------------------------------------------------------------
# Global test isolation - runs before/after EVERY test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolate_tests(monkeypatch):
    """
    Ensure complete isolation between tests.
    
    This fixture runs automatically for every test and:
    - Resets rate limiter cache
    - Clears any global state
    - Cleans up mocks
    - Resets Flask app state
    - Ensures clean environment
    """
    # Before test: Clear rate limiter cache
    try:
        import services.rate_limiter as rl
        rl._memory_cache.clear()
    except Exception:
        pass
    
    # Before test: Clear cache
    try:
        from services.cache import reset_cache
        reset_cache()
    except Exception:
        pass
    
    # Before test: Reset any module-level state
    try:
        # Clear Flask's app context stack
        from flask import _app_ctx_stack
        while _app_ctx_stack.top is not None:
            _app_ctx_stack.pop()
    except Exception:
        pass
    
    # Before test: Clear any request context
    try:
        from flask import _request_ctx_stack
        while _request_ctx_stack.top is not None:
            _request_ctx_stack.pop()
    except Exception:
        pass
    
    yield
    
    # After test: Clean up again
    try:
        import services.rate_limiter as rl
        rl._memory_cache.clear()
    except Exception:
        pass
    
    try:
        from services.cache import reset_cache
        reset_cache()
    except Exception:
        pass
    
    # After test: Clear Flask contexts
    try:
        from flask import _app_ctx_stack
        while _app_ctx_stack.top is not None:
            _app_ctx_stack.pop()
    except Exception:
        pass
    
    try:
        from flask import _request_ctx_stack
        while _request_ctx_stack.top is not None:
            _request_ctx_stack.pop()
    except Exception:
        pass
    
    # After test: Stop any mock patches that weren't cleaned up
    try:
        patch.stopall()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Flask app fixture with proper cleanup and isolation
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """
    Create a Flask app instance with proper cleanup and isolation.
    
    This fixture ensures:
    - Fresh app instance for each test
    - Background threads are stopped after test
    - App context is properly cleaned up
    - No state leaks between tests
    """
    # Import here to avoid circular imports
    from app import create_app
    
    # Create fresh app instance
    test_app = create_app()
    test_app.config['TESTING'] = True
    test_app.config['WTF_CSRF_ENABLED'] = False
    
    # Push app context for the test
    ctx = test_app.app_context()
    ctx.push()
    
    yield test_app
    
    # Cleanup: Signal background threads to stop
    if hasattr(test_app, '_shutdown_event'):
        test_app._shutdown_event.set()
        # Give threads a moment to stop
        import time
        time.sleep(0.1)
    
    # Cleanup: Pop app context
    try:
        ctx.pop()
    except Exception:
        pass
    
    # Cleanup: Clear any remaining contexts
    try:
        from flask import _app_ctx_stack
        while _app_ctx_stack.top is not None:
            _app_ctx_stack.pop()
    except Exception:
        pass


@pytest.fixture
def client(app):
    """Create Flask test client from app fixture with proper context."""
    with app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# 24.1 — Isolated database fixture (Requirement 20.1, 20.2)
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    """
    Provide an isolated SQLAlchemy session for each test.

    Creates a fresh in-memory SQLite database, builds all tables,
    yields the session, then tears down — so every test starts clean.
    
    Uses nested transactions for complete isolation.
    """
    from sqlalchemy import event

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    
    # Start a transaction
    session.begin_nested()
    
    try:
        yield session
    finally:
        # Always rollback to ensure no state leaks
        try:
            session.rollback()
        except Exception:
            pass
        
        try:
            session.close()
        except Exception:
            pass
        
        try:
            Base.metadata.drop_all(engine)
        except Exception:
            pass
        
        try:
            engine.dispose()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 24.2 — Cache reset fixture (Requirement 20.3)
# ---------------------------------------------------------------------------

@pytest.fixture
def reset_cache_fixture():
    """
    Reset the global cache before and after each test.

    Not autouse — apply explicitly to tests that exercise caching.
    """
    from services.cache import reset_cache
    reset_cache()
    yield
    reset_cache()


# ---------------------------------------------------------------------------
# 24.3 — Rate limiter reset fixture (Requirement 20.4)
# ---------------------------------------------------------------------------

@pytest.fixture
def reset_rate_limiter():
    """
    Clear the in-memory rate limiter fallback cache between tests.
    """
    import services.rate_limiter as rl
    rl._memory_cache.clear()
    yield
    rl._memory_cache.clear()


# ---------------------------------------------------------------------------
# 24.3.5 — Config reload fixture (for tests that monkeypatch env vars)
# ---------------------------------------------------------------------------

@pytest.fixture
def reload_config():
    """
    Reload configuration after monkeypatching environment variables.
    
    Usage::
        def test_something(monkeypatch, reload_config):
            monkeypatch.setenv("INBOUND_WEBHOOK_SECRET", "test_secret")
            reload_config()  # Now Config.INBOUND_WEBHOOK_SECRET has the new value
    """
    from config import Config
    
    def _reload():
        Config.reload()
    
    return _reload


# ---------------------------------------------------------------------------
# 24.4 — Factory fixtures (Requirement 20.5)
# ---------------------------------------------------------------------------

@pytest.fixture
def make_user(db_session):
    """
    Factory fixture that creates and persists a User with sensible defaults.

    Usage::

        def test_something(make_user):
            user = make_user(username="alice")
    """
    from models.user import User

    def _factory(**kwargs):
        defaults = {
            "username": f"testuser_{secrets.token_hex(4)}",
            "email": f"test_{secrets.token_hex(4)}@example.com",
            "is_active": True,
            "auth_provider": "traditional",
        }
        defaults.update(kwargs)
        user = User(**defaults)
        if not user.password_hash:
            user.set_password("TestPassword123!")
        db_session.add(user)
        db_session.flush()
        return user

    return _factory


@pytest.fixture
def make_transaction(db_session):
    """
    Factory fixture that creates and persists a Transaction with sensible defaults.

    Usage::

        def test_something(make_transaction):
            tx = make_transaction(amount=Decimal("500.00"))
    """
    from models.transaction import Transaction, TransactionStatus

    def _factory(**kwargs):
        defaults = {
            "tx_ref": f"TEST-{secrets.token_hex(6).upper()}",
            "amount": Decimal("1000.00"),
            "currency": "NGN",
            "hash_token": secrets.token_hex(32),
            "status": TransactionStatus.PENDING,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        defaults.update(kwargs)
        tx = Transaction(**defaults)
        db_session.add(tx)
        db_session.flush()
        return tx

    return _factory
