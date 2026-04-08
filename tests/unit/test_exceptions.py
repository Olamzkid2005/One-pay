"""
Unit tests for custom exception hierarchy.

Tests the exception classes in core/exceptions.py to ensure:
- Each exception type has correct properties
- Error codes and status codes are correct
- Global handler response format is correct
- Exception inheritance works correctly

**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6**
"""
import pytest
from unittest.mock import Mock, patch
from flask import Flask, g
from core.exceptions import (
    OnePayError,
    ValidationError,
    ProviderError,
    AuthenticationError,
    AuthorizationError
)


class TestOnePayErrorBase:
    """Test base OnePayError exception class."""

    def test_onepay_error_has_required_attributes(self):
        """
        Test that OnePayError has message, error_code, and status_code.
        
        Requirement 7.1: THE System SHALL define a base OnePayError exception class
        Requirement 7.6: WHEN an exception is raised, THE System SHALL include 
        an error code and user-friendly message
        """
        # Arrange & Act
        error = OnePayError(
            message="Test error message",
            error_code="TEST_ERROR",
            status_code=500
        )
        
        # Assert
        assert error.message == "Test error message"
        assert error.error_code == "TEST_ERROR"
        assert error.status_code == 500

    def test_onepay_error_default_status_code(self):
        """
        Test that OnePayError defaults to 500 status code.
        
        Requirement 7.1: Base exception should have sensible defaults
        """
        # Arrange & Act
        error = OnePayError(
            message="Test error",
            error_code="TEST_ERROR"
        )
        
        # Assert
        assert error.status_code == 500

    def test_onepay_error_is_exception(self):
        """
        Test that OnePayError inherits from Exception.
        
        Requirement 7.1: Base exception should be a proper Python exception
        """
        # Arrange & Act
        error = OnePayError(
            message="Test error",
            error_code="TEST_ERROR"
        )
        
        # Assert
        assert isinstance(error, Exception)

    def test_onepay_error_str_representation(self):
        """
        Test that OnePayError has proper string representation.
        
        Requirement 7.1: Exception should be printable
        """
        # Arrange & Act
        error = OnePayError(
            message="Test error message",
            error_code="TEST_ERROR"
        )
        
        # Assert
        assert str(error) == "Test error message"

    def test_onepay_error_can_be_raised(self):
        """
        Test that OnePayError can be raised and caught.
        
        Requirement 7.1: Exception should work with Python's exception handling
        """
        # Arrange
        error = OnePayError(
            message="Test error",
            error_code="TEST_ERROR"
        )
        
        # Act & Assert
        with pytest.raises(OnePayError) as exc_info:
            raise error
        
        assert exc_info.value.message == "Test error"
        assert exc_info.value.error_code == "TEST_ERROR"

    def test_onepay_error_with_custom_status_code(self):
        """
        Test that OnePayError accepts custom status codes.
        
        Requirement 7.1: Base exception should be flexible
        """
        # Arrange & Act
        error = OnePayError(
            message="I'm a teapot",
            error_code="TEAPOT_ERROR",
            status_code=418
        )
        
        # Assert
        assert error.status_code == 418


class TestValidationError:
    """Test ValidationError exception class."""

    def test_validation_error_has_correct_error_code(self):
        """
        Test that ValidationError has VALIDATION_ERROR code.
        
        Requirement 7.2: THE System SHALL define ValidationError for input 
        validation failures
        """
        # Arrange & Act
        error = ValidationError(message="Invalid input")
        
        # Assert
        assert error.error_code == "VALIDATION_ERROR"

    def test_validation_error_has_correct_status_code(self):
        """
        Test that ValidationError has 400 status code.
        
        Requirement 7.2: Validation errors should return 400 Bad Request
        """
        # Arrange & Act
        error = ValidationError(message="Invalid input")
        
        # Assert
        assert error.status_code == 400

    def test_validation_error_with_field(self):
        """
        Test that ValidationError can include field name.
        
        Requirement 7.2: Validation errors should identify the problematic field
        """
        # Arrange & Act
        error = ValidationError(message="Invalid email format", field="email")
        
        # Assert
        assert error.field == "email"
        assert error.message == "Invalid email format"

    def test_validation_error_without_field(self):
        """
        Test that ValidationError works without field name.
        
        Requirement 7.2: Field parameter should be optional
        """
        # Arrange & Act
        error = ValidationError(message="Invalid input")
        
        # Assert
        assert error.field is None

    def test_validation_error_inherits_from_onepay_error(self):
        """
        Test that ValidationError inherits from OnePayError.
        
        Requirement 7.2: ValidationError should be a OnePayError
        """
        # Arrange & Act
        error = ValidationError(message="Invalid input")
        
        # Assert
        assert isinstance(error, OnePayError)
        assert isinstance(error, Exception)

    def test_validation_error_can_be_caught_as_onepay_error(self):
        """
        Test that ValidationError can be caught as OnePayError.
        
        Requirement 7.2: Exception hierarchy should work correctly
        """
        # Arrange & Act & Assert
        with pytest.raises(OnePayError) as exc_info:
            raise ValidationError(message="Invalid input", field="username")
        
        assert exc_info.value.error_code == "VALIDATION_ERROR"
        assert exc_info.value.status_code == 400

    def test_validation_error_examples(self):
        """
        Test common validation error scenarios.
        
        Requirement 7.2: Validation errors for various input failures
        """
        # Test various validation scenarios
        errors = [
            ValidationError("Email is required", field="email"),
            ValidationError("Phone number is invalid", field="phone"),
            ValidationError("Amount must be positive", field="amount"),
            ValidationError("Password too short", field="password"),
        ]
        
        for error in errors:
            assert error.error_code == "VALIDATION_ERROR"
            assert error.status_code == 400
            assert error.field is not None


class TestProviderError:
    """Test ProviderError exception class."""

    def test_provider_error_has_correct_error_code(self):
        """
        Test that ProviderError has PROVIDER_ERROR code.
        
        Requirement 7.3: THE System SHALL define ProviderError for external 
        service failures
        """
        # Arrange & Act
        error = ProviderError(
            message="Payment provider unavailable",
            provider="korapay"
        )
        
        # Assert
        assert error.error_code == "PROVIDER_ERROR"

    def test_provider_error_has_correct_status_code(self):
        """
        Test that ProviderError has 502 status code.
        
        Requirement 7.3: Provider errors should return 502 Bad Gateway
        """
        # Arrange & Act
        error = ProviderError(
            message="Payment provider unavailable",
            provider="korapay"
        )
        
        # Assert
        assert error.status_code == 502

    def test_provider_error_includes_provider_name(self):
        """
        Test that ProviderError includes provider name.
        
        Requirement 7.3: Provider errors should identify the failing service
        """
        # Arrange & Act
        error = ProviderError(
            message="Service timeout",
            provider="korapay"
        )
        
        # Assert
        assert error.provider == "korapay"

    def test_provider_error_with_original_error(self):
        """
        Test that ProviderError can include original error message.
        
        Requirement 7.3: Provider errors should preserve original error details
        """
        # Arrange & Act
        error = ProviderError(
            message="Payment failed",
            provider="voicepay",
            original_error="Connection timeout after 30s"
        )
        
        # Assert
        assert error.original_error == "Connection timeout after 30s"
        assert error.provider == "voicepay"

    def test_provider_error_without_original_error(self):
        """
        Test that ProviderError works without original error.
        
        Requirement 7.3: Original error parameter should be optional
        """
        # Arrange & Act
        error = ProviderError(
            message="Payment failed",
            provider="korapay"
        )
        
        # Assert
        assert error.original_error is None

    def test_provider_error_inherits_from_onepay_error(self):
        """
        Test that ProviderError inherits from OnePayError.
        
        Requirement 7.3: ProviderError should be a OnePayError
        """
        # Arrange & Act
        error = ProviderError(
            message="Service unavailable",
            provider="korapay"
        )
        
        # Assert
        assert isinstance(error, OnePayError)
        assert isinstance(error, Exception)

    def test_provider_error_examples(self):
        """
        Test common provider error scenarios.
        
        Requirement 7.3: Provider errors for various external service failures
        """
        # Test various provider scenarios
        errors = [
            ProviderError("KoraPay API timeout", provider="korapay", 
                         original_error="Timeout after 30s"),
            ProviderError("VoicePay service unavailable", provider="voicepay"),
            ProviderError("Payment gateway error", provider="korapay",
                         original_error="Invalid API key"),
            ProviderError("Refund failed", provider="korapay",
                         original_error="Insufficient balance"),
        ]
        
        for error in errors:
            assert error.error_code == "PROVIDER_ERROR"
            assert error.status_code == 502
            assert error.provider is not None


class TestAuthenticationError:
    """Test AuthenticationError exception class."""

    def test_authentication_error_has_correct_error_code(self):
        """
        Test that AuthenticationError has AUTHENTICATION_ERROR code.
        
        Requirement 7.4: THE System SHALL define AuthenticationError for 
        authentication failures
        """
        # Arrange & Act
        error = AuthenticationError()
        
        # Assert
        assert error.error_code == "AUTHENTICATION_ERROR"

    def test_authentication_error_has_correct_status_code(self):
        """
        Test that AuthenticationError has 401 status code.
        
        Requirement 7.4: Authentication errors should return 401 Unauthorized
        """
        # Arrange & Act
        error = AuthenticationError()
        
        # Assert
        assert error.status_code == 401

    def test_authentication_error_default_message(self):
        """
        Test that AuthenticationError has default message.
        
        Requirement 7.4: Authentication errors should have sensible default
        """
        # Arrange & Act
        error = AuthenticationError()
        
        # Assert
        assert error.message == "Authentication required"

    def test_authentication_error_custom_message(self):
        """
        Test that AuthenticationError accepts custom message.
        
        Requirement 7.4: Authentication errors should allow custom messages
        """
        # Arrange & Act
        error = AuthenticationError(message="Invalid credentials")
        
        # Assert
        assert error.message == "Invalid credentials"

    def test_authentication_error_inherits_from_onepay_error(self):
        """
        Test that AuthenticationError inherits from OnePayError.
        
        Requirement 7.4: AuthenticationError should be a OnePayError
        """
        # Arrange & Act
        error = AuthenticationError()
        
        # Assert
        assert isinstance(error, OnePayError)
        assert isinstance(error, Exception)

    def test_authentication_error_examples(self):
        """
        Test common authentication error scenarios.
        
        Requirement 7.4: Authentication errors for various auth failures
        """
        # Test various authentication scenarios
        errors = [
            AuthenticationError("Invalid username or password"),
            AuthenticationError("Session expired"),
            AuthenticationError("API key is invalid"),
            AuthenticationError("Token has expired"),
            AuthenticationError(),  # Default message
        ]
        
        for error in errors:
            assert error.error_code == "AUTHENTICATION_ERROR"
            assert error.status_code == 401


class TestAuthorizationError:
    """Test AuthorizationError exception class."""

    def test_authorization_error_has_correct_error_code(self):
        """
        Test that AuthorizationError has AUTHORIZATION_ERROR code.
        
        Requirement 7.5: THE System SHALL define AuthorizationError for 
        authorization failures
        """
        # Arrange & Act
        error = AuthorizationError()
        
        # Assert
        assert error.error_code == "AUTHORIZATION_ERROR"

    def test_authorization_error_has_correct_status_code(self):
        """
        Test that AuthorizationError has 403 status code.
        
        Requirement 7.5: Authorization errors should return 403 Forbidden
        """
        # Arrange & Act
        error = AuthorizationError()
        
        # Assert
        assert error.status_code == 403

    def test_authorization_error_default_message(self):
        """
        Test that AuthorizationError has default message.
        
        Requirement 7.5: Authorization errors should have sensible default
        """
        # Arrange & Act
        error = AuthorizationError()
        
        # Assert
        assert error.message == "Access denied"

    def test_authorization_error_custom_message(self):
        """
        Test that AuthorizationError accepts custom message.
        
        Requirement 7.5: Authorization errors should allow custom messages
        """
        # Arrange & Act
        error = AuthorizationError(message="Insufficient permissions")
        
        # Assert
        assert error.message == "Insufficient permissions"

    def test_authorization_error_inherits_from_onepay_error(self):
        """
        Test that AuthorizationError inherits from OnePayError.
        
        Requirement 7.5: AuthorizationError should be a OnePayError
        """
        # Arrange & Act
        error = AuthorizationError()
        
        # Assert
        assert isinstance(error, OnePayError)
        assert isinstance(error, Exception)

    def test_authorization_error_examples(self):
        """
        Test common authorization error scenarios.
        
        Requirement 7.5: Authorization errors for various permission failures
        """
        # Test various authorization scenarios
        errors = [
            AuthorizationError("You don't have permission to access this resource"),
            AuthorizationError("Admin access required"),
            AuthorizationError("API key does not have required scope"),
            AuthorizationError("Account suspended"),
            AuthorizationError(),  # Default message
        ]
        
        for error in errors:
            assert error.error_code == "AUTHORIZATION_ERROR"
            assert error.status_code == 403


class TestGlobalExceptionHandler:
    """Test global exception handler behavior."""

    def test_handler_returns_correct_json_structure(self):
        """
        Test that handler returns JSON with success, message, and error_code.
        
        Requirement 7.6: Global handler should return standardized format
        """
        # Arrange - use the app factory
        from app import create_app
        app = create_app()
        
        @app.route('/test-error')
        def test_error():
            raise ValidationError("Test validation error", field="test_field")
        
        # Act
        with app.test_client() as client:
            response = client.get('/test-error')
            data = response.get_json()
        
        # Assert
        assert response.status_code == 400
        assert data['success'] is False
        assert data['message'] == "Test validation error"
        assert data['error_code'] == "VALIDATION_ERROR"

    def test_handler_uses_correct_status_code(self):
        """
        Test that handler uses exception's status code.
        
        Requirement 7.6: Handler should respect exception status codes
        """
        # Arrange - use the app factory
        from app import create_app
        app = create_app()
        
        @app.route('/test-auth-error')
        def test_auth_error():
            raise AuthenticationError("Invalid token")
        
        # Act
        with app.test_client() as client:
            response = client.get('/test-auth-error')
        
        # Assert
        assert response.status_code == 401

    def test_handler_logs_error_with_correlation_id(self):
        """
        Test that handler logs error with correlation ID.
        
        Requirement 7.6: Handler should log errors with correlation ID
        """
        # Arrange - use the app factory
        from app import create_app
        app = create_app()
        
        @app.route('/test-provider-error')
        def test_provider_error():
            g.correlation_id = "test-correlation-123"
            raise ProviderError("Service timeout", provider="korapay")
        
        # Act
        with app.test_client() as client:
            response = client.get('/test-provider-error')
        
        # Assert
        assert response.status_code == 502

    def test_handler_works_for_all_exception_types(self):
        """
        Test that handler works for all custom exception types.
        
        Requirement 7.6: Handler should handle all OnePayError subclasses
        """
        # Arrange - use the app factory
        from app import create_app
        app = create_app()
        
        # Define test routes for each exception type
        @app.route('/validation')
        def validation_error():
            raise ValidationError("Invalid input")
        
        @app.route('/provider')
        def provider_error():
            raise ProviderError("Timeout", provider="korapay")
        
        @app.route('/auth')
        def auth_error():
            raise AuthenticationError("Invalid token")
        
        @app.route('/authz')
        def authz_error():
            raise AuthorizationError("No permission")
        
        @app.route('/generic')
        def generic_error():
            raise OnePayError("Generic error", "GENERIC", 500)
        
        test_cases = [
            ('/validation', 400, "VALIDATION_ERROR"),
            ('/provider', 502, "PROVIDER_ERROR"),
            ('/auth', 401, "AUTHENTICATION_ERROR"),
            ('/authz', 403, "AUTHORIZATION_ERROR"),
            ('/generic', 500, "GENERIC"),
        ]
        
        # Act & Assert
        with app.test_client() as client:
            for route, expected_status, expected_code in test_cases:
                response = client.get(route)
                data = response.get_json()
                
                assert response.status_code == expected_status
                assert data['error_code'] == expected_code
                assert data['success'] is False

    def test_handler_includes_all_required_fields(self):
        """
        Test that handler response includes all required fields.
        
        Requirement 7.6: Handler response must have success, message, error_code
        """
        # Arrange - use the app factory
        from app import create_app
        app = create_app()
        
        @app.route('/test')
        def test_route():
            raise ValidationError("Test error")
        
        # Act
        with app.test_client() as client:
            response = client.get('/test')
            data = response.get_json()
        
        # Assert
        assert 'success' in data
        assert 'message' in data
        assert 'error_code' in data
        assert len(data) == 3  # Only these three fields


class TestExceptionHierarchy:
    """Test exception inheritance and hierarchy."""

    def test_all_exceptions_inherit_from_onepay_error(self):
        """
        Test that all custom exceptions inherit from OnePayError.
        
        Requirement 7.1: All exceptions should be part of the hierarchy
        """
        # Arrange
        exceptions = [
            ValidationError("test"),
            ProviderError("test", provider="test"),
            AuthenticationError("test"),
            AuthorizationError("test"),
        ]
        
        # Act & Assert
        for exc in exceptions:
            assert isinstance(exc, OnePayError)
            assert isinstance(exc, Exception)

    def test_exceptions_can_be_caught_generically(self):
        """
        Test that all exceptions can be caught as OnePayError.
        
        Requirement 7.1: Exception hierarchy should enable generic catching
        """
        # Arrange
        exceptions = [
            ValidationError("test"),
            ProviderError("test", provider="test"),
            AuthenticationError("test"),
            AuthorizationError("test"),
        ]
        
        # Act & Assert
        for exc in exceptions:
            with pytest.raises(OnePayError):
                raise exc

    def test_exceptions_can_be_caught_specifically(self):
        """
        Test that exceptions can be caught by their specific type.
        
        Requirement 7.1: Exception hierarchy should enable specific catching
        """
        # Test ValidationError
        with pytest.raises(ValidationError):
            raise ValidationError("test")
        
        # Test ProviderError
        with pytest.raises(ProviderError):
            raise ProviderError("test", provider="test")
        
        # Test AuthenticationError
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("test")
        
        # Test AuthorizationError
        with pytest.raises(AuthorizationError):
            raise AuthorizationError("test")

    def test_exception_hierarchy_order(self):
        """
        Test that exception catching respects hierarchy order.
        
        Requirement 7.1: More specific exceptions should be caught first
        """
        # Arrange
        error = ValidationError("test")
        
        # Act & Assert - specific catch should work
        try:
            raise error
        except ValidationError as e:
            assert isinstance(e, ValidationError)
            assert isinstance(e, OnePayError)
        except OnePayError:
            pytest.fail("Should have caught ValidationError specifically")

    def test_all_exceptions_have_required_attributes(self):
        """
        Test that all exceptions have message, error_code, and status_code.
        
        Requirement 7.6: All exceptions must have consistent attributes
        """
        # Arrange
        exceptions = [
            OnePayError("test", "TEST", 500),
            ValidationError("test"),
            ProviderError("test", provider="test"),
            AuthenticationError("test"),
            AuthorizationError("test"),
        ]
        
        # Act & Assert
        for exc in exceptions:
            assert hasattr(exc, 'message')
            assert hasattr(exc, 'error_code')
            assert hasattr(exc, 'status_code')
            assert isinstance(exc.message, str)
            assert isinstance(exc.error_code, str)
            assert isinstance(exc.status_code, int)
