"""
OnePay — Security utilities
HMAC hash generation, link expiry, input validation.
"""
import hmac
import hashlib
import base64
import secrets
import ipaddress
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlparse

from config import Config


def generate_tx_reference() -> str:
    """
    Generate a cryptographically strong transaction reference.
    Format: ONEPAY-{16 hex chars}  — 64 bits of entropy, unguessable.
    Shortened for better UX while maintaining security.
    """
    return f"ONEPAY-{secrets.token_hex(8).upper()}"


def _normalize_expires_for_signing(expires_at: datetime) -> str:
    """Normalize expiry to a deterministic UTC string for HMAC signing."""
    if expires_at.tzinfo is None:
        expires_utc = expires_at.replace(tzinfo=timezone.utc)
    else:
        expires_utc = expires_at.astimezone(timezone.utc)
    return expires_utc.replace(microsecond=0).strftime("%Y%m%d%H%M%S")


def _hmac_urlsafe_token(secret_key: str, message: str) -> str:
    mac = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    )
    return base64.urlsafe_b64encode(mac.digest()).decode("utf-8").rstrip("=")


def generate_hash_token(tx_ref: str, amount, expires_at: datetime) -> str:
    """
    Create an HMAC-SHA256 hash for the payment link.
    Amount is normalised to 2dp using Decimal to prevent float precision attacks.
    Returns a URL-safe base64 string (no padding).
    """
    normalised   = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    expires_norm = _normalize_expires_for_signing(expires_at)
    message      = f"{tx_ref}:{normalised}:{expires_norm}"
    return _hmac_urlsafe_token(Config.HMAC_SECRET, message)


def _generate_hash_token_with_secret(
    tx_ref: str, amount, expires_at: datetime, secret_key: str
) -> str:
    normalised   = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    expires_norm = _normalize_expires_for_signing(expires_at)
    message      = f"{tx_ref}:{normalised}:{expires_norm}"
    return _hmac_urlsafe_token(secret_key, message)


def verify_hash_token(tx_ref: str, amount, expires_at: datetime, hash_token: str) -> bool:
    """
    Verify a hash token using constant-time comparison (prevents timing attacks).
    Supports optional old-secret rotation via HMAC_SECRET_OLD.
    Legacy (no-expiry) format is intentionally NOT supported — those links
    should be treated as expired and re-issued.
    """
    expected = generate_hash_token(tx_ref, amount, expires_at)
    if hmac.compare_digest(expected, hash_token):
        return True

    # Secret rotation support
    if Config.HMAC_SECRET_OLD:
        expected_old = _generate_hash_token_with_secret(
            tx_ref, amount, expires_at, Config.HMAC_SECRET_OLD
        )
        if hmac.compare_digest(expected_old, hash_token):
            return True

    return False


def generate_expiration_time(minutes: int = None) -> datetime:
    """Return a timezone-aware UTC datetime when the link should expire."""
    minutes = minutes or Config.LINK_EXPIRATION_MINUTES
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def generate_reset_token() -> str:
    """Generate a secure password-reset token."""
    return secrets.token_urlsafe(48)


def validate_return_url(value: str) -> str | None:
    """
    Validate and normalize a customer return URL to prevent open redirects.
    - Allow relative paths starting with /
    - Allow absolute HTTPS URLs only
    - Block javascript:, data:, file:, etc.
    - Block localhost / loopback / private IP literals
    - Block credentials and fragments in URL
    
    VULN-008 FIX: Check length BEFORE parsing, reject if exceeds 500 chars.
    """
    if not value:
        return None

    url = value.strip()
    if not url:
        return None
    
    # VULN-008 FIX: Reject if exceeds max length (don't truncate)
    if len(url) > 500:
        return None

    if url.startswith("/"):
        # Block protocol-relative URLs like //evil.com
        # which browsers resolve as https://evil.com
        if url.startswith("//"):
            return None
        return url

    parsed = urlparse(url)

    if parsed.scheme != "https":
        return None

    if not parsed.hostname:
        return None

    if parsed.fragment or parsed.username or parsed.password:
        return None

    hostname = parsed.hostname.lower()

    if hostname in ("localhost", "127.0.0.1", "::1"):
        return None

    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            return None
    except ValueError:
        pass

    return url


def validate_hash_token_format(hash_token: str) -> bool:
    """Validate that the hash token looks like a base64-url signature."""
    if not hash_token:
        return False
    return bool(re.match(r'^[A-Za-z0-9_-]{20,300}$', hash_token))


def validate_webhook_url(value: str) -> str | None:
    """
    Validate a merchant webhook URL.
    Must be an absolute HTTPS URL pointing to a public host.
    Same rules as validate_return_url but no relative paths allowed.
    
    VULN-008 FIX: Check length BEFORE parsing, reject if exceeds 500 chars.
    """
    if not value:
        return None
    url = value.strip()
    
    # VULN-008 FIX: Reject if exceeds max length (don't truncate)
    if len(url) > 500:
        return None
    
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return None
    if not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    hostname = parsed.hostname.lower()
    if hostname in ("localhost", "127.0.0.1", "::1"):
        return None
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            return None
    except ValueError:
        pass
    return url



