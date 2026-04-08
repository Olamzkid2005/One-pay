"""
OnePay — URL Validator Service with SSRF Protection

Enhanced URL validation with DNS rebinding protection and private IP blocking.
Implements requirements 3.1, 3.2, 3.3, and 3.4 from codebase-improvements spec.

This service resolves DNS to IP addresses BEFORE making HTTP requests to prevent
SSRF attacks via DNS rebinding (TOCTOU vulnerabilities).

Requirement 3.4: DNS rebinding race condition detection via TTL checks.
"""

import socket
import ipaddress
import logging
import dns.resolver
import dns.exception
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Minimum acceptable TTL in seconds (5 minutes)
# DNS records with TTL < 300 seconds are suspicious and may indicate
# a DNS rebinding attack preparation
MIN_SAFE_TTL = 300

# Private IP ranges (RFC 1918, RFC 3927, RFC 4291, RFC 5735)
PRIVATE_NETWORKS = [
    # IPv4 private ranges
    ipaddress.ip_network('10.0.0.0/8'),          # RFC 1918
    ipaddress.ip_network('172.16.0.0/12'),       # RFC 1918
    ipaddress.ip_network('192.168.0.0/16'),      # RFC 1918
    ipaddress.ip_network('127.0.0.0/8'),         # Loopback
    ipaddress.ip_network('169.254.0.0/16'),      # Link-local (RFC 3927)
    ipaddress.ip_network('224.0.0.0/4'),         # Multicast
    ipaddress.ip_network('240.0.0.0/4'),         # Reserved
    ipaddress.ip_network('0.0.0.0/8'),           # Current network
    # IPv6 ranges
    ipaddress.ip_network('::1/128'),             # Loopback
    ipaddress.ip_network('fe80::/10'),           # Link-local
    ipaddress.ip_network('fc00::/7'),            # Unique local
    ipaddress.ip_network('ff00::/8'),            # Multicast
]


def validate_url_for_ssrf(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate URL and resolve to safe IP address with SSRF protection.
    
    This function implements DNS resolution BEFORE HTTP requests to prevent
    DNS rebinding attacks (TOCTOU). The resolved IP should be used directly
    for HTTP requests with the original hostname in the Host header.
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    
    Requirement 3.4: DNS rebinding race condition detection via TTL checks.
    If DNS TTL is suspiciously low (< 300 seconds), the request is rejected
    as it may indicate a DNS rebinding attack preparation.
    
    Args:
        url: The URL to validate (must be HTTP or HTTPS)
    
    Returns:
        Tuple of (is_valid, resolved_ip, error_message):
        - is_valid: True if URL is safe to use, False otherwise
        - resolved_ip: The resolved IP address if valid, None otherwise
        - error_message: Human-readable error if invalid, None if valid
    
    Example:
        >>> is_valid, ip, error = validate_url_for_ssrf("https://example.com/logo.png")
        >>> if is_valid:
        ...     # Use ip for HTTP request with Host: example.com header
        ...     response = requests.get(f"https://{ip}/logo.png", 
        ...                            headers={"Host": "example.com"})
    """
    try:
        # Parse URL
        parsed = urlparse(url)
        
        # Requirement 3.1: Only allow HTTP/HTTPS
        if parsed.scheme not in ('http', 'https'):
            return False, None, "URL must use HTTP or HTTPS protocol"
        
        hostname = parsed.hostname
        if not hostname:
            return False, None, "URL must have a valid hostname"
        
        # Requirement 3.4: Check DNS TTL for race condition detection
        # Use dnspython for TTL information
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 5
            
            # Query A record (IPv4)
            answers = resolver.resolve(hostname, 'A')
            
            # Check TTL of DNS response
            ttl = answers.rrset.ttl
            
            # Requirement 3.4: Reject if TTL is suspiciously low
            if ttl < MIN_SAFE_TTL:
                logger.warning(
                    "DNS rebinding race condition suspected | url=%s hostname=%s ttl=%d min_ttl=%d",
                    url, hostname, ttl, MIN_SAFE_TTL
                )
                return False, None, (
                    f"DNS TTL too low ({ttl}s < {MIN_SAFE_TTL}s). "
                    "This may indicate a DNS rebinding attack. Request rejected for security."
                )
            
            # Get first IP address from response
            ip = str(answers[0])
            
            logger.debug(
                "DNS resolution successful | url=%s hostname=%s ip=%s ttl=%d",
                url, hostname, ip, ttl
            )
            
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer) as e:
            logger.warning(
                "DNS resolution failed (no record) | url=%s hostname=%s error=%s",
                url, hostname, str(e)
            )
            return False, None, f"DNS resolution failed: {str(e)}"
        except dns.exception.Timeout as e:
            logger.warning(
                "DNS resolution timeout | url=%s hostname=%s error=%s",
                url, hostname, str(e)
            )
            return False, None, "DNS resolution timed out"
        except Exception as e:
            # Fallback to socket.gethostbyname if dnspython fails
            # This provides backward compatibility but without TTL checking
            logger.warning(
                "DNS TTL check failed, falling back to socket | url=%s hostname=%s error=%s",
                url, hostname, str(e)
            )
            try:
                ip = socket.gethostbyname(hostname)
                logger.info(
                    "DNS resolution via socket (no TTL check) | url=%s hostname=%s ip=%s",
                    url, hostname, ip
                )
            except socket.gaierror as socket_error:
                logger.warning(
                    "DNS resolution failed | url=%s hostname=%s error=%s",
                    url, hostname, str(socket_error)
                )
                return False, None, f"DNS resolution failed: {str(socket_error)}"
        
        # Additional check for AWS metadata endpoint (common SSRF target)
        # Check this BEFORE general private IP checks for specific error message
        if str(ip) == "169.254.169.254":
            logger.warning(
                "SSRF attempt blocked (AWS metadata) | url=%s hostname=%s ip=%s",
                url, hostname, ip
            )
            return False, None, "Access to AWS metadata endpoint is not allowed"
        
        # Requirement 3.2: Check if IP is private/internal
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError as e:
            logger.error(
                "Invalid IP address | url=%s hostname=%s ip=%s error=%s",
                url, hostname, ip, str(e)
            )
            return False, None, f"Invalid IP address: {str(e)}"
        
        # Check against all private network ranges
        for network in PRIVATE_NETWORKS:
            if ip_obj in network:
                logger.warning(
                    "SSRF attempt blocked | url=%s hostname=%s ip=%s network=%s",
                    url, hostname, ip, network
                )
                return False, None, f"Private IP address not allowed: {ip} (network: {network})"
        
        # Requirement 3.3: Return resolved IP for Host header binding
        logger.info(
            "URL validated successfully | url=%s hostname=%s ip=%s",
            url, hostname, ip
        )
        return True, ip, None
        
    except Exception as e:
        logger.error(
            "URL validation error | url=%s error=%s",
            url, str(e)
        )
        return False, None, f"Validation error: {str(e)}"


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
        # Invalid IP address
        return True  # Fail closed - treat invalid IPs as private
