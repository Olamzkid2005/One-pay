"""Tests for health check endpoint"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from models.base import Base


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    from models.user import User
    
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
    
    # Register public blueprint
    from blueprints.public import public_bp
    app.register_blueprint(public_bp)
    
    return app.test_client()


def test_health_check_includes_dependencies(client):
    """Test health check includes dependency status checks"""
    response = client.get('/health')
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'database' in data
    assert 'timestamp' in data
    assert 'status' in data


def test_health_check_database_healthy(client):
    """Test health check reports database as healthy"""
    response = client.get('/health')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['database'] == 'ok'
    assert data['status'] == 'healthy'
