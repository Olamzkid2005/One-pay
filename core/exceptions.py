"""
Custom exception hierarchy for OnePay application.

Provides consistent error handling with error codes and HTTP status codes.
"""

from typing import Optional


class OnePayError(Exception):
    """Base exception for all OnePay errors."""
    
    def __init__(self, message: str, error_code: str, status_code: int = 500):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


class ValidationError(OnePayError):
    """Input validation failure."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400
        )


class ProviderError(OnePayError):
    """External service (KoraPay, VoicePay) failure."""
    
    def __init__(self, message: str, provider: str, original_error: Optional[str] = None):
        self.provider = provider
        self.original_error = original_error
        super().__init__(
            message=message,
            error_code="PROVIDER_ERROR",
            status_code=502
        )


class AuthenticationError(OnePayError):
    """Authentication failure."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401
        )


class AuthorizationError(OnePayError):
    """Authorization failure."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403
        )
