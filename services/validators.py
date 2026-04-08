"""
Input validation service for email and phone normalization.

Provides centralized validation functions used by all blueprints.
"""

import re
from typing import Optional

# Pre-compiled patterns for performance
_EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
_PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{6,14}$')


def validate_email(email: str) -> Optional[str]:
    """
    Validate and normalize email address.

    Returns:
        Normalized lowercase email if valid, None otherwise.
    """
    if not email or len(email) > 255:
        return None

    email = email.strip().lower()

    if not _EMAIL_PATTERN.match(email):
        return None

    return email


def validate_phone(phone: str) -> Optional[str]:
    """
    Validate and normalize phone number.

    Returns:
        Normalized phone number if valid, None otherwise.
    """
    if not phone or len(phone) > 20:
        return None

    # Remove spaces, dashes, parentheses
    phone = re.sub(r'[\s\-\(\)]', '', phone.strip())

    if not _PHONE_PATTERN.match(phone):
        return None

    return phone