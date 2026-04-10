"""
OnePay — Email validation.
"""

import re
from typing import Optional

_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


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
