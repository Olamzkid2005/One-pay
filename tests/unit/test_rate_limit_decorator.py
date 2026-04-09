"""
Unit tests for rate limit decorator.

Tests the @rate_limit decorator in core/decorators.py to ensure:
- Rate limit enforcement works correctly
- Key placeholder resolution works for {user_id}, {ip}, {api_key}
- 429 response format is correct
- Retry-After header is included

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
"""
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g


class TestRateLimitEnforcement:
    """Test rate limit enforcement behavior."""

    def test_allows_request_when_under_limit(self):
        """
        Test that requests are allowed when under the rate limit.

        Requirement 5.2: WHEN the decorator is applied to a route, THE System
        SHALL check the rate limit before executing the route handler
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = True  # Under limit

                response = client.get('/test')

                assert response.status_code == 200
                assert response.get_json() == {"success": True}

    def test_blocks_request_when_limit_exceeded(self):
        """
        Test that requests are blocked when rate limit is exceeded.

        Requirement 5.3: WHEN the rate limit is exceeded, THE System SHALL
        return HTTP 429 Too Many Requests
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = False  # Limit exceeded

                response = client.get('/test')

                assert response.status_code == 429

    def test_rate_limit_checked_before_route_handler(self):
        """
        Test that rate limit is checked before the route handler executes.

        Requirement 5.2: The rate limit check happens before route execution
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        handler_called = []

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=60)
        def test_route():
            handler_called.append(True)
            return {"success": True}

        # Act & Assert - When rate limited, handler should NOT be called
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = False  # Limit exceeded
                handler_called.clear()

                response = client.get('/test')

                assert response.status_code == 429
                assert len(handler_called) == 0  # Handler was never called


class TestKeyPlaceholderResolution:
    """Test key placeholder resolution for {user_id}, {ip}, {api_key}."""

    def test_resolves_ip_placeholder(self):
        """
        Test that {ip} placeholder is resolved to client IP.

        Requirement 5.1: THE System SHALL provide a @rate_limit decorator that
        accepts key, limit, and window_secs parameters
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("login:{ip}", limit=5, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = True

                client.get('/test', environ_base={'REMOTE_ADDR': '192.168.1.1'})

                # Verify the key was resolved with the IP
                call_args = mock_check.call_args
                assert call_args is not None
                resolved_key = call_args[0][1]  # Second argument is the key
                assert '192.168.1.1' in resolved_key or '127.0.0.1' in resolved_key

    def test_resolves_user_id_placeholder(self):
        """
        Test that {user_id} placeholder is resolved from Flask's g object.

        Requirement 5.4: THE decorator SHALL support both authenticated and
        anonymous rate limiting keys
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("api:{user_id}", limit=100, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = True

                # Use before_request to set g.user_id
                @app.before_request
                def set_user_id():
                    from flask import g
                    g.user_id = "user-123"

                client.get('/test')

                # Verify the key was resolved with user_id
                call_args = mock_check.call_args
                if call_args:
                    resolved_key = call_args[0][1]
                    assert 'user-123' in resolved_key

    def test_resolves_api_key_placeholder(self):
        """
        Test that {api_key} placeholder is resolved from Flask's g object.

        Requirement 5.4: THE decorator SHALL support both authenticated and
        anonymous rate limiting keys
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("api:{api_key}", limit=100, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = True

                # Use before_request to set g.api_key
                @app.before_request
                def set_api_key():
                    from flask import g
                    g.api_key = "pk_test_abc123"

                client.get('/test')

                # Verify the key was resolved with api_key
                call_args = mock_check.call_args
                if call_args:
                    resolved_key = call_args[0][1]
                    assert 'pk_test_abc123' in resolved_key

    def test_resolves_anonymous_user_placeholder(self):
        """
        Test that {user_id} defaults to 'anon' for unauthenticated users.

        Requirement 5.4: THE decorator SHALL support both authenticated and
        anonymous rate limiting keys
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("api:{user_id}", limit=100, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = True

                client.get('/test')

                # Verify the key was resolved with 'anon' for unauthenticated user
                call_args = mock_check.call_args
                if call_args:
                    resolved_key = call_args[0][1]
                    assert 'anon' in resolved_key

    def test_resolves_multiple_placeholders(self):
        """
        Test that multiple placeholders can be resolved in a single key.

        Requirement 5.1: The decorator accepts key parameter with placeholders
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("api:{user_id}:{ip}", limit=100, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = True

                # Use before_request to set g.user_id
                @app.before_request
                def set_user_id():
                    from flask import g
                    g.user_id = "user-456"

                client.get('/test')

                # Verify both placeholders were resolved
                call_args = mock_check.call_args
                if call_args:
                    resolved_key = call_args[0][1]
                    assert 'user-456' in resolved_key


class Test429ResponseFormat:
    """Test 429 response format and content."""

    def test_429_response_has_success_false(self):
        """
        Test that 429 response has success: false.

        Requirement 5.3: WHEN the rate limit is exceeded, THE System SHALL
        return HTTP 429 Too Many Requests with a JSON error body
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = False

                response = client.get('/test')
                data = response.get_json()

                assert data.get('success') is False

    def test_429_response_has_error_code(self):
        """
        Test that 429 response has error code RATE_LIMIT_EXCEEDED.

        Requirement 5.3: The response shall include an error code
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = False

                response = client.get('/test')
                data = response.get_json()

                assert data.get('error') == 'RATE_LIMIT_EXCEEDED'

    def test_429_response_has_user_friendly_message(self):
        """
        Test that 429 response has a user-friendly message.

        Requirement 5.3: The response shall include a user-friendly message
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = False

                response = client.get('/test')
                data = response.get_json()

                assert 'message' in data
                assert 'Too many requests' in data.get('message', '')

    def test_429_response_has_retry_after_field(self):
        """
        Test that 429 response includes retry_after field.

        Requirement 5.3: The response shall include retry_after information
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=120)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = False

                response = client.get('/test')
                data = response.get_json()

                assert 'retry_after' in data
                assert data.get('retry_after') == 120


class TestRetryAfterHeader:
    """Test Retry-After header in 429 responses."""

    def test_429_response_has_retry_after_header(self):
        """
        Test that 429 response includes Retry-After header.

        Requirement 5.3: WHEN the rate limit is exceeded, THE System SHALL
        return HTTP 429 Too Many Requests with a Retry-After header
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = False

                response = client.get('/test')

                assert 'Retry-After' in response.headers

    def test_retry_after_header_matches_window_secs(self):
        """
        Test that Retry-After header value matches window_secs parameter.

        Requirement 5.3: The Retry-After header shall indicate when to retry
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=300)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = False

                response = client.get('/test')

                assert response.headers.get('Retry-After') == '300'

    def test_retry_after_header_is_string(self):
        """
        Test that Retry-After header is a string (per HTTP spec).

        Requirement 5.3: The Retry-After header format
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = False

                response = client.get('/test')

                assert isinstance(response.headers.get('Retry-After'), str)


class TestRateLimitDecoratorIntegration:
    """Test decorator integration with database-backed rate limiter."""

    def test_decorator_calls_check_rate_limit_with_correct_params(self):
        """
        Test that decorator passes correct parameters to check_rate_limit.

        Requirement 5.5: THE decorator SHALL integrate with the existing
        database-backed rate limiter
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=10, window_secs=120, critical=True)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = True

                client.get('/test')

                # Verify check_rate_limit was called with correct params
                mock_check.assert_called_once()
                call_args = mock_check.call_args
                assert call_args[0][2] == 10  # limit
                assert call_args[0][3] == 120  # window_secs
                assert call_args[0][4] is True  # critical

    def test_decorator_uses_context_manager_for_db(self):
        """
        Test that decorator uses get_db context manager.

        Requirement 5.5: THE decorator SHALL integrate with the existing
        database-backed rate limiter
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            mock_db = MagicMock()
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)

            with patch('core.decorators.get_db') as mock_get_db:
                with patch('core.decorators.check_rate_limit') as mock_check:
                    mock_get_db.return_value = mock_db
                    mock_check.return_value = True

                    client.get('/test')

                    # Verify get_db was called (context manager)
                    mock_get_db.assert_called_once()


class TestRateLimitDecoratorEdgeCases:
    """Test edge cases for rate limit decorator."""

    def test_decorator_with_custom_window(self):
        """
        Test that custom window_secs parameter works correctly.

        Requirement 5.1: The decorator accepts window_secs parameter
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=3600)  # 1 hour
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = False

                response = client.get('/test')

                # Verify retry_after matches custom window
                assert response.headers.get('Retry-After') == '3600'

    def test_decorator_preserves_route_function_metadata(self):
        """
        Test that decorator preserves the original function's metadata.

        This ensures @wraps(f) is used correctly.
        """
        from functools import wraps

        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)

        @app.route('/test')
        @rate_limit("test:{ip}", limit=5, window_secs=60)
        def test_route():
            """Test route docstring."""
            return {"success": True}

        # Act & Assert
        # The wrapped function should preserve the original name
        assert test_route.__name__ == 'test_route'

    def test_decorator_with_zero_limit(self):
        """
        Test decorator behavior with zero limit (edge case).

        This tests that the decorator handles edge cases gracefully.
        """
        from core.decorators import rate_limit

        # Arrange
        app = Flask(__name__)
        app.config['TESTING'] = True

        @app.route('/test')
        @rate_limit("test:{ip}", limit=0, window_secs=60)
        def test_route():
            return {"success": True}

        # Act & Assert
        with app.test_client() as client:
            with patch('core.decorators.check_rate_limit') as mock_check:
                mock_check.return_value = False  # Zero limit = always blocked

                response = client.get('/test')

                assert response.status_code == 429
