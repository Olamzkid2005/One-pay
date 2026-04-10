"""
OnePay — Core security primitives.

Cryptographic utilities that are foundational to the application.
Moved from services/security.py to emphasize these are core domain primitives,
not external service integrations.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from config import Config


def generate_tx_reference() -> str:
    """
    Generate a cryptographically strong transaction reference.
    Format: ONEPAY-{16 hex chars} — 64 bits of entropy, unguessable.
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
    normalised = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    expires_norm = _normalize_expires_for_signing(expires_at)
    message = f"{tx_ref}:{normalised}:{expires_norm}"
    return _hmac_urlsafe_token(Config.HMAC_SECRET, message)


def _generate_hash_token_with_secret(tx_ref: str, amount, expires_at: datetime, secret_key: str) -> str:
    normalised = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    expires_norm = _normalize_expires_for_signing(expires_at)
    message = f"{tx_ref}:{normalised}:{expires_norm}"
    return _hmac_urlsafe_token(secret_key, message)


def verify_hash_token(tx_ref: str, amount, expires_at: datetime, hash_token: str) -> bool:
    """
    Verify a hash token using constant-time comparison (prevents timing attacks).
    Supports optional old-secret rotation via HMAC_SECRET_OLD.
    """
    expected = generate_hash_token(tx_ref, amount, expires_at)
    if hmac.compare_digest(expected, hash_token):
        return True

    if Config.HMAC_SECRET_OLD:
        expected_old = _generate_hash_token_with_secret(tx_ref, amount, expires_at, Config.HMAC_SECRET_OLD)
        if hmac.compare_digest(expected_old, hash_token):
            return True

    return False


def generate_expiration_time(minutes: Optional[int] = None) -> datetime:
    """Return a timezone-aware UTC datetime when the link should expire."""
    minutes = minutes or Config.LINK_EXPIRATION_MINUTES
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def generate_reset_token() -> str:
    """Generate a secure password-reset token."""
    return secrets.token_urlsafe(48)
