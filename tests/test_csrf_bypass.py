"""Tests for CSRF bypass with API key authentication"""
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models.base import Base


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    from models.api_key import APIKey
    from models.user import User

    engine = create_engine('sqlite:///:memory:')

    # Enable foreign key constraints in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Create a test user
    test_user = User(id=1, username="testuser", email="test@example.com", password_hash="dummy_hash")
    session.add(test_user)
    session.commit()

    yield session
    session.close()


def test_current_user_id_from_api_key(db_session, monkeypatch) -> None:
    """Test that current_user_id returns user from API key"""
    from flask import Flask, g

    from core.api_auth import generate_api_key, hash_api_key
    from core.auth import current_user_id
    from models.api_key import APIKey

    # Create test key for user_id 1 (created in fixture)
    key = generate_api_key()
    api_key = APIKey(
        user_id=1,
        key_hash=hash_api_key(key),
        key_prefix=key[:20],
        is_active=True
    )
    db_session.add(api_key)
    db_session.commit()

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'

    with app.test_request_context():
        # Simulate API key authentication
        g.api_key_authenticated = True
        g.user_id = 1

        user_id = current_user_id()
        assert user_id == 1


def test_current_user_id_from_session() -> None:
    """Test that current_user_id returns user from session"""
    from flask import Flask, session

    from core.auth import current_user_id

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'

    with app.test_request_context():
        # Set user_id in session
        session['user_id'] = 99

        user_id = current_user_id()
        assert user_id == 99


def test_current_user_id_no_auth() -> None:
    """Test that current_user_id returns None when not authenticated"""
    from flask import Flask

    from core.auth import current_user_id

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'

    with app.test_request_context():
        user_id = current_user_id()
        assert user_id is None
