"""
OnePay — Network security primitives.

Consolidates all IP/CIDR blocklists and URL validation logic that was
previously scattered across url_validator.py, security.py, and webhook.py.

Provides unified functions for:
- Private IP detection (RFC 1918, RFC 3927, RFC 4291, RFC 5735)
- AWS metadata endpoint blocking (169.254.169.254)
- DNS rebinding protection via TTL checks
- URL security validation with DNS resolution
"""

import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Minimum acceptable TTL in seconds (5 minutes)
# DNS records with TTL < 300 seconds are suspicious and may indicate
# a DNS rebinding attack preparation
MIN_SAFE_TTL = 300

# Private IP ranges (RFC 1918, RFC 3927, RFC 4291, RFC 5735)
# Consolidated from services/url_validator.py and services/security.py
PRIVATE_NETWORKS = [
    # IPv4 private ranges
    ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),  # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local (RFC 3927)
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
    ipaddress.ip_network("0.0.0.0/8"),  # Current network
    # IPv6 ranges
    ipaddress.ip_network("::1/128"),  # Loopback
    ipaddress.ip_network("fe80::/10"),  # Link-local
    ipaddress.ip_network("fc00::/7"),  # Unique local
    ipaddress.ip_network("ff00::/8"),  # Multicast
]


def is_private_ip(ip_str: str) -> bool:
    """
    Check if an IP address is private, loopback, link-local, or multicast.

    Args:
        ip_str: IP address as string (IPv4 or IPv6)

    Returns:
        True if IP is private/internal, False if public

    Example:
        >>> is_private_ip("192.168.1.1")
        True
        >>> is_private_ip("8.8.8.8")
        False
    """
    try:
        ip_obj = ipaddress.ip_address(ip_str)

        for network in PRIVATE_NETWORKS:
            if ip_obj in network:
                return True

        return False

    except ValueError:
        return True


def is_restricted_ip(ip_str: str) -> Optional[str]:
    """
    Check if IP is restricted (private, localhost, or AWS metadata).

    Args:
        ip_str: IP address as string

    Returns:
        None if safe, error message if restricted
    """
    if ip_str == "169.254.169.254":
        return "AWS metadata endpoint blocked"

    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return "Invalid IP address"

    for network in PRIVATE_NETWORKS:
        if ip_obj in network:
            return f"IP in restricted range: {network}"

    return None


def is_safe_hostname(hostname: str) -> bool:
    """
    Check if hostname resolves to a safe (non-private) IP.

    Does NOT perform DNS rebinding protection - use is_safe_url for that.

    Args:
        hostname: DNS hostname to check

    Returns:
        True if hostname resolves to public IP, False otherwise
    """
    if hostname in ("localhost", "127.0.0.1", "::1"):
        return False

    try:
        ip = socket.gethostbyname(hostname)
        return not is_private_ip(ip)
    except socket.gaierror:
        return False


def resolve_hostname_with_ttl(
    hostname: str, url: str, require_safe_ttl: bool = True
) -> tuple[Optional[str], Optional[str]]:
    """
    Resolve hostname to IP using dnspython with optional TTL check.
    Falls back to socket.gethostbyname if dnspython unavailable.

    Args:
        hostname: DNS hostname to resolve
        url: Original URL (for logging)
        require_safe_ttl: If True, reject TTL < MIN_SAFE_TTL (rebinding protection)

    Returns:
        (ip, error_message) — error_message is None on success
    """
    try:
        import dns.exception
        import dns.resolver

        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        answers = resolver.resolve(hostname, "A")

        ttl = answers.rrset.ttl
        if require_safe_ttl and ttl < MIN_SAFE_TTL:
            logger.warning(
                "DNS rebinding suspected | url=%s hostname=%s ttl=%d min_ttl=%d", url, hostname, ttl, MIN_SAFE_TTL
            )
            return None, "DNS TTL too low - possible rebinding attack"

        ip = str(answers[0])
        logger.debug("DNS resolution successful | url=%s hostname=%s ip=%s ttl=%d", url, hostname, ip, ttl)
        return ip, None

    except ImportError:
        pass
    except Exception as e:
        logger.debug("DNS resolution via dnspython failed, falling back to socket: %s", e)

    try:
        ip = socket.gethostbyname(hostname)
        logger.info("DNS resolution via socket (no TTL check) | url=%s hostname=%s ip=%s", url, hostname, ip)
        return ip, None
    except socket.gaierror as e:
        logger.warning("DNS resolution failed | url=%s hostname=%s error=%s", url, hostname, str(e))
        return None, "Hostname could not be resolved"


def validate_url_security(url: str) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Validate URL and resolve to safe IP address with SSRF protection.
    Combines URL parsing, DNS resolution, and private IP blocking.

    Args:
        url: URL to validate (http/https only)

    Returns:
        (is_valid, resolved_ip, error_message)
    """
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return False, None, "URL must use HTTP or HTTPS protocol"

        hostname = parsed.hostname
        if not hostname:
            return False, None, "URL must have a valid hostname"

        ip, err = resolve_hostname_with_ttl(hostname, url, require_safe_ttl=True)
        if err:
            return False, None, err

        restriction = is_restricted_ip(ip)
        if restriction:
            return False, None, f"URL resolves to restricted address: {restriction}"

        logger.debug("URL validated | url=%s hostname=%s ip=%s", url, hostname, ip)
        return True, ip, None

    except Exception as e:
        logger.error("URL validation error | url=%s error=%s", url, str(e))
        return False, None, "URL could not be validated"


def validate_public_url(url: str) -> Optional[str]:
    """
    Validate a URL points to a public host (not private/internal).
    Used for webhook URL validation and return URL validation.

    Args:
        url: URL to validate

    Returns:
        Normalized URL if valid, None if invalid/restricted
    """
    if not url:
        return None

    url = url.strip()
    if len(url) > 500:
        return None

    # Allow relative URLs (for return URLs)
    if url.startswith("/"):
        return None if url.startswith("//") else url

    parsed = urlparse(url)

    # Must be HTTPS for webhooks
    if parsed.scheme != "https":
        return None

    if not parsed.hostname:
        return None

    # Check for credentials in URL
    if parsed.username or parsed.password:
        return None

    # Check hostname doesn't resolve to private IP
    if not is_safe_hostname(parsed.hostname):
        return None

    return url
