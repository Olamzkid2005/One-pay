"""
OnePay — Phone validation.
"""

import re
from typing import Optional

_PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{6,14}$")


def validate_phone(phone: str) -> Optional[str]:
    """
    Validate and normalize phone number.

    Returns:
        Normalized phone number if valid, None otherwise.
    """
    if not phone or len(phone) > 20:
        return None

    phone = re.sub(r"[\s\-\(\)]", "", phone.strip())

    if not _PHONE_PATTERN.match(phone):
        return None

    return phone
