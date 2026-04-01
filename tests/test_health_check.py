"""Tests for health check endpoint"""
import pytest


def test_health_check_includes_dependencies():
    """Health check should include dependency status checks"""
    from flask import Flask
    from blueprints.public import public_bp
    
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(public_bp)
    
    client = app.test_client()
    response = client.get('/health')
    
    # Should return 200 or 503 depending on critical services
    assert response.status_code in [200, 503]
    data = response.get_json()
    assert 'checks' in data
    assert 'database' in data['checks']
    assert 'timestamp' in data
    assert 'version' in data
    assert 'status' in data
    
    # Verify checks structure
    assert isinstance(data['checks'], dict)
    assert isinstance(data['checks']['database'], bool)
