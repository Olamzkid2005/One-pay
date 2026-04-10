"""
OnePay — URL Validator Service with SSRF Protection

Enhanced URL validation with DNS rebinding protection and private IP blocking.
Implements requirements 3.1, 3.2, 3.3, and 3.4 from codebase-improvements spec.

This module now delegates to core.network_security for the underlying IP/CIDR logic.
"""

import logging
from typing import Optional

from core.network_security import (
    MIN_SAFE_TTL,
    PRIVATE_NETWORKS,
    is_private_ip,
    is_restricted_ip,
    resolve_hostname_with_ttl,
    validate_url_security,
)

logger = logging.getLogger(__name__)


def _check_ip_not_restricted(ip: str, url: str, hostname: str) -> Optional[str]:
    """
    Check IP is not AWS metadata, private, or otherwise restricted.
    Returns error message if restricted, None if safe.
    """
    result = is_restricted_ip(ip)
    if result:
        logger.warning("SSRF attempt blocked | url=%s hostname=%s ip=%s reason=%s", url, hostname, ip, result)
        return "The URL resolves to a restricted address"
    return None


def validate_url_for_ssrf(url: str) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Validate URL and resolve to safe IP address with SSRF protection.
    Returns (is_valid, resolved_ip, error_message).

    This is a backwards-compatible wrapper around core.network_security.validate_url_security.
    """
    return validate_url_security(url)


# Re-export for backwards compatibility
__all__ = [
    "validate_url_for_ssrf",
    "is_private_ip",
    "MIN_SAFE_TTL",
    "PRIVATE_NETWORKS",
]
