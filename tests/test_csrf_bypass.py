"""Tests for CSRF bypass with API key authentication"""
import pytest
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from models.base import Base


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    from models.user import User
    from models.api_key import APIKey
    
    engine = create_engine('sqlite:///:memory:')
    
    # Enable foreign key constraints in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create a test user
    test_user = User(id=1, username="testuser", email="test@example.com", password_hash="dummy_hash")
    session.add(test_user)
    session.commit()
    
    yield session
    session.close()


def test_current_user_id_from_api_key(db_session, monkeypatch):
    """Test that current_user_id returns user from API key"""
    from core.api_auth import generate_api_key, hash_api_key
    from models.api_key import APIKey
    from core.auth import current_user_id
    from flask import Flask, g
    
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


def test_current_user_id_from_session():
    """Test that current_user_id returns user from session"""
    from core.auth import current_user_id
    from flask import Flask, session
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'
    
    with app.test_request_context():
        # Set user_id in session
        session['user_id'] = 99
        
        user_id = current_user_id()
        assert user_id == 99


def test_current_user_id_no_auth():
    """Test that current_user_id returns None when not authenticated"""
    from core.auth import current_user_id
    from flask import Flask
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'
    
    with app.test_request_context():
        user_id = current_user_id()
        assert user_id is None
