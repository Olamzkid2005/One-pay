# tests/test_api_key_endpoints.py
"""Tests for API key management endpoints"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from models.base import Base
from models.api_key import APIKey
from core.api_auth import hash_api_key


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing - fresh for each test."""
    from models.user import User
    from models.api_key import APIKey  # Import to ensure table is registered
    
    # Use simple :memory: which creates a new database for each connection
    engine = create_engine('sqlite:///:memory:', connect_args={"check_same_thread": False})
    
    # Enable foreign key constraints in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    # Clean up
    session.close()
    engine.dispose()


@pytest.fixture
def auth_user(db_session):
    """Create authenticated test user"""
    from models.user import User
    
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        password_hash="dummy_hash"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def client(db_session, monkeypatch):
    """Create Flask test client with authenticated session"""
    from flask import Flask
    from contextlib import contextmanager
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['TESTING'] = True
    
    # Mock get_db to return our test session (same instance every time)
    @contextmanager
    def mock_get_db():
        try:
            yield db_session
            db_session.commit()  # Commit changes made in the endpoint
        except Exception:
            db_session.rollback()
            raise
    
    monkeypatch.setattr('database.get_db', mock_get_db)
    
    # Register blueprints
    from blueprints.api_keys import api_keys_bp
    app.register_blueprint(api_keys_bp)
    
    client = app.test_client()
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_id'] = 1
    
    return client


def test_list_api_keys(client, db_session, auth_user):
    """Test listing API keys for authenticated user"""
    # Create test keys
    key1 = APIKey(
        user_id=auth_user.id,
        key_hash=hash_api_key("test1"),
        key_prefix="onepay_live_test1",
        name="Key 1"
    )
    key2 = APIKey(
        user_id=auth_user.id,
        key_hash=hash_api_key("test2"),
        key_prefix="onepay_live_test2",
        name="Key 2"
    )
    db_session.add(key1)
    db_session.add(key2)
    db_session.commit()
    
    response = client.get('/api/api-keys')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert len(data['api_keys']) == 2
    assert data['api_keys'][0]['name'] == 'Key 1'
    assert data['api_keys'][1]['name'] == 'Key 2'


def test_list_api_keys_unauthenticated(db_session, monkeypatch):
    """Test listing API keys without authentication"""
    from flask import Flask
    from contextlib import contextmanager
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['TESTING'] = True
    
    # Mock get_db
    @contextmanager
    def mock_get_db():
        yield db_session
    
    monkeypatch.setattr('database.get_db', mock_get_db)
    
    # Register blueprint
    from blueprints.api_keys import api_keys_bp
    app.register_blueprint(api_keys_bp)
    
    client = app.test_client()
    # No session setup - unauthenticated
    
    response = client.get('/api/api-keys')
    assert response.status_code == 401


# TODO: Add test for user isolation once fixture issues are resolved
# def test_list_api_keys_only_shows_own_keys(client, db_session, auth_user):
#     """Test that users only see their own API keys"""
#     pass
