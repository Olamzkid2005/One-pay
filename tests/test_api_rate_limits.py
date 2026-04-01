"""Tests for API rate limiting"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from models.base import Base


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    from models.user import User
    from models.api_key import APIKey
    from models.rate_limit import RateLimit
    
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
    
    # Mock get_db to return our test session
    @contextmanager
    def mock_get_db():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
    
    monkeypatch.setattr('database.get_db', mock_get_db)
    
    # Register blueprints
    from blueprints.payments import payments_bp
    app.register_blueprint(payments_bp, url_prefix="/api/v1")
    
    # Add API key middleware
    from core.api_auth import validate_api_key
    from flask import request, g
    
    @app.before_request
    def authenticate_api_key():
        """Check for API key in Authorization header"""
        auth_header = request.headers.get('Authorization', '')
        
        if auth_header.startswith('Bearer '):
            api_key = auth_header[7:]
            is_valid, user_id = validate_api_key(api_key)
            
            if is_valid:
                g.api_key_authenticated = True
                g.user_id = user_id
                g.api_key = api_key
    
    client = app.test_client()
    
    # Set up authenticated session
    with client.session_transaction() as sess:
        sess['user_id'] = 1
    
    return client


def test_api_rate_limit_higher_than_web(client, db_session, auth_user, monkeypatch):
    """API clients should have higher rate limits than web clients"""
    from core.api_auth import generate_api_key, hash_api_key
    from models.api_key import APIKey
    from contextlib import contextmanager
    
    # Mock get_db for validate_api_key
    @contextmanager
    def mock_get_db():
        yield db_session
    
    monkeypatch.setattr('core.api_auth.get_db', mock_get_db)
    
    # Create API key
    key = generate_api_key()
    api_key = APIKey(user_id=auth_user.id, key_hash=hash_api_key(key), key_prefix=key[:20], is_active=True)
    db_session.add(api_key)
    db_session.commit()
    
    # Make 11 requests (web limit is 10)
    for i in range(11):
        response = client.post(
            '/api/v1/payments/link',
            json={'amount': '1000.00', 'currency': 'NGN'},
            headers={'Authorization': f'Bearer {key}'}
        )
    
    # 11th request should succeed (API limit is 100)
    assert response.status_code != 429
