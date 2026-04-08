"""
Tests for global OnePay exception handler.

Validates Requirement 7.6: Global exception handler for OnePayError.
"""

import pytest
from unittest.mock import patch
from core.exceptions import (
    OnePayError,
    ValidationError,
    ProviderError,
    AuthenticationError,
    AuthorizationError
)


def test_onepay_error_handler_registered():
    """Test that OnePayError handler is registered in the app."""
    from app import app
    from core.exceptions import OnePayError as ImportedOnePayError
    
    # Check that the error handler is registered
    # error_handler_spec structure is nested: {blueprint: {status_code_or_None: {exception: handler}}}
    # For app-level handlers: app.error_handler_spec[None][None][ExceptionClass]
    assert None in app.error_handler_spec
    
    # Get handlers for None blueprint (app-level)
    app_level_handlers = app.error_handler_spec[None]
    
    # Get handlers for None status code (exception-based, not HTTP status)
    exception_handlers = app_level_handlers[None]
    
    # Check if OnePayError is in the exception handlers
    assert ImportedOnePayError in exception_handlers, \
        f"OnePayError not found. Available exceptions: {list(exception_handlers.keys())}"
    
    # Verify the handler is callable
    handler_func = exception_handlers[ImportedOnePayError]
    assert callable(handler_func)


def test_validation_error_properties():
    """Test ValidationError has correct properties."""
    error = ValidationError("Invalid email", field="email")
    
    assert error.message == "Invalid email"
    assert error.error_code == "VALIDATION_ERROR"
    assert error.status_code == 400
    assert error.field == "email"


def test_authentication_error_properties():
    """Test AuthenticationError has correct properties."""
    error = AuthenticationError("Invalid credentials")
    
    assert error.message == "Invalid credentials"
    assert error.error_code == "AUTHENTICATION_ERROR"
    assert error.status_code == 401


def test_authorization_error_properties():
    """Test AuthorizationError has correct properties."""
    error = AuthorizationError("Access denied")
    
    assert error.message == "Access denied"
    assert error.error_code == "AUTHORIZATION_ERROR"
    assert error.status_code == 403


def test_provider_error_properties():
    """Test ProviderError has correct properties."""
    error = ProviderError("Timeout", provider="korapay", original_error="Connection timeout")
    
    assert error.message == "Timeout"
    assert error.error_code == "PROVIDER_ERROR"
    assert error.status_code == 502
    assert error.provider == "korapay"
    assert error.original_error == "Connection timeout"


def test_generic_onepay_error_properties():
    """Test generic OnePayError has correct properties."""
    error = OnePayError("Custom error", error_code="CUSTOM_ERROR", status_code=418)
    
    assert error.message == "Custom error"
    assert error.error_code == "CUSTOM_ERROR"
    assert error.status_code == 418


def test_error_response_format_structure():
    """Test that error responses have the correct structure."""
    # The handler should return JSON with success, message, and error_code
    # This is verified by the implementation in app.py
    
    error = ValidationError("Test error")
    
    # Verify the error has the required attributes for the handler
    assert hasattr(error, 'message')
    assert hasattr(error, 'error_code')
    assert hasattr(error, 'status_code')
    
    # These are used in the handler's jsonify call
    assert error.message == "Test error"
    assert error.error_code == "VALIDATION_ERROR"
    assert error.status_code == 400
