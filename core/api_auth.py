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
