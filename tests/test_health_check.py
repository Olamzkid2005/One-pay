"""Tests for health check endpoint"""
import pytest
from flask import Flask


@pytest.fixture
def client():
    """Create Flask test client"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    # Register public blueprint
    from blueprints.public import public_bp
    app.register_blueprint(public_bp)
    
    return app.test_client()


def test_health_check_basic_structure(client):
    """Test health check returns expected structure"""
    response = client.get('/health')
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'status' in data
    assert 'database' in data
    assert 'timestamp' in data
    assert 'app' in data
    assert data['app'] == 'OnePay'


def test_health_check_database_status(client):
    """Test health check includes database status"""
    response = client.get('/health')
    
    assert response.status_code == 200
    data = response.get_json()
    # Database should be 'ok' or 'error'
    assert data['database'] in ['ok', 'error']
    # Status should be 'healthy' or 'degraded'
    assert data['status'] in ['healthy', 'degraded']
