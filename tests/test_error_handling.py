"""
Tests for error handling standardization (Requirement 25).

Validates:
- 25.1: Standardized error response format
- 25.2: HTTP status codes match error types
- 25.3: Correlation ID in error logs
- 25.4: Internal details not exposed in error messages
"""

import json
import logging

import pytest
from flask import Blueprint

from core.exceptions import AuthenticationError, AuthorizationError, OnePayError, ProviderError, ValidationError

# Create a test blueprint with routes that raise various errors
test_bp = Blueprint('test_errors', __name__)


@test_bp.route('/validation-error')
def validation_error_route():
    raise ValidationError("Invalid email format", field="email")


@test_bp.route('/auth-error')
def auth_error_route():
    raise AuthenticationError("Invalid credentials")


@test_bp.route('/authz-error')
def authz_error_route():
    raise AuthorizationError("Insufficient permissions")


@test_bp.route('/provider-error')
def provider_error_route():
    raise ProviderError(
        "Payment provider unavailable",
        provider="korapay",
        original_error="Connection timeout"
    )


@test_bp.route('/generic-error')
def generic_error_route():
    raise OnePayError(
        "Something went wrong",
        error_code="CUSTOM_ERROR",
        status_code=500
    )


@test_bp.route('/custom-status')
def custom_status_route():
    raise OnePayError("Custom error", error_code="CUSTOM", status_code=418)


@test_bp.route('/internal-details')
def internal_details_route():
    raise ProviderError(
        "Payment provider unavailable",
        provider="korapay",
        original_error="Internal server error: Database connection failed at line 42"
    )


@test_bp.route('/unexpected')
def unexpected_route():
    raise OnePayError(
        "An unexpected error occurred",
        error_code="INTERNAL_ERROR",
        status_code=500
    )


@test_bp.route('/special-chars')
def special_chars_route():
    raise ValidationError("Error with <script>alert('xss')</script>")


@test_bp.route('/unicode')
def unicode_route():
    raise ValidationError("Error: Invalid currency ₦")


@pytest.fixture
def test_app():
    """Create a minimal Flask app with error handlers for testing."""
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True

    # Register test blueprint
    app.register_blueprint(test_bp, url_prefix='/test')

    yield app

    # Cleanup: Signal background threads to stop
    if hasattr(app, '_shutdown_event'):
        app._shutdown_event.set()


@pytest.fixture
def client(test_app):
    """Create Flask test client."""
    return test_app.test_client()


# ============================================================================
# Requirement 25.1: Test error response format
# ============================================================================

def test_validation_error_response_format(client):
    """Test ValidationError returns standardized JSON format."""
    response = client.get('/test/validation-error')
    data = json.loads(response.data)

    # Verify response structure
    assert 'success' in data
    assert 'message' in data
    assert 'error_code' in data

    # Verify values
    assert data['success'] is False
    assert data['message'] == "Invalid email format"
    assert data['error_code'] == "VALIDATION_ERROR"


def test_authentication_error_response_format(client):
    """Test AuthenticationError returns standardized JSON format."""
    response = client.get('/test/auth-error')
    data = json.loads(response.data)

    assert data['success'] is False
    assert data['message'] == "Invalid credentials"
    assert data['error_code'] == "AUTHENTICATION_ERROR"


def test_authorization_error_response_format(client):
    """Test AuthorizationError returns standardized JSON format."""
    response = client.get('/test/authz-error')
    data = json.loads(response.data)

    assert data['success'] is False
    assert data['message'] == "Insufficient permissions"
    assert data['error_code'] == "AUTHORIZATION_ERROR"


def test_provider_error_response_format(client):
    """Test ProviderError returns standardized JSON format."""
    response = client.get('/test/provider-error')
    data = json.loads(response.data)

    assert data['success'] is False
    assert data['message'] == "Payment provider unavailable"
    assert data['error_code'] == "PROVIDER_ERROR"


def test_generic_onepay_error_response_format(client):
    """Test generic OnePayError returns standardized JSON format."""
    response = client.get('/test/generic-error')
    data = json.loads(response.data)

    assert data['success'] is False
    assert data['message'] == "Something went wrong"
    assert data['error_code'] == "CUSTOM_ERROR"


def test_error_response_has_no_extra_fields(client):
    """Test error responses don't include extra fields beyond success, message, error_code."""
    response = client.get('/test/validation-error')
    data = json.loads(response.data)

    # Should only have these three fields
    assert set(data.keys()) == {'success', 'message', 'error_code'}


# ============================================================================
# Requirement 25.2: Test status codes
# ============================================================================

def test_validation_error_status_code(client):
    """Test ValidationError returns HTTP 400."""
    response = client.get('/test/validation-error')
    assert response.status_code == 400


def test_authentication_error_status_code(client):
    """Test AuthenticationError returns HTTP 401."""
    response = client.get('/test/auth-error')
    assert response.status_code == 401


def test_authorization_error_status_code(client):
    """Test AuthorizationError returns HTTP 403."""
    response = client.get('/test/authz-error')
    assert response.status_code == 403


def test_provider_error_status_code(client):
    """Test ProviderError returns HTTP 502."""
    response = client.get('/test/provider-error')
    assert response.status_code == 502


def test_custom_status_code(client):
    """Test OnePayError respects custom status codes."""
    response = client.get('/test/custom-status')
    assert response.status_code == 418


# ============================================================================
# Requirement 25.3: Test correlation ID in errors
# ============================================================================

def test_correlation_id_in_error_logs(client, caplog):
    """Test that correlation ID is included in error logs."""
    # Set log level to capture error logs
    with caplog.at_level(logging.ERROR):
        client.get(
            '/test/validation-error',
            headers={'X-Request-ID': 'test-correlation-123'}
        )

    # Verify error was logged
    assert len(caplog.records) > 0

    # Find the error log record
    error_logs = [r for r in caplog.records if r.levelname == 'ERROR']
    assert len(error_logs) > 0

    # Verify correlation ID is in the log message or record
    error_record = error_logs[0]
    assert hasattr(error_record, 'correlation_id')
    assert error_record.correlation_id == 'test-correlation-123'


def test_correlation_id_generated_when_not_provided(client, caplog):
    """Test that correlation ID is generated when not provided in request."""
    with caplog.at_level(logging.ERROR):
        client.get('/test/validation-error')

    # Verify correlation ID was generated
    error_logs = [r for r in caplog.records if r.levelname == 'ERROR']
    assert len(error_logs) > 0

    error_record = error_logs[0]
    assert hasattr(error_record, 'correlation_id')
    assert error_record.correlation_id != '-'
    assert len(error_record.correlation_id) > 0


def test_correlation_id_in_response_header(client):
    """Test that correlation ID is returned in X-Correlation-ID header."""
    response = client.get(
        '/test/validation-error',
        headers={'X-Request-ID': 'test-corr-456'}
    )

    # Verify correlation ID in response header
    assert 'X-Correlation-ID' in response.headers
    assert response.headers['X-Correlation-ID'] == 'test-corr-456'


def test_error_log_contains_error_code(client, caplog):
    """Test that error logs contain the error code."""
    with caplog.at_level(logging.ERROR):
        client.get('/test/validation-error')

    # Verify error code is in log message
    error_logs = [r for r in caplog.records if r.levelname == 'ERROR']
    assert len(error_logs) > 0

    log_message = error_logs[0].message
    assert 'VALIDATION_ERROR' in log_message


def test_error_log_contains_message(client, caplog):
    """Test that error logs contain the error message."""
    with caplog.at_level(logging.ERROR):
        client.get('/test/validation-error')

    # Verify message is in log
    error_logs = [r for r in caplog.records if r.levelname == 'ERROR']
    assert len(error_logs) > 0

    log_message = error_logs[0].message
    assert 'Invalid email format' in log_message


# ============================================================================
# Requirement 25.4: Test internal details not exposed
# ============================================================================

def test_provider_error_hides_internal_details(client):
    """Test that ProviderError doesn't expose internal error details."""
    response = client.get('/test/internal-details')
    data = json.loads(response.data)

    # User-facing message should not contain internal details
    assert "Database connection" not in data['message']
    assert "line 42" not in data['message']
    assert data['message'] == "Payment provider unavailable"


def test_validation_error_no_stack_trace(client):
    """Test that error responses don't include stack traces."""
    response = client.get('/test/validation-error')
    data = json.loads(response.data)

    # Response should not contain stack trace keywords
    response_str = json.dumps(data)
    assert 'Traceback' not in response_str
    assert 'File "' not in response_str
    assert 'line ' not in response_str


def test_error_response_no_exception_type(client):
    """Test that error responses don't expose Python exception types."""
    response = client.get('/test/validation-error')
    data = json.loads(response.data)

    # Should not contain Python exception class names
    response_str = json.dumps(data)
    assert 'ValidationError' not in response_str
    assert 'Exception' not in response_str
    assert 'Error' not in data['message']  # Only in error_code


def test_error_response_no_file_paths(client):
    """Test that error responses don't expose file paths."""
    response = client.get('/test/unexpected')
    data = json.loads(response.data)

    # Should not contain file system paths
    response_str = json.dumps(data)
    assert '/app/' not in response_str
    assert '/core/' not in response_str
    assert '.py' not in response_str


def test_generic_error_message_for_unexpected_errors(client):
    """Test that unexpected errors return generic messages."""
    response = client.get('/test/unexpected')
    data = json.loads(response.data)

    # Message should be generic, not revealing internal details
    assert data['message'] == "An unexpected error occurred"
    assert 'database' not in data['message'].lower()
    assert 'sql' not in data['message'].lower()
    assert 'connection' not in data['message'].lower()


# ============================================================================
# Edge cases and integration tests
# ============================================================================

def test_multiple_errors_same_request(client):
    """Test that each error in a request gets its own correlation ID."""
    # First request
    response1 = client.get('/test/validation-error')
    corr_id_1 = response1.headers.get('X-Correlation-ID')

    # Second request
    response2 = client.get('/test/auth-error')
    corr_id_2 = response2.headers.get('X-Correlation-ID')

    # Each request should have a different correlation ID
    assert corr_id_1 != corr_id_2


def test_error_with_special_characters(client):
    """Test error messages with special characters are properly escaped."""
    response = client.get('/test/special-chars')
    data = json.loads(response.data)

    # Message should be preserved but JSON-safe
    assert '<script>' in data['message']
    # Verify response is valid JSON
    assert isinstance(data, dict)


def test_error_with_unicode(client):
    """Test error messages with unicode characters."""
    response = client.get('/test/unicode')
    data = json.loads(response.data)

    assert '₦' in data['message']
    assert data['error_code'] == 'VALIDATION_ERROR'


def test_error_response_content_type(client):
    """Test that error responses have correct Content-Type header."""
    response = client.get('/test/validation-error')

    assert 'application/json' in response.content_type


def test_all_error_types_have_consistent_format(client):
    """Test that all error types follow the same response format."""
    test_routes = [
        ('/test/validation-error', 400),
        ('/test/auth-error', 401),
        ('/test/authz-error', 403),
        ('/test/provider-error', 502),
        ('/test/generic-error', 500),
    ]

    for route, expected_status in test_routes:
        response = client.get(route)
        data = json.loads(response.data)

        # All should have the same structure
        assert set(data.keys()) == {'success', 'message', 'error_code'}
        assert data['success'] is False
        assert isinstance(data['message'], str)
        assert isinstance(data['error_code'], str)
        assert response.status_code == expected_status
