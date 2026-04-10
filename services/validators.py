"""
OnePay — Input validation service for email and phone normalization.

DEPRECATED: Use services.validation instead.
This module is kept for backwards compatibility.
"""

from services.validation.email import validate_email
from services.validation.phone import validate_phone

__all__ = ["validate_email", "validate_phone"]
