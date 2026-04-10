"""
OnePay — Unified Validation Service

Provides a single entry point for all input validation.
Each validator returns a consistent (is_valid, normalized_value, error_msg) tuple.
"""

from typing import Optional

from .email import validate_email
from .password import validate_password_strength
from .phone import validate_phone
from .url import validate_url_for_ssrf


class ValidationService:
    """
    Unified validation service with consistent interface.

    All methods return (is_valid, normalized_value, error_message):
    - is_valid: bool indicating if input passed validation
    - normalized_value: the cleaned/normalized value if valid, None if invalid
    - error_message: None if valid, error string if invalid
    """

    @staticmethod
    def email(email: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Validate and normalize email address.

        Returns:
            (is_valid, normalized_email, error_message)
        """
        result = validate_email(email)
        if result is None:
            return False, None, "Invalid email address"
        return True, result, None

    @staticmethod
    def phone(phone: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Validate and normalize phone number.

        Returns:
            (is_valid, normalized_phone, error_message)
        """
        result = validate_phone(phone)
        if result is None:
            return False, None, "Invalid phone number"
        return True, result, None

    @staticmethod
    def password(password: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Validate password strength.

        Returns:
            (is_valid, None, error_message)
            (Note: password is not returned for security)
        """
        is_valid, error_msg = validate_password_strength(password)
        if is_valid:
            return True, None, None
        return False, None, error_msg

    @staticmethod
    def url(url: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Validate URL for SSRF protection.

        Returns:
            (is_valid, resolved_ip, error_message)
        """
        return validate_url_for_ssrf(url)


# Default instance for convenience
validator = ValidationService()


__all__ = ["ValidationService", "validator"]
