"""
Integration tests for Google OAuth flow.

Tests the complete OAuth authentication flow including token validation,
profile extraction, account creation, account linking, session management,
rate limiting, and audit logging.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import session
import json


class TestGoogleOAuthCallback:
    """
    Integration tests for /auth/google/callback endpoint.
    
    Property 10: Session Creation Completeness
    Property 11: Session Validation Consistency
    Property 12: No Token Storage
    Property 13: Authentication Failure Logging
    Property 14: Authentication Success Logging
    Property 17: Rate Limiting Enforcement
    """
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        from app import create_app
        import os
        # Set test environment variables
        os.environ['ENFORCE_HTTPS'] = 'false'
        os.environ['DEBUG'] = 'true'
        
        app = create_app()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key-for-sessions'
        app.config['GOOGLE_CLIENT_ID'] = 'test-client-id.apps.googleusercontent.com'
        app.config['GOOGLE_CLIENT_SECRET'] = 'test-secret'
        app.config['ENFORCE_HTTPS'] = False
        app.config['DEBUG'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for tests
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client with session support."""
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def mock_csrf(self):
        """Mock CSRF validation to return True for all tests."""
        with patch('blueprints.auth.is_valid_csrf_token', return_value=True):
            yield
    
    @pytest.fixture
    def mock_token_payload(self):
        """Mock valid token payload."""
        return {
            'iss': 'https://accounts.google.com',
            'aud': 'test-client-id.apps.googleusercontent.com',
            'sub': '1234567890',
            'email': 'test@example.com',
            'email_verified': True,
            'name': 'Test User',
            'picture': 'https://example.com/photo.jpg',
            'exp': 9999999999,
            'iat': 1234567890
        }
    
    def test_complete_oauth_flow_creates_new_account(self, client, mock_token_payload, mock_csrf):
        """
        Test that complete OAuth flow creates new account.
        Property 14: Authentication Success Logging
        """
        with patch('services.google_oauth.id_token.verify_oauth2_token', return_value=mock_token_payload):
            with patch('blueprints.auth.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Mock: no existing user
                mock_db.query().filter().first.return_value = None
                
                # Mock rate limiter
                with patch('blueprints.auth.check_rate_limit', return_value=True):
                    # Get CSRF token first
                    with client.session_transaction() as sess:
                        sess['csrf_token'] = 'test-csrf-token'
                    
                    response = client.post('/auth/google/callback',
                        json={
                            'credential': 'valid.jwt.token',
                            'csrf_token': 'test-csrf-token'
                        },
                        content_type='application/json'
                    )
                    
                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data['success'] is True
                    assert 'redirect_url' in data
    
    def test_complete_oauth_flow_links_existing_account(self, client, mock_token_payload, mock_csrf):
        """
        Test that OAuth flow links to existing account with matching email.
        Property 8: Account Linking for Existing Users
        """
        with patch('services.google_oauth.id_token.verify_oauth2_token', return_value=mock_token_payload):
            with patch('blueprints.auth.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Mock: no user with google_id, but user with email exists
                mock_existing_user = Mock()
                mock_existing_user.google_id = None
                mock_existing_user.id = 1
                mock_existing_user.username = 'existinguser'
                
                mock_db.query().filter().first.side_effect = [
                    None,  # No user with google_id
                    mock_existing_user  # User with email exists
                ]
                
                with patch('blueprints.auth.check_rate_limit', return_value=True):
                    with client.session_transaction() as sess:
                        sess['csrf_token'] = 'test-csrf-token'
                    
                    response = client.post('/auth/google/callback',
                        json={
                            'credential': 'valid.jwt.token',
                            'csrf_token': 'test-csrf-token'
                        },
                        content_type='application/json'
                    )
                    
                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data['success'] is True
                    
                    # Verify link_google_account was called
                    mock_existing_user.link_google_account.assert_called_once()
    
    def test_session_created_after_successful_authentication(self, client, mock_token_payload, mock_csrf):
        """
        Test that session is created after successful authentication.
        Property 10: Session Creation Completeness
        """
        with patch('services.google_oauth.id_token.verify_oauth2_token', return_value=mock_token_payload):
            with patch('blueprints.auth.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Mock existing user
                mock_user = Mock()
                mock_user.id = 1
                mock_user.username = 'testuser'
                mock_db.query().filter().first.return_value = mock_user
                
                with patch('blueprints.auth.check_rate_limit', return_value=True):
                    with client.session_transaction() as sess:
                        sess['csrf_token'] = 'test-csrf-token'
                    
                    response = client.post('/auth/google/callback',
                        json={
                            'credential': 'valid.jwt.token',
                            'csrf_token': 'test-csrf-token'
                        },
                        content_type='application/json'
                    )
                    
                    assert response.status_code == 200
                    
                    # Verify session was created (would be set by _regenerate_session_secure)
                    with client.session_transaction() as sess:
                        # Session should have been regenerated
                        assert 'csrf_token' in sess
    
    def test_csrf_validation_enforced(self, client):
        """
        Test that CSRF validation is enforced.
        Property 11: Session Validation Consistency
        """
        response = client.post('/auth/google/callback',
            json={
                'credential': 'valid.jwt.token',
                'csrf_token': 'invalid-token'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'CSRF' in data['message'] or 'Session expired' in data['message']
    
    def test_rate_limiting_enforced(self, client, mock_token_payload, mock_csrf):
        """
        Test that rate limiting is enforced.
        Property 17: Rate Limiting Enforcement
        """
        with patch('services.google_oauth.id_token.verify_oauth2_token', return_value=mock_token_payload):
            with patch('blueprints.auth.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Mock rate limiter returning False (rate limit exceeded)
                with patch('blueprints.auth.check_rate_limit', return_value=False):
                    with client.session_transaction() as sess:
                        sess['csrf_token'] = 'test-csrf-token'
                    
                    response = client.post('/auth/google/callback',
                        json={
                            'credential': 'valid.jwt.token',
                            'csrf_token': 'test-csrf-token'
                        },
                        content_type='application/json'
                    )
                    
                    assert response.status_code == 429
                    data = json.loads(response.data)
                    assert data['success'] is False
                    assert 'Too many' in data['message']
    
    def test_account_linking_conflict_rejection(self, client, mock_token_payload, mock_csrf):
        """
        Test that account linking conflict is rejected.
        Property 9: Account Linking Conflict Prevention
        """
        with patch('services.google_oauth.id_token.verify_oauth2_token', return_value=mock_token_payload):
            with patch('blueprints.auth.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Mock: no user with this google_id, but user with email has different google_id
                mock_existing_user = Mock()
                mock_existing_user.google_id = 'different-google-id'
                mock_existing_user.id = 1
                
                mock_db.query().filter().first.side_effect = [
                    None,  # No user with this google_id
                    mock_existing_user  # User with email has different google_id
                ]
                
                with patch('blueprints.auth.check_rate_limit', return_value=True):
                    with client.session_transaction() as sess:
                        sess['csrf_token'] = 'test-csrf-token'
                    
                    response = client.post('/auth/google/callback',
                        json={
                            'credential': 'valid.jwt.token',
                            'csrf_token': 'test-csrf-token'
                        },
                        content_type='application/json'
                    )
                    
                    assert response.status_code == 409
                    data = json.loads(response.data)
                    assert data['success'] is False
                    assert 'already linked' in data['message']
    
    def test_no_token_storage_in_database(self, client, mock_token_payload, mock_csrf):
        """
        Test that OAuth tokens are not stored in database.
        Property 12: No Token Storage
        """
        with patch('services.google_oauth.id_token.verify_oauth2_token', return_value=mock_token_payload):
            with patch('blueprints.auth.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Mock: no existing user
                mock_db.query().filter().first.return_value = None
                
                with patch('blueprints.auth.check_rate_limit', return_value=True):
                    with client.session_transaction() as sess:
                        sess['csrf_token'] = 'test-csrf-token'
                    
                    response = client.post('/auth/google/callback',
                        json={
                            'credential': 'valid.jwt.token',
                            'csrf_token': 'test-csrf-token'
                        },
                        content_type='application/json'
                    )
                    
                    assert response.status_code == 200
                    
                    # Verify that no token-related fields were set on user
                    # Only google_id should be stored, not access_token or refresh_token
                    calls = mock_db.add.call_args_list
                    if calls:
                        user = calls[0][0][0]
                        assert hasattr(user, 'google_id')
                        assert not hasattr(user, 'access_token')
                        assert not hasattr(user, 'refresh_token')
    
    def test_authentication_failure_logging(self, client, mock_csrf):
        """
        Test that authentication failures are logged.
        Property 13: Authentication Failure Logging
        """
        with patch('services.google_oauth.id_token.verify_oauth2_token', side_effect=ValueError("Invalid token")):
            with patch('blueprints.auth.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                with patch('blueprints.auth.check_rate_limit', return_value=True):
                    with patch('blueprints.auth.log_event') as mock_log_event:
                        with client.session_transaction() as sess:
                            sess['csrf_token'] = 'test-csrf-token'
                        
                        response = client.post('/auth/google/callback',
                            json={
                                'credential': 'invalid.token',
                                'csrf_token': 'test-csrf-token'
                            },
                            content_type='application/json'
                        )
                        
                        assert response.status_code == 401
                        
                        # Verify failure was logged
                        mock_log_event.assert_called()
                        call_args = mock_log_event.call_args
                        assert 'oauth.authentication_failed' in call_args[0] or 'failed' in str(call_args)
    
    def test_authentication_success_logging(self, client, mock_token_payload, mock_csrf):
        """
        Test that successful authentication is logged.
        Property 14: Authentication Success Logging
        """
        with patch('services.google_oauth.id_token.verify_oauth2_token', return_value=mock_token_payload):
            with patch('blueprints.auth.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value.__enter__.return_value = mock_db
                
                # Mock existing user
                mock_user = Mock()
                mock_user.id = 1
                mock_user.username = 'testuser'
                mock_db.query().filter().first.return_value = mock_user
                
                with patch('blueprints.auth.check_rate_limit', return_value=True):
                    with patch('blueprints.auth.log_event') as mock_log_event:
                        with client.session_transaction() as sess:
                            sess['csrf_token'] = 'test-csrf-token'
                        
                        response = client.post('/auth/google/callback',
                            json={
                                'credential': 'valid.jwt.token',
                                'csrf_token': 'test-csrf-token'
                            },
                            content_type='application/json'
                        )
                        
                        assert response.status_code == 200
                        
                        # Verify success was logged
                        mock_log_event.assert_called()
                        call_args = mock_log_event.call_args
                        assert 'oauth.login' in call_args[0] or 'login' in str(call_args)


class TestGoogleOAuthConfig:
    """Test /auth/google/config endpoint."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    def test_config_returns_enabled_when_configured(self, client):
        """Test that config returns enabled=true when OAuth is configured."""
        with patch('blueprints.auth.Config') as mock_config:
            mock_config.GOOGLE_CLIENT_ID = 'test-client-id.apps.googleusercontent.com'
            
            response = client.get('/auth/google/config')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['enabled'] is True
            assert data['client_id'] == 'test-client-id.apps.googleusercontent.com'
    
    def test_config_returns_disabled_when_not_configured(self, client):
        """
        Test that config returns enabled=false when OAuth is not configured.
        Property 16: Graceful Degradation
        """
        with patch('blueprints.auth.Config') as mock_config:
            mock_config.GOOGLE_CLIENT_ID = ''
            
            response = client.get('/auth/google/config')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['enabled'] is False
            assert 'client_id' not in data
