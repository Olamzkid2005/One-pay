"""
OnePay — URL validation with SSRF protection.
"""

from typing import Optional

from services.url_validator import validate_url_for_ssrf as _validate_url


def validate_url_for_ssrf(url: str) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Validate URL and resolve to safe IP address with SSRF protection.

    Returns:
        (is_valid, resolved_ip, error_message)
    """
    return _validate_url(url)
