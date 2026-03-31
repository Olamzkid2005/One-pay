"""API key authentication module for machine-to-machine access"""
import secrets


def generate_api_key() -> str:
    """Generate a new API key with secure random bytes
    
    Returns:
        str: API key in format 'onepay_live_<64-hex-chars>' (76 chars total)
    """
    random_bytes = secrets.token_bytes(32)
    hex_string = random_bytes.hex()
    return f"onepay_live_{hex_string}"

import hashlib


def hash_api_key(key: str) -> str:
    """Hash API key using SHA256
    
    Args:
        key: The API key to hash
        
    Returns:
        str: SHA256 hash as hex string (64 characters)
    """
    return hashlib.sha256(key.encode('utf-8')).hexdigest()

from datetime import datetime, timezone
from database import get_db
from models.api_key import APIKey


def validate_api_key(key: str) -> tuple[bool, int | None]:
    """Validate API key and return (is_valid, user_id)
    
    Args:
        key: The API key to validate
        
    Returns:
        tuple: (is_valid, user_id) where user_id is None if invalid
    """
    if not key or not key.startswith('onepay_live_'):
        return False, None
    
    key_hash = hash_api_key(key)
    
    with get_db() as db:
        api_key = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
        
        if not api_key:
            return False, None
        
        # Check expiration
        if api_key.expires_at:
            if api_key.expires_at < datetime.now(timezone.utc):
                return False, None
        
        # Update last used timestamp
        api_key.last_used_at = datetime.now(timezone.utc)
        db.flush()
        
        return True, api_key.user_id


def is_api_key_authenticated() -> bool:
    """Check if current request authenticated via API key
    
    Returns:
        bool: True if request used API key authentication
    """
    from flask import g
    return getattr(g, 'api_key_authenticated', False)
