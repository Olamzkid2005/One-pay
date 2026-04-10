"""
OnePay — Security utilities.

This module re-exports cryptographic primitives from core.security,
and provides URL validation functions that depend on core.network_security.
"""

import re
from typing import Optional

from core.network_security import is_safe_hostname
from core.security import (
    generate_expiration_time,
    generate_hash_token,
    generate_reset_token,
    generate_tx_reference,
    verify_hash_token,
)


def _assert_public_webhook_hostname(hostname: str) -> None:
    """Raise ValueError if hostname is private/internal (for webhook validation)."""
    if hostname in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Webhook URL cannot point to localhost")

    if not is_safe_hostname(hostname):
        raise ValueError(f"Webhook URL cannot use private/internal address: {hostname}")


def validate_return_url(value: str) -> Optional[str]:
    """
    Validate and normalize a customer return URL to prevent open redirects.
    Allows relative paths (/) and absolute HTTPS URLs to public hosts only.
    """
    if not value:
        return None
    url = value.strip()
    if not url or len(url) > 500:
        return None

    if url.startswith("/"):
        return None if url.startswith("//") else url

    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    if parsed.fragment or parsed.username or parsed.password:
        return None
    if not is_safe_hostname(parsed.hostname.lower()):
        return None
    return url


def validate_webhook_url(value: str) -> Optional[str]:
    """
    Validate a merchant webhook URL.
    Must be an absolute HTTPS URL pointing to a public host.
    """
    if not value:
        return None
    url = value.strip()
    if len(url) > 500:
        raise ValueError("Webhook URL exceeds maximum length of 500 characters")

    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Webhook URL must use HTTPS protocol")
    if not parsed.hostname:
        raise ValueError("Webhook URL must have a valid hostname")
    if parsed.username or parsed.password:
        raise ValueError("Webhook URL cannot contain credentials")

    _assert_public_webhook_hostname(parsed.hostname.lower())
    return url


def validate_hash_token_format(hash_token: str) -> bool:
    """Validate that the hash token looks like a base64-url signature."""
    if not hash_token:
        return False
    return bool(re.match(r"^[A-Za-z0-9_-]{20,300}$", hash_token))
