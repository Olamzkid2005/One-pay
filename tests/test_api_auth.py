"""Tests for API key authentication functionality"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from models.base import Base


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    from models.user import User  # Import to register with Base
    from models.api_key import APIKey  # Import to register with Base
    
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


def test_api_key_model_creation():
    """Test that APIKey model can be created with required fields"""
    from models.api_key import APIKey
    
    key = APIKey(
        user_id=1,
        key_hash="abc123",
        key_prefix="onepay_live_abc12345",
        name="Test Key"
    )
    assert key.user_id == 1
    assert key.key_hash == "abc123"
    assert key.key_prefix == "onepay_live_abc12345"
    assert key.name == "Test Key"



def test_generate_api_key_format():
    """Test that generated API keys have the correct format"""
    from core.api_auth import generate_api_key
    
    key = generate_api_key()
    assert key.startswith("onepay_live_")
    assert len(key) == 76  # onepay_live_ (12) + 64 hex chars
    
    # Verify it's actually hex
    hex_part = key[12:]
    assert all(c in '0123456789abcdef' for c in hex_part)



def test_hash_api_key():
    """Test that API key hashing is consistent and secure"""
    from core.api_auth import hash_api_key
    
    key = "onepay_live_abc123"
    hash1 = hash_api_key(key)
    hash2 = hash_api_key(key)
    
    assert hash1 == hash2  # Consistent
    assert len(hash1) == 64  # SHA256 hex
    assert hash1 != key  # Actually hashed
    assert all(c in '0123456789abcdef' for c in hash1)  # Valid hex



def test_validate_api_key_valid(db_session, monkeypatch):
    """Test that valid API keys are accepted"""
    from core.api_auth import generate_api_key, hash_api_key, validate_api_key
    from models.api_key import APIKey
    from contextlib import contextmanager
    
    # Create test key
    key = generate_api_key()
    api_key = APIKey(
        user_id=1,
        key_hash=hash_api_key(key),
        key_prefix=key[:20],
        is_active=True
    )
    db_session.add(api_key)
    db_session.commit()
    
    # Mock get_db to return our test session
    @contextmanager
    def mock_get_db():
        yield db_session
    
    monkeypatch.setattr('core.api_auth.get_db', mock_get_db)
    
    # Validate
    is_valid, user_id = validate_api_key(key)
    assert is_valid is True
    assert user_id == 1


def test_validate_api_key_invalid():
    """Test that invalid API keys are rejected"""
    from core.api_auth import validate_api_key
    
    # Invalid format
    is_valid, user_id = validate_api_key("invalid_key")
    assert is_valid is False
    assert user_id is None
    
    # Non-existent key
    is_valid, user_id = validate_api_key("onepay_live_" + "0" * 64)
    assert is_valid is False
    assert user_id is None


def test_validate_api_key_inactive(db_session, monkeypatch):
    """Test that inactive API keys are rejected"""
    from core.api_auth import generate_api_key, hash_api_key, validate_api_key
    from models.api_key import APIKey
    from contextlib import contextmanager
    
    # Create inactive key
    key = generate_api_key()
    api_key = APIKey(
        user_id=1,
        key_hash=hash_api_key(key),
        key_prefix=key[:20],
        is_active=False
    )
    db_session.add(api_key)
    db_session.commit()
    
    # Mock get_db to return our test session
    @contextmanager
    def mock_get_db():
        yield db_session
    
    monkeypatch.setattr('core.api_auth.get_db', mock_get_db)
    
    # Validate
    is_valid, user_id = validate_api_key(key)
    assert is_valid is False
    assert user_id is None



def test_is_api_key_authenticated():
    """Test the is_api_key_authenticated helper function"""
    from core.api_auth import is_api_key_authenticated
    from flask import Flask, g
    
    app = Flask(__name__)
    
    with app.app_context():
        # No flag set
        assert is_api_key_authenticated() is False
        
        # Flag set to True
        g.api_key_authenticated = True
        assert is_api_key_authenticated() is True
        
        # Flag set to False
        g.api_key_authenticated = False
        assert is_api_key_authenticated() is False
