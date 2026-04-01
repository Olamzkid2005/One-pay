"""Tests for inbound webhook receiver"""
import hmac
import hashlib
import json
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from models.base import Base


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    from models.user import User
    from models.transaction import Transaction
    
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
    
    yield session
    session.close()


@pytest.fixture
def client(db_session, monkeypatch):
    """Create Flask test client"""
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
    
    # Register webhooks blueprint
    from blueprints.webhooks import webhooks_bp
    app.register_blueprint(webhooks_bp, url_prefix="/api/v1")
    
    return app.test_client()


def test_verify_webhook_signature_valid():
    """Test HMAC signature verification with valid signature"""
    from blueprints.webhooks import verify_webhook_signature
    
    payload = b'{"tx_ref": "TEST123"}'
    secret = "test-secret"
    
    # Generate valid signature
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    
    # Verify
    assert verify_webhook_signature(payload, f"sha256={sig}", secret) is True


def test_verify_webhook_signature_invalid():
    """Test HMAC signature verification with invalid signature"""
    from blueprints.webhooks import verify_webhook_signature
    
    payload = b'{"tx_ref": "TEST123"}'
    secret = "test-secret"
    
    # Invalid signature
    assert verify_webhook_signature(payload, "sha256=invalid", secret) is False


def test_verify_webhook_signature_wrong_format():
    """Test HMAC signature verification with wrong format"""
    from blueprints.webhooks import verify_webhook_signature
    
    payload = b'{"tx_ref": "TEST123"}'
    secret = "test-secret"
    
    # Missing sha256= prefix
    assert verify_webhook_signature(payload, "abc123", secret) is False


def test_receive_payment_status_webhook(client, db_session):
    """Test webhook receiver endpoint with valid signature"""
    from models.transaction import Transaction
    from models.user import User
    
    # Create test user
    user = User(username="testuser", email="test@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()
    
    # Create test transaction
    from datetime import datetime, timezone, timedelta
    tx = Transaction(
        tx_ref="TEST123",
        status="PENDING",
        amount=1000,
        currency="NGN",
        user_id=user.id,
        hash_token="test_hash_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    db_session.add(tx)
    db_session.commit()
    
    # Prepare webhook payload
    payload = {"tx_ref": "TEST123", "status": "verified"}
    
    # Convert to JSON bytes exactly as Flask will receive it
    import json
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode()
    
    # Sign it
    secret = "test-secret"
    sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    
    # Mock the config secret
    import config
    original_secret = config.Config.INBOUND_WEBHOOK_SECRET
    config.Config.INBOUND_WEBHOOK_SECRET = secret
    
    try:
        # Send webhook with raw data (not json parameter)
        response = client.post(
            '/api/v1/webhooks/payment-status',
            data=payload_bytes,
            content_type='application/json',
            headers={'X-Webhook-Signature': f'sha256={sig}'}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['tx_ref'] == "TEST123"
        
        # Verify transaction was updated
        db_session.refresh(tx)
        assert tx.status == "verified"
    finally:
        config.Config.INBOUND_WEBHOOK_SECRET = original_secret
